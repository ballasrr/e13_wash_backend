from celery import Celery
from celery.schedules import timedelta

celery_app = Celery(
    "e13wash",
    broker="redis://:e13asko@redis:6379/0",
    backend="redis://:e13asko@redis:6379/0",
    include=["app.worker.tasks"]
)

celery_app.conf.beat_schedule = {
    "sync-all-machines-every-minute": {
        "task": "app.worker.tasks.sync_all_machines_task",
        "schedule": timedelta(minutes=1),  # каждую минуту
    },
}

celery_app.conf.timezone = "Europe/Moscow"