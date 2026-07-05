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


@router.get("/report", summary="Финансовый отчёт по мойкам")
async def financial_report(
    period: str = "today",
    machine_id: int = None,
    start: str = None,
    end: str = None
):
    machines_data = await get_machines()
    all_machines = machines_data.get("machines", [])

    if machine_id:
        all_machines = [m for m in all_machines if m["id"] == machine_id]

    if start and end:
        period_start, period_end = start, end
    else:
        period_start, period_end = get_period(period)

    result = []
    for machine in all_machines:
        report = await get_summary_report(machine["serial"], period_start, period_end)

        totals = {"cash": 0, "cashless": 0, "qr": 0, "mobileApp": 0}
        if isinstance(report, list):
            for item in report:
                report_type = item.get("washerReportType")
                if report_type in totals:
                    totals[report_type] += item.get("amount", 0)

        result.append({
            "machine_id": machine["id"],
            "machine_name": machine["name"],
            "period": {"start": period_start, "end": period_end},
            "revenue": {
                "cash": totals["cash"],
                "cashless": totals["cashless"],
                "qr": totals["qr"],
                "mobile_app": totals["mobileApp"],
                "total": sum(totals.values())
            }
        })

    return {
        "period": period,
        "total_revenue": sum(m["revenue"]["total"] for m in result),
        "machines": result
    }


@router.get("/launches/{machine_id}", summary="Запуски программ мойки за период")
async def program_launches(
    machine_id: int,
    period: str = "today",
    start: str = None,
    end: str = None
):
    if start and end:
        period_start, period_end = start, end
    else:
        period_start, period_end = get_period(period)
    return await get_program_launches(machine_id, period_start, period_end)


@router.get("/events/{machine_id}", summary="Журнал событий устройства")
async def device_events(
    machine_id: int,
    period: str = "today",
    start: str = None,
    end: str = None
):
    if start and end:
        period_start, period_end = start, end
    else:
        period_start, period_end = get_period(period)
    return await get_events(machine_id, period_start, period_end)


@router.get("/debug/summary/{machine_id}", summary="Сырые данные summary-reports для отладки")
async def debug_summary(machine_id: int, start: str, end: str):
    machines_data = await get_machines()
    all_machines = machines_data.get("machines", [])
    machine = next((m for m in all_machines if m["id"] == machine_id), None)
    if not machine:
        return {"error": "not found"}
    report = await get_summary_report(machine["serial"], start, end)
    types = {}
    if isinstance(report, list):
        for item in report:
            t = item.get("washerReportType")
            types[t] = types.get(t, 0) + (item.get("amount") or 0)
    return {
        "total_records": len(report) if isinstance(report, list) else 0,
        "types_summary": types,
        "sample": report[:3] if isinstance(report, list) else report
    }


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


@router.post("/sync/summary/{machine_id}", summary="Синхронизировать финансовую сводку (с QR) в ClickHouse")
async def sync_summary(
    machine_id: int,
    start: str,
    end: str
):
    machines_data = await get_machines()
    all_machines = machines_data.get("machines", [])
    machine = next((m for m in all_machines if m["id"] == machine_id), None)

    if not machine:
        return {"error": "Мойка не найдена"}

    report = await get_summary_report(machine["serial"], start, end)
    save_financial_report(machine_id, machine["name"], report)

    return {
        "status": "ok",
        "machine_id": machine_id,
        "period": {"start": start, "end": end},
        "records": len(report) if isinstance(report, list) else 0
    }


@router.post("/sync/historical-async/{machine_id}", summary="Запустить историческую синхронизацию в фоне")
async def sync_historical_async(
    machine_id: int,
    start_date: str,
    end_date: str
):
    task = sync_historical_task.delay(machine_id, start_date, end_date)
    return {"task_id": task.id, "status": "started"}


@router.get("/sync/status/{task_id}", summary="Проверить прогресс синхронизации")
async def sync_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return {"state": "pending"}
    elif result.state == "PROGRESS":
        return {"state": "in_progress", **result.info}
    elif result.state == "SUCCESS":
        return {"state": "completed", **result.result}
    elif result.state == "FAILURE":
        return {"state": "failed", "error": str(result.info)}

    return {"state": result.state}


@router.post("/sync/{machine_id}", summary="Синхронизировать данные мойки в ClickHouse")
async def sync_machine_data(
    machine_id: int,
    period: str = "today",
    start: str = None,
    end: str = None
):
    machines_data = await get_machines()
    all_machines = machines_data.get("machines", [])
    machine = next((m for m in all_machines if m["id"] == machine_id), None)

    if not machine:
        return {"error": "Мойка не найдена"}

    if start and end:
        period_start, period_end = start, end
    else:
        period_start, period_end = get_period(period)

    events_data = await get_events(machine_id, period_start, period_end)
    events = events_data.get("events", [])
    save_device_events(machine_id, machine["name"], events)

    launches_data = await get_program_launches(machine_id, period_start, period_end)
    launches = launches_data.get("program_launches", [])
    save_program_launches(machine_id, machine["name"], launches)

    report = await get_summary_report(machine["serial"], period_start, period_end)
    save_financial_report(machine_id, machine["name"], report)

    return {
        "status": "ok",
        "machine_id": machine_id,
        "events_saved": len(events),
        "launches_saved": len(launches),
        "period": {"start": period_start, "end": period_end}
    }