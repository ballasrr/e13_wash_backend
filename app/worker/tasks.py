from app.worker.celary_app import celery_app
from app.services.crestwave import get_machines, get_events, get_program_launches, get_summary_report
from app.db.clickhouse import save_device_events, save_program_launches, save_financial_report
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_all())
        return result
    finally:
        loop.close()


async def _sync_all():
    machines_data = await get_machines()
    machines = machines_data.get("machines", [])

    results = []
    for machine in machines:
        period_start, period_end = get_sync_period(machine["id"])

        events_data = await get_events(machine["id"], period_start, period_end)
        events = events_data.get("events", [])
        save_device_events(machine["id"], machine["name"], events)

        launches_data = await get_program_launches(machine["id"], period_start, period_end)
        launches = launches_data.get("program_launches", [])
        save_program_launches(machine["id"], machine["name"], launches)

        today_start = datetime.now().replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
        today_end = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        summary_report = await get_summary_report(machine["serial"], today_start, today_end)
        save_financial_report(machine["id"], machine["name"], summary_report)

        results.append({
            "machine_id": machine["id"],
            "machine_name": machine["name"],
            "period_start": period_start,
            "period_end": period_end,
            "events_saved": len(events),
            "launches_saved": len(launches),
        })

    return results


@celery_app.task(
    name="app.worker.tasks.sync_historical_task",
    bind=True
)
def sync_historical_task(self, machine_id: int, start_date: str, end_date: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_historical(self, machine_id, start_date, end_date))
        return result
    finally:
        loop.close()


async def _sync_historical(task, machine_id: int, start_date: str, end_date: str):
    machines_data = await get_machines()
    machines = machines_data.get("machines", [])
    machine = next((m for m in machines if m["id"] == machine_id), None)

    if not machine:
        return {"error": "Машина не найдена"}

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    total_days = (end - current).days + 1

    total_events = 0
    total_launches = 0
    days_done = 0
    days_failed = []

    while current <= end:
        day_start = current.strftime("%Y-%m-%dT00:00:00")
        day_end = current.strftime("%Y-%m-%dT23:59:59")

        try:
            events_data = await get_events(machine_id, day_start, day_end)
            events = events_data.get("events", [])
            save_device_events(machine_id, machine["name"], events)

            launches_data = await get_program_launches(machine_id, day_start, day_end)
            launches = launches_data.get("program_launches", [])
            save_program_launches(machine_id, machine["name"], launches)

            summary_report = await get_summary_report(machine["serial"], day_start, day_end)
            save_financial_report(machine_id, machine["name"], summary_report)

            total_events += len(events)
            total_launches += len(launches)
        except Exception as e:
            days_failed.append(day_start[:10])

        days_done += 1

        task.update_state(
            state="PROGRESS",
            meta={
                "current_date": day_start[:10],
                "days_done": days_done,
                "total_days": total_days,
                "total_events": total_events,
                "total_launches": total_launches,
                "days_failed": days_failed,
            }
        )

        current += timedelta(days=1)

    return {
        "status": "completed",
        "days_done": days_done,
        "total_events": total_events,
        "total_launches": total_launches,
        "days_failed": days_failed,
    }


@celery_app.task(
    name="app.worker.tasks.resync_recent_days_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=10
)
def resync_recent_days_task():
    """Перепроверить и дозаполнить последние 7 дней — страховка от пропусков синхронизации"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_resync_recent_days())
        return result
    finally:
        loop.close()


async def _resync_recent_days(days_back: int = 14):
    """Пройтись по последним N дням и перезаписать financial_report + program_launches свежими данными с CrestWave"""
    machines_data = await get_machines()
    machines = machines_data.get("machines", [])

    results = []
    for machine in machines:
        resynced = 0
        for day_offset in range(days_back):
            target_day = datetime.now() - timedelta(days=day_offset)
            day_start = target_day.strftime("%Y-%m-%dT00:00:00")
            day_end = target_day.strftime("%Y-%m-%dT23:59:59")

            try:
                summary_report = await get_summary_report(machine["serial"], day_start, day_end)
                save_financial_report(machine["id"], machine["name"], summary_report)

                launches_data = await get_program_launches(machine["id"], day_start, day_end)
                launches = launches_data.get("program_launches", [])
                save_program_launches(machine["id"], machine["name"], launches)

                resynced += 1
            except Exception:
                continue

        results.append({"machine_id": machine["id"], "resynced_days": resynced})

    return results