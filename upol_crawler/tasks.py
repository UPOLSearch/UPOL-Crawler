from __future__ import absolute_import, unicode_literals

import cProfile
import datetime
import hashlib
import os
import time

import pymongo
from celery.utils.log import get_task_logger

from upol_crawler.celery import app
from upol_crawler.db import db_mongodb as db
from upol_crawler.settings import *


@app.task(rate_limit=CONFIG.get('Settings', 'crawl_frequency'), queue='crawler', ignore_result=True, task_compression='zlib')
def crawl_url_task(url, depth):
    from upol_crawler.core import crawler

    if CONFIG.getboolean('Debug', 'cprofile_crawl_task'):
        os.makedirs(CPROFILE_DIR, exist_ok=True)

        actual_time = str(datetime.datetime.now()).encode('utf-8')

        cprofile_filename = hashlib.sha1(actual_time).hexdigest()
        cprofile_path = os.path.join(CPROFILE_DIR, cprofile_filename)

        cProfile.runctx('crawler.crawl_url(url, depth)',
                        globals=globals(),
                        locals=locals(),
                        filename=cprofile_path)
    else:
        crawler.crawl_url(url, depth)


@app.task(queue='collector', ignore_result=True, task_compression='zlib')
def collect_url_info_task(url, info_type, args={}):
    client = pymongo.MongoClient('localhost', 27017, maxPoolSize=None)
    database = client[DATABASE_NAME]

    db.insert_url_info(database, url, info_type, args)

    client.close()
