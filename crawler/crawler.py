import requests
import pymongo
import crawler
import re
from bs4 import BeautifulSoup
from crawler import config
from crawler.urls import validator
from crawler.urls import parser
from crawler.urls import url_tools
from crawler.urls import robots
from crawler.db import db_mongodb as db
# from crawler import tasks
from crawler import logger

def request_url(url):
    """Request url and check if content-type is valid"""
    headers = {'user-agent': config.user_agent}
    response = requests.head(url, headers=headers, verify=config.verify_ssl)

    if validator.validate_content_type(response.headers['Content-Type']):
        return requests.get(url, headers=headers, verify=config.verify_ssl)
    else:
        return None

    # return requests.get(url, headers=headers, verify=config.verify_ssl)


def get_url(url):
    """Return url, original_url and boolean if url was redirected"""
    response = request_url(url)
    redirected = False
    original_url = url

    url = url_tools.clean(response.url)

    # Experimental fix for session id in url
    re.sub('\&sid=[0-9a-zA-Z]*', '', url)
    re.sub('\&sid=[0-9a-zA-Z]*', '', original_url)

    if original_url != url:
        redirected = True

    return url, original_url, redirected, response


def crawl_url(url, value):
    # crawler.tasks.log_url_validator_task.delay(url, "visiting")
    client = pymongo.MongoClient('localhost', 27017)
    database = client.upol_crawler

    try:
        url, original_url, redirected, response = get_url(url)
    except Exception as e:
        crawler.tasks.log_url_reason_task.delay(url, "exception", {"place": "get_url", "info": str(e)})
        raise
    else:
        # crawler.tasks.log_url_validator_task.delay(url, "visited")

        # Content type is invalid
        if response is None:
            # Set original_url to visited, because original url is invalid.
            if redirected:
                db.set_visited_url(database, url)

            client.close()
            return response, "Response is", redirected

        if redirected:
            # crawler.tasks.log_url_validator_task.delay(url, "redirected")

            # Check if redirected url is valid
            valid, reason = validator.validate(url)

            if not valid:
                client.close()
                crawler.tasks.log_url_reason_task.delay(url, "not_valid_redirect", {"reason": reason, "original_url": original_url})
                return response, "URL is not valid", redirected

            if not db.exists_url(database, url):
                if url_tools.is_same_domain(url, original_url):
                    db.insert_url(database, url, True, value - 1)
                else:
                    db.insert_url(database, url, True, config.max_value)
            else:
                if db.is_visited(database, url):
                    client.close()

                    crawler.tasks.log_url_task.delay(url, logger.get_log_format(response))

                    return response, "URL is already visited", redirected
                else:
                    db.set_visited_url(database, url)

        # Begin parse part, should avoid 404
        try:
            html = response.text
            soup = BeautifulSoup(html, "lxml")

            validated_urls_on_page = parser.validated_page_urls(soup, url)
            # crawler.tasks.log_url_validator_task.delay(url, "parsing", len(validated_urls_on_page))

            for page_url in validated_urls_on_page:
                page_url = url_tools.clean(page_url)

                if url_tools.is_same_domain(url, page_url):
                    if value - 1 != 0:
                        db.insert_url(database, page_url, False, value - 1)
                    else:
                        crawler.tasks.log_url_reason_task.delay(url, "UrlDepthLimit")
                else:
                    db.insert_url(database, page_url, False, config.max_value)
        except Exception as e:
            crawler.tasks.log_url_reason_task.delay(url, "exception", {"place": "parser", "info": str(e)})
            raise


        crawler.tasks.log_url_task.delay(url, logger.get_log_format(response))
        client.close()
        return response, "URL done", redirected
