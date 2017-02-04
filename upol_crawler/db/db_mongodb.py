import random
import urllib.parse
from datetime import datetime

import pymongo
from upol_crawler.settings import *
from upol_crawler.urls import parser, url_tools


# Global database connection
# client = pymongo.MongoClient('localhost', 27017, maxPoolSize=None)
# database = client[DATABASE_NAME]


def init(db):
    db['Urls'].create_index('visited')
    db['Urls'].create_index('queued')
    db['Urls'].create_index('timeout')


def _universal_insert_url(url, collection, visited, queued, depth):
    url_object = {'_id': url_tools.hash(url),
                  'url': url,
                  'domain': url_tools.domain(url),
                  'depth': depth,
                  'visited': visited,
                  'queued': queued}

    url_object['progress'] = {}
    url_object['progress']['discovered'] = str(datetime.now())

    try:
        result = collection.insert_one(url_object).inserted_id
    except pymongo.errors.DuplicateKeyError as e:
        return False

    return result


def insert_url(db, url, visited, queued, depth):
    """Insert url into db"""
    return _universal_insert_url(url, db['Urls'], visited, queued, depth)


def delete_url(db, url):
    """Try to delete url from db, returns True if case of success"""
    result = db['Urls'].delete_one({'_id': url_tools.hash(url)})

    return result.deleted_count > 0


def exists_url(db, url):
    """Return if url is exists in db"""
    url_hash = url_tools.hash(url)

    result = db['Urls'].find_one({'_id': url_hash})

    return result is not None


# def get_unvisited_url(db):
#     """Return unvisited url from db"""
#     result = db["Urls"].find_one({'visited': False})
#
#     if result is not None:
#         return result['url'], result['depth']
#     else:
#         return None, None
#
#
# def get_random_unvisited_url(db):
#     """Return random unvisited url"""
#     result = list(db["Urls"].aggregate([{"$match": {'visited': False}}, {"$sample": {'size': 1}}]))
#     if len(result) != 0:
#         return result[0]['url'], result[0]['depth']
#     else:
#         return None, None


def get_url_for_crawl(db):
    """Return url from db which is ready for crawling - unvisited and unqueued"""
    result = db['Urls'].find_one({'$and': [
                                {'visited': False},
                                {'queued': False},
                                {'timeout': {'$exists': False}}
                              ]})

    if result is not None:
        return result['url'], result['depth']
    else:
        return None, None


def get_random_url_for_crawl(db):
    """Return random url from db which is ready for crawling - unvisited and unqueued"""
    result = list(db['Urls'].aggregate([{'$match':
                                        {'$and': [
                                          {'visited': False},
                                          {'queued': False},
                                          {'timeout': {'$exists': False}}]}}, {'$sample': {'size': 1}}]))

    if len(result) != 0:
        return result[0]['url'], result[0]['depth']
    else:
        return None, None


def set_visited_url(db, url, response, html):
    """Try to set url to visited and update other important informations"""
    url_hash = url_tools.hash(url)

    url_addition = {}

    url_addition['visited'] = True
    url_addition['queued'] = False

    url_addition['progress.last_visited'] = str(datetime.now())

    url_addition['content.html'] = html
    url_addition['content.hashes.document'] = parser.hash_document(html)
    url_addition['content.encoding'] = response.encoding
    # Later detect language

    url_addition['response.elapsed'] = str(response.elapsed)
    url_addition['response.redirect'] = response.is_redirect
    url_addition['response.status_code'] = response.status_code
    url_addition['response.reason'] = response.reason

    for key, value in response.headers.items():
        url_addition['response.' + str(key)] = str(value)

    # url_addition = {'$set': {'visited': True,
    #                          'queued': False,
    #                          'progress.last_visited': str(datetime.now()),
    #                          'content.html': html,
    #                          'content.encoding': response.encoding,
    #                          'content.hashes.document': parser.hash_document(html),
    #                          'response.elapsed': str(response.elapsed),
    #                          'response.redirect': response.is_redirect,
    #                          'response.status_code': response.status_code,
    #                          'response.reason': response.reason}}

    result = db['Urls'].find_one_and_update({'_id': url_hash}, {'$set': url_addition})

    return result is not None


def set_queued_url(db, url):
    """Try to set url to queued"""
    url_hash = url_tools.hash(url)

    result = db['Urls'].find_one_and_update({'_id': url_hash}, {'$set': {'queued': True}})

    return result is not None


def set_timeout_url(db, url):
    """Try to set url as timouted"""
    url_hash = url_tools.hash(url)

    result = db['Urls'].find_one_and_update({'_id': url_hash}, {'$set': {'queued': False,
                                                                         'timeout.timeout': True,
                                                                         'timeout.last_timeout': str(datetime.now())}})

    return result is not None

def is_visited_or_queued(db, url):
    """Check if url is visited"""
    result = db['Urls'].find_one({'$or': [
                                {'visited': True},
                                {'queued': True}
                              ]})

    if result is not None:
        return True


def should_crawler_wait(db):
    """Check if some url is in queue"""
    result = db['Urls'].find_one({'$or': [{'$and': [{'visited': False}, {'queued': True}]},
                                          {'$and': [{'visited': False}, {'queued': False}, {'timeout': {'$exists': False}}]}]})

    return not ((result is None) or (len(result) == 0))


def insert_crawler_start(db):
    """Save when crawler start into database"""
    result = db['CrawlerInfo'].update({'_id': 1}, {'$set': {'time.start': str(datetime.now())}}, upsert=True)

    return result is not None


def insert_crawler_end(db):
    """Save when crawler start into database"""
    result = db['CrawlerInfo'].update({'_id': 1}, {'$set': {'time.end': str(datetime.now())}}, upsert=True)

    return result is not None


def flush_db():
    """Delete everything from database"""
    return db['Urls'].drop()
