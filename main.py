from crawler import tasks
from crawler.db import db_mongodb as db
from time import sleep

from celery.app.control import Control
from crawler.celery import app

# Temporal solution
db.insert_url("http://www.inf.upol.cz")


def is_worker_running():
    inspect = app.control.inspect()

    active = inspect.active()
    registered = inspect.registered()
    scheduled = inspect.scheduled()

    if len(active.items()) + len(registered.items()) + len(scheduled.items()) > 0:
        return True
    else:
        return False


while True:
    url = db.random_unvisited_url()

    if url is not None:
        print("FEEDING QUEUE")
        db.set_visited_url(url)
        tasks.crawl_url_task.delay(url)
    else:
        if is_worker_running():
            print("WORKER IS RUNNING - SLEEPING")
            sleep(5)
        else:
            print("END")
            break
