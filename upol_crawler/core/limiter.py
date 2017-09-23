import socket
import threading
from datetime import datetime

import pymongo
from upol_crawler import settings
from upol_crawler.tools import logger
from upol_crawler.utils import urls

log = logger.universal_logger('limiter')


def insert_limits_for_ip(db, domain, ip, last, max_frequency):
    """Insert limits for specific IP"""
    result = db['Limiter'].insert_one({'ip': ip,
                                       'domain': domain,
                                       'last': str(last),
                                       'max_frequency': max_frequency})

    return result is not None


def get_limits_for_ip(db, ip):
    """Return limits informations for specific IP"""
    result = db['Limiter'].find_one({'ip': ip})

    return result


def set_last_for_ip_limit(db, ip, last):
    """Set the last property for specific IP"""
    result = db['Limiter'].update({'ip': ip},
                                  {'$set':
                                   {'last': str(last)}})

    return result is not None


def _time_difference_from_now(time):
    """Return time difference from time to now"""
    delta = datetime.now() - time
    return delta.total_seconds()


def get_ip(url):
    """Return IP of website from URL"""
    domain = urls.domain(url)
    return socket.gethostbyname(domain)


def is_crawl_allowed(url):
    """Check if crawler is allowed to crawl given URL"""
    client = pymongo.MongoClient(
      settings.DB_SERVER,
      settings.DB_PORT,
      maxPoolSize=None)
    database = client[settings.DB_NAME]

    ip = get_ip(url)

    result = True
    record = get_limits_for_ip(database, ip)

    if record is not None:
        try:
            last = datetime.strptime(record['last'], '%Y-%m-%d %H:%M:%S.%f')
        except ValueError as e:
            last = datetime.strptime(record['last'], '%Y-%m-%d %H:%M:%S')

        delta = _time_difference_from_now(last)

        if delta < float(record['max_frequency']):
            result = False
        else:
            set_last_for_ip_limit(database, ip, datetime.now())

    else:
        insert_limits_for_ip(database,
                             urls.domain(url),
                             ip,
                             datetime.now(),
                             settings.FREQUENCY_PER_SERVER)

    if not result:
        log.info('Limited: {0}'.format(url))

    return result
