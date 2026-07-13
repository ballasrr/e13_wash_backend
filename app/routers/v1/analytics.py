from fastapi import APIRouter, Depends
from app.db.clickhouse import get_clickhouse
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.services.analytics import build_dashboard_data, get_all_transactions, get_programs_breakdown
from app.services.reports import build_report_data

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_default_period():
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
    end = now.strftime("%Y-%m-%dT%H:%M:%S")
    return start, end


def parse_machine_ids(machine_id: str = None):
    """machine_id может быть пустым (все станции), '35863' (одна) или '35863,35864' (несколько)"""
    if not machine_id:
        return None
    return [int(x.strip()) for x in machine_id.split(",") if x.strip()]


@router.get("/errors", summary="Ошибки устройств")
async def get_errors(
    machine_id: int = None,
    start: str = None,
    end: str = None,
    limit: int = 100
):
    if not start or not end:
        start, end = get_default_period()

    client = get_clickhouse()

    where = f"event_date BETWEEN '{start}' AND '{end}' AND status = 'ERROR'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    rows = client.execute(f"""
        SELECT
            machine_id,
            machine_name,
            description,
            event_date,
            event_type,
            params
        FROM device_events
        WHERE {where}
        ORDER BY event_date DESC
        LIMIT {limit}
    """)

    client.disconnect()

    return {
        "total_errors": len(rows),
        "errors": [
            {
                "machine_id": r[0],
                "machine_name": r[1],
                "description": r[2],
                "event_date": r[3].isoformat() if r[3] else None,
                "event_type": r[4],
                "params": r[5],
            }
            for r in rows
        ]
    }


@router.get("/errors/summary", summary="Сводка ошибок по мойкам")
async def get_errors_summary(
    start: str = None,
    end: str = None
):
    if not start or not end:
        now = datetime.now()
        start = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        end = now.strftime("%Y-%m-%dT%H:%M:%S")

    client = get_clickhouse()

    rows = client.execute(f"""
        SELECT
            machine_id,
            machine_name,
            event_type,
            COUNT(*) as error_count,
            MAX(event_date) as last_error
        FROM device_events
        WHERE event_date BETWEEN '{start}' AND '{end}'
        AND status = 'ERROR'
        GROUP BY machine_id, machine_name, event_type
        ORDER BY error_count DESC
    """)

    client.disconnect()

    return {
        "period": {"start": start, "end": end},
        "errors": [
            {
                "machine_id": r[0],
                "machine_name": r[1],
                "event_type": r[2],
                "error_count": r[3],
                "last_error": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    }


@router.get("/dashboard", summary="Сводные данные для дашборда админки")
async def get_dashboard(
    machine_id: int = None,
    period: str = "today",
    start: str = None,
    end: str = None,
    db: AsyncSession = Depends(get_db)
):
    return await build_dashboard_data(db, machine_id, period, start, end)


@router.get("/transactions", summary="Все транзакции (терминал + приложение) с пагинацией")
async def transactions(
    machine_id: str = None,
    period: str = "all",
    start: str = None,
    end: str = None,
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now()

    if period == "today":
        start_date = now.strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "month":
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "year":
        start_date = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "custom":
        start_date = start[:10] if start else now.replace(day=1).strftime("%Y-%m-%d")
        end_date = end[:10] if end else now.strftime("%Y-%m-%d")
    else:  # all
        start_date = "2020-01-01"
        end_date = now.strftime("%Y-%m-%d")

    machine_ids = parse_machine_ids(machine_id)

    return await get_all_transactions(db, machine_ids, start_date, end_date, page, page_size)


@router.get("/programs-report", summary="Финансовая статистика + разбивка по тарифам за период")
async def programs_report(
    machine_id: str = None,
    period: str = "month",
    start: str = None,
    end: str = None,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now()

    if period == "today":
        start_date = now.strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "month":
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "year":
        start_date = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "all":
        start_date = "2020-01-01"
        end_date = now.strftime("%Y-%m-%d")
    else:  # custom
        start_date = start[:10] if start else now.replace(day=1).strftime("%Y-%m-%d")
        end_date = end[:10] if end else now.strftime("%Y-%m-%d")

    machine_ids = parse_machine_ids(machine_id)

    totals, days = await build_report_data(db, machine_ids, start_date, end_date, refresh_today=True)
    programs = await get_programs_breakdown(machine_ids, start_date, end_date)

    return {
        "period": {"type": period, "start": start_date, "end": end_date},
        "summary": totals,
        "programs": programs
    }