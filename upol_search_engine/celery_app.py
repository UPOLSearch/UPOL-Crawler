# from __future__ import absolute_import

from celery import Celery
from kombu import Exchange, Queue
from upol_search_engine import settings


class Config(object):
    broker_url = 'amqp://guest:guest@localhost:5672//'
    result_backend = 'amqp://guest:guest@localhost:5672//'

    task_queues = (
        Queue(
            'crawler',
            exchange=Exchange('crawler'),
            routing_key='crawler'
        ),
        Queue(
            'feeder',
            exchange=Exchange('feeder'),
            routing_key='feeder'
        ),
    )

    enable_utc = False
    timezone = 'Europe/Prague'
    include = ['upol_search_engine.upol_crawler.tasks']
    # worker_hijack_root_logger = False
    log_file = settings.CONFIG.get('Settings', 'log_dir')
    task_acks_late = True


app = Celery('celery_app')
app.config_from_object(Config)

if __name__ == '__main__':
    app.start()
