from app.celery.celary_app import celery_app
from app.services.crestwave import get_machines, get_events, get_program_launches
from app.db.clickhouse import save_device_events, save_program_launches

def get_today_data_period():
    """Получить период времени с начала дня до текущего момента"""
    from datetime import datetime
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
    end = now.strftime("%Y-%m-%dT%H:%M:%S")
    return start, end