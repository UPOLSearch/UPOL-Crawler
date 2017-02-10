from __future__ import absolute_import, unicode_literals

import cProfile
import datetime
import hashlib
import os
import time

import upol_crawler
from celery.utils.log import get_task_logger
from .celery import app
from .settings import *


@app.task(rate_limit='6/s', queue='crawler', ignore_result=True, task_compression='zlib')
def crawl_url_task(url, depth):
    if CONFIG.getboolean('Debug', 'cprofile_crawl_task'):
        os.makedirs(CPROFILE_DIR, exist_ok=True)

        actual_time = str(datetime.datetime.now()).encode('utf-8')

        cprofile_filename = hashlib.sha1(actual_time).hexdigest()
        cprofile_path = os.path.join(CPROFILE_DIR, cprofile_filename)

        cProfile.runctx('upol_crawler.crawler.crawl_url(url, depth)',
                        globals=globals(),
                        locals=locals(),
                        filename=cprofile_path)
    else:
        upol_crawler.crawler.crawl_url(url, depth)


@app.task(queue='logger', ignore_result=True, task_compression='zlib')
def log_url_reason_task(url, reason, arg={}):
    upol_crawler.logger.log_url_reason(url, reason, arg)
