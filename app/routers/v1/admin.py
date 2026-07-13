from fastapi import APIRouter
from datetime import datetime, timedelta
from app.services.crestwave import (
    get_machines,
    get_device_status,
    get_summary_report,
    get_program_launches,
    get_post_status,
    get_events
)
from app.db.clickhouse import save_device_events, save_program_launches, save_financial_report
from app.worker.tasks import sync_historical_task
from app.worker.celary_app import celery_app
from celery.result import AsyncResult

router = APIRouter(prefix="/admin", tags=["admin"])


def get_period(period: str):
    now = datetime.now()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
        end = now.strftime("%Y-%m-%dT%H:%M:%S")
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
        end = now.strftime("%Y-%m-%dT%H:%M:%S")
    elif period == "last_month":
        first_this = now.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        start = last_month_end.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
        end = last_month_end.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
        end = now.strftime("%Y-%m-%dT%H:%M:%S")
    return start, end


@router.get("/machines", summary="Список всех моек")
async def machines():
    return await get_machines()


@router.get("/machines/{machine_id}/status", summary="Статус устройства онлайн/офлайн")
async def machine_status(machine_id: int):
    return await get_device_status(machine_id)


@router.get("/machines/{machine_id}/post-status", summary="Статус поста свободен/занят")
async def post_status(machine_id: int):
    return await get_post_status(machine_id)




@router.post("/sync/all", summary="Синхронизировать все мойки в ClickHouse")
async def sync_all_machines(
    period: str = "today",
    start: str = None,
    end: str = None
):
    machines_data = await get_machines()
    all_machines = machines_data.get("machines", [])

    if start and end:
        period_start, period_end = start, end
    else:
        period_start, period_end = get_period(period)

    results = []
    for machine in all_machines:
        events_data = await get_events(machine["id"], period_start, period_end)
        events = events_data.get("events", [])
        save_device_events(machine["id"], machine["name"], events)

        launches_data = await get_program_launches(machine["id"], period_start, period_end)
        launches = launches_data.get("program_launches", [])
        save_program_launches(machine["id"], machine["name"], launches)

        report = await get_summary_report(machine["serial"], period_start, period_end)
        save_financial_report(machine["id"], machine["name"], report)

        results.append({
            "machine_id": machine["id"],
            "machine_name": machine["name"],
            "events_saved": len(events),
            "launches_saved": len(launches),
        })

    return {
        "status": "ok",
        "period": {"start": period_start, "end": period_end},
        "machines": results
    }

