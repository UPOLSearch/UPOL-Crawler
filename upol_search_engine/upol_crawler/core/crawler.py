import re

import pymongo
import requests
from bs4 import BeautifulSoup
from celery.utils.log import get_task_logger
from upol_search_engine import settings
from upol_search_engine.upol_crawler import db
from upol_search_engine.upol_crawler.core import (limiter, link_extractor,
                                                  validator)
from upol_search_engine.upol_crawler.tools import blacklist, robots
from upol_search_engine.upol_crawler.utils import urls

log = get_task_logger(__name__)
# # import the Celery log getter
#     from celery.utils.log import get_task_logger
#
#     # grab the logger for the Celery app
#     logger = get_task_logger(__name__)

def get_response(url, connect_max_timeout, read_max_timeout):
    """Request url and check if content-type is valid"""
    headers = {'user-agent': settings.CONFIG.get('Info', 'user_agent')}
    response = requests.get(url,
                            headers=headers,
                            verify=False,
                            timeout=(
                                connect_max_timeout,
                                read_max_timeout))

    # content_type = response.headers.get('Content-Type')
    #
    # if content_type is not None:
    #     if not validator.validate_content_type(response.headers['Content-Type']):
    #         return None

    return response


def get_page(url, connect_max_timeout, read_max_timeout):
    """Return url, original_url and boolean if url was redirected"""
    response = get_response(url, connect_max_timeout, read_max_timeout)
    original_url = url

    is_redirect = False

    if response is not None:
        # Detect if response is redirect
        for history in response.history:
            if history.is_redirect:
                is_redirect = True
                break

        url = urls.clean(response.url)

    return url, original_url, is_redirect, response


def _handle_response(database, url, original_url, redirected, response, depth, max_depth, limit_domain, blacklist):
    try:
        url_document = db.get_url(database, url)
        regex = urls.generate_regex(limit_domain)

        # Redirect handling
        if original_url != url:
            log.info('Redirect: {0} (original: {1})'.format(original_url, url))

            # Check if redirected url is valid
            is_valid_redirect, reason = validator.validate(url, regex, blacklist)

            if is_valid_redirect:
                db.set_alias_visited_url(database, original_url)

                url_document = db.get_url(database, url)

                if url_document is not None:
                    if url_document.get('visited') and not url_document.get('alias'):
                        canonical_group = url_document.get('canonical_group')
                        db.set_canonical_group_to_alias(database, original_url, canonical_group)
                        return
                else:
                    if not urls.is_same_domain(url, original_url):
                        depth = max_depth

                    db.insert_url(database, url, False, False, depth)

            else:
                db.set_visited_invalid_url(database, original_url, response, "invalid_redirect")
                db.delete_pagerank_edge_to(database, urls.hash(original_url))

                log.info('Not Valid Redirect: {0} (original: {1})'.format(url, original_url))

                return
        else:
            # Check if url is already visited
            if url_document is not None:
                if url_document.get('visited'):
                    log.info('Already visited: {0}'.format(url))
                    return

        # File handling
        content_type = response.headers.get('Content-Type')

        if content_type is None:
            content_type = ''

        if 'text/html' not in content_type:
            # 'application/msword' in content_type or
            # 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in content_type
            if (('application/pdf' not in content_type) and ('text/plain' not in content_type)):
                # Not valid file
                if content_type is not '':
                    content_type = content_type.split(';')[0]
                else:
                    content_type = 'unknown'

                db.delete_pagerank_edge_to(database, urls.hash(url))
                db.set_visited_invalid_url(database, url, response, "invalid_file", True)

                log.info('Not valid file: {0}'.format(url))
                return
            else:
                # Handle file
                if original_url != url:
                    db.set_visited_file_url(database, url, response, original_url)
                else:
                    db.set_visited_file_url(database, url, response)
                log.info('Done (file) [{0}]: {1}'.format(response.reason, url))
        else:
            # Handle normal page
            soup = BeautifulSoup(response.content, 'lxml')
            no_index = link_extractor.has_noindex(soup)
            validated_urls_on_page = link_extractor.validated_page_urls(soup,
                                                                        url,
                                                                        regex,
                                                                        blacklist)

            urls_for_insert = []

            for page_url in validated_urls_on_page:
                insert_url = {'url': page_url}

                if urls.is_same_domain(url, page_url):
                    if depth - 1 != 0:
                        insert_url['depth'] = depth - 1
                    else:
                        continue
                else:
                    insert_url['depth'] = max_depth

                urls_for_insert.append(insert_url)

            if len(urls_for_insert) > 0:
                db.batch_insert_url(database, urls_for_insert, False, False)
                db.batch_insert_pagerank_outlinks(database, url, urls_for_insert)

            if original_url != url:
                db.set_visited_url(database, url, response, soup, no_index, original_url)
            else:
                db.set_visited_url(database, url, response, soup, no_index)

            log.info('Done [{0}]: {1}'.format(response.reason, url))

    except Exception as e:
        db.delete_url(database, url)
        log.exception('Exception: {0}'.format(url))
        raise


def crawl_url(url, depth, crawler_settings):
    try:
        client = db.create_client()
        database = db.get_database(crawler_settings.get('limit_domain'), client)

        if not limiter.is_crawl_allowed(url,
                                        database,
                                        crawler_settings.get('frequency_per_server')):
            db.set_url_for_recrawl(database, url)
            client.close()
            return


        url, original_url, redirected, response = get_page(url,
                                                           crawler_settings.get('connect_max_timeout'),
                                                           crawler_settings.get('read_max_timeout'))
    except requests.exceptions.ReadTimeout as e:
        # It also remove url from queue and set it as timeouted
        db.set_timeout_url(database, url)
        log.warning('(Timeout) - ReadTimeout: {0}'.format(url))
    except requests.exceptions.ConnectionError as e:
        # It also remove url from queue and set it as timeouted
        db.set_timeout_url(database, url)
        log.warning('(Timeout) - ConnectionError: {0}'.format(url))
    except requests.exceptions.ChunkedEncodingError as e:
        # It also remove url from queue and set it as timeouted
        db.set_timeout_url(database, url)
        log.warning('(Timeout) - ChunkedEncodingError: {0}'.format(url))
    except Exception as e:
        db.delete_url(database, url)
        log.exception('Exception: {0}'.format(url))
        client.close()
        raise
    else:
        _handle_response(database,
                         url,
                         original_url,
                         redirected,
                         response,
                         depth,
                         crawler_settings.get('max_depth'),
                         crawler_settings.get('limit_domain'),
                         blacklist.generate_blacklist(crawler_settings.get('blacklist')))

    client.close()