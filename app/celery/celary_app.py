from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "e13wash", # имя приложения
    broker="redis://:e13asko@redis:6379/0", # куда отправлять задачи
    backend="redis://:e13asko@redis:6379/0", # куда сохранять результаты
    include=["app.tasks"] # где искать задачи
)

celery_app.conf.beat_schedule = {
    "sync-all-machines-every-hour": { # название расписания
        "task": "app.tasks.sync_all_machines_task", # какую задачу запускать
        "schedule": crontab(minute=0, hour="*"), # когда — каждый час в 0 минут
    },
}

celery_app.conf.timezone = "Europe/Moscow"