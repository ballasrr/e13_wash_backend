from celery import Celery
from celery.schedules import timedelta, crontab

celery_app = Celery(
    "e13wash",
    broker="redis://:e13asko@redis:6379/0",
    backend="redis://:e13asko@redis:6379/0",
    include=["app.worker.tasks"]
)

celery_app.conf.beat_schedule = {
    "sync-all-machines-every-minute": {
        "task": "app.worker.tasks.sync_all_machines_task",
        "schedule": timedelta(minutes=1),  # каждую минуту — свежие данные за сегодня
    },
    "resync-recent-days-daily": {
        "task": "app.worker.tasks.resync_recent_days_task",
        "schedule": crontab(hour=4, minute=0),  # каждый день в 4:00 ночи — перепроверка последних 14 дней
    },
}

celery_app.conf.timezone = "Europe/Moscow"