from app.worker.celary_app import celery_app
from app.services.crestwave import get_machines, get_events, get_program_launches
from app.db.clickhouse import save_device_events, save_program_launches
from datetime import datetime
import asyncio


def get_today_period():
    """Получить период с начала дня до текущего момента"""
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
    end = now.strftime("%Y-%m-%dT%H:%M:%S")
    return start, end


@celery_app.task(name="app.worker.tasks.sync_all_machines_task")
def sync_all_machines_task():
    """Синхронизировать данные всех моек в ClickHouse"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_all())
        return result
    finally:
        loop.close()


async def _sync_all():
    """Асинхронная логика синхронизации всех моек"""
    machines_data = await get_machines()
    machines = machines_data.get("machines", [])
    period_start, period_end = get_today_period()

    results = []
    for machine in machines:
        # Синхронизация событий устройства
        events_data = await get_events(machine["id"], period_start, period_end)
        events = events_data.get("events", [])
        save_device_events(machine["id"], machine["name"], events)

        # Синхронизация запусков программ
        launches_data = await get_program_launches(machine["id"], period_start, period_end)
        launches = launches_data.get("program_launches", [])
        save_program_launches(machine["id"], machine["name"], launches)

        results.append({
            "machine_id": machine["id"],
            "machine_name": machine["name"],
            "events_saved": len(events),
            "launches_saved": len(launches),
        })

    return results