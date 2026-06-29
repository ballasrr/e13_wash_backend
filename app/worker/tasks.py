from app.worker.celary_app import celery_app
from app.services.crestwave import get_machines, get_events, get_program_launches
from app.db.clickhouse import save_device_events, save_program_launches
from datetime import datetime, timedelta
import asyncio
import redis as redis_lib


REDIS_CLIENT = redis_lib.Redis(
    host="redis",
    port=6379,
    password="e13asko",
    decode_responses=True
)


def get_sync_period(machine_id: int):
    """Получить период синхронизации для мойки"""
    now = datetime.now()
    key = f"last_sync:{machine_id}"
    last_sync = REDIS_CLIENT.get(key)

    if last_sync:
        start = (datetime.fromisoformat(last_sync) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        start = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")

    end = now.strftime("%Y-%m-%dT%H:%M:%S")
    REDIS_CLIENT.set(key, now.isoformat())

    return start, end


@celery_app.task(
    name="app.worker.tasks.sync_all_machines_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=5
)
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

    results = []
    for machine in machines:
        period_start, period_end = get_sync_period(machine["id"])

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
            "period_start": period_start,
            "period_end": period_end,
            "events_saved": len(events),
            "launches_saved": len(launches),
        })

    return results