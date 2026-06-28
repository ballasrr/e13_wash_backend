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


@router.get("/machines")
async def machines():
    return await get_machines()


@router.get("/machines/{machine_id}/status")
async def machine_status(machine_id: int):
    return await get_device_status(machine_id)


@router.get("/machines/{machine_id}/post-status")
async def post_status(machine_id: int):
    return await get_post_status(machine_id)


@router.get("/report")
async def financial_report(
    period: str = "today",
    machine_id: int = None,
    start: str = None,
    end: str = None
):
    machines_data = await get_machines()
    machines = machines_data.get("machines", [])

    if machine_id:
        machines = [m for m in machines if m["id"] == machine_id]

    if start and end:
        period_start, period_end = start, end
    else:
        period_start, period_end = get_period(period)

    result = []
    for machine in machines:
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


@router.get("/launches/{machine_id}")
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


@router.get("/events/{machine_id}")
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