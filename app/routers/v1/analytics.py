from fastapi import APIRouter, Query, Depends
from sqlalchemy import func, select
from app.db.clickhouse import get_clickhouse
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.models.transaction import Transaction

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_default_period():
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
    end = now.strftime("%Y-%m-%dT%H:%M:%S")
    return start, end


@router.get("/launches", summary="Запуски программ из ClickHouse")
async def get_launches(
    machine_id: int = None,
    start: str = None,
    end: str = None,
    limit: int = 100
):
    if not start or not end:
        start, end = get_default_period()

    client = get_clickhouse()

    where = f"event_date BETWEEN '{start}' AND '{end}'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    rows = client.execute(f"""
        SELECT
            machine_id,
            machine_name,
            program_name,
            program_price,
            cash_amount,
            card_amount,
            bonus_amount,
            cloud_amount,
            loyalty_card_amount,
            total_amount,
            loyalty_msisdn,
            event_date
        FROM program_launches
        WHERE {where}
        ORDER BY event_date DESC
        LIMIT {limit}
    """)

    client.disconnect()

    return {
        "total": len(rows),
        "launches": [
            {
                "machine_id": r[0],
                "machine_name": r[1],
                "program_name": r[2],
                "program_price": r[3],
                "cash_amount": r[4],
                "card_amount": r[5],
                "bonus_amount": r[6],
                "cloud_amount": r[7],
                "loyalty_card_amount": r[8],
                "total_amount": r[9],
                "loyalty_msisdn": r[10],
                "event_date": r[11].isoformat() if r[11] else None,
            }
            for r in rows
        ]
    }


@router.get("/events", summary="События устройств из ClickHouse")
async def get_device_events(
    machine_id: int = None,
    start: str = None,
    end: str = None,
    limit: int = 100
):
    if not start or not end:
        start, end = get_default_period()

    client = get_clickhouse()

    where = f"event_date BETWEEN '{start}' AND '{end}'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    rows = client.execute(f"""
        SELECT
            machine_id,
            machine_name,
            description,
            event_date,
            status,
            event_type,
            params
        FROM device_events
        WHERE {where}
        ORDER BY event_date DESC
        LIMIT {limit}
    """)

    client.disconnect()

    return {
        "total": len(rows),
        "events": [
            {
                "machine_id": r[0],
                "machine_name": r[1],
                "description": r[2],
                "event_date": r[3].isoformat() if r[3] else None,
                "status": r[4],
                "event_type": r[5],
                "params": r[6],
            }
            for r in rows
        ]
    }


@router.get("/stats", summary="Сводная статистика по мойкам")
async def get_stats(
    machine_id: int = None,
    start: str = None,
    end: str = None
):
    if not start or not end:
        start, end = get_default_period()

    client = get_clickhouse()

    where = f"event_date BETWEEN '{start}' AND '{end}'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    rows = client.execute(f"""
        SELECT
            machine_id,
            machine_name,
            COUNT(*) as total_launches,
            SUM(total_amount) as total_revenue,
            SUM(cash_amount) as cash_revenue,
            SUM(card_amount) as card_revenue,
            SUM(bonus_amount) as bonus_revenue,
            SUM(cloud_amount) as cloud_revenue,
            AVG(total_amount) as avg_check
        FROM program_launches
        WHERE {where}
        GROUP BY machine_id, machine_name
        ORDER BY total_revenue DESC
    """)

    client.disconnect()

    return {
        "period": {"start": start, "end": end},
        "machines": [
            {
                "machine_id": r[0],
                "machine_name": r[1],
                "total_launches": r[2],
                "total_revenue": round(r[3], 2),
                "cash_revenue": round(r[4], 2),
                "card_revenue": round(r[5], 2),
                "bonus_revenue": round(r[6], 2),
                "cloud_revenue": round(r[7], 2),
                "avg_check": round(r[8], 2),
            }
            for r in rows
        ]
    }


@router.get("/top-programs", summary="Топ программ по количеству запусков")
async def get_top_programs(
    machine_id: int = None,
    start: str = None,
    end: str = None,
    limit: int = 10
):
    if not start or not end:
        start, end = get_default_period()

    client = get_clickhouse()

    where = f"event_date BETWEEN '{start}' AND '{end}'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    rows = client.execute(f"""
        SELECT
            program_name,
            COUNT(*) as launches_count,
            SUM(total_amount) as total_revenue,
            AVG(total_amount) as avg_price
        FROM program_launches
        WHERE {where}
        GROUP BY program_name
        ORDER BY launches_count DESC
        LIMIT {limit}
    """)

    client.disconnect()

    return {
        "period": {"start": start, "end": end},
        "programs": [
            {
                "program_name": r[0],
                "launches_count": r[1],
                "total_revenue": round(r[2], 2),
                "avg_price": round(r[3], 2),
            }
            for r in rows
        ]
    }


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


@router.get("/daily-summary", summary="Финансовая сводка по дням (с корректным QR)")
async def get_daily_summary(
    machine_id: int = None,
    start: str = None,
    end: str = None
):
    if not start or not end:
        now = datetime.now()
        start = now.replace(day=1).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

    client = get_clickhouse()

    where = f"report_date BETWEEN '{start}' AND '{end}'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    rows = client.execute(f"""
        SELECT
            report_date,
            SUM(total_amount) as total,
            SUM(cash) as cash,
            SUM(cashless) as cashless,
            SUM(qr) as qr,
            SUM(mobile_app_total) as mobile_app
        FROM financial_report FINAL
        WHERE {where}
        GROUP BY report_date
        ORDER BY report_date DESC
    """)

    client.disconnect()

    summary_row = {
        "date": "Всего",
        "total": sum(r[1] for r in rows),
        "cash": sum(r[2] for r in rows),
        "cashless": sum(r[3] for r in rows),
        "qr": sum(r[4] for r in rows),
        "mobile_app": sum(r[5] for r in rows),
    }

    return {
        "summary": summary_row,
        "days": [
            {
                "date": r[0].strftime("%m-%d"),
                "total": r[1],
                "cash": r[2],
                "cashless": r[3],
                "qr": r[4],
                "mobile_app": r[5],
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
    now = datetime.now()

    if period == "today":
        start_date = now.strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "month":
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
    elif period == "all":
        start_date = "2020-01-01"
        end_date = now.strftime("%Y-%m-%d")
    else:
        start_date = start[:10] if start else now.replace(day=1).strftime("%Y-%m-%d")
        end_date = end[:10] if end else now.strftime("%Y-%m-%d")

    # объекты date для PostgreSQL запросов
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

    client = get_clickhouse()

    where = f"report_date BETWEEN '{start_date}' AND '{end_date}'"
    if machine_id:
        where += f" AND machine_id = {machine_id}"

    summary_rows = client.execute(f"""
        SELECT
            SUM(total_amount) as total,
            SUM(cash) as cash,
            SUM(cashless) as cashless,
            SUM(qr) as qr
        FROM financial_report FINAL
        WHERE {where}
    """)
    s = summary_rows[0] if summary_rows else (0, 0, 0, 0)

    daily_rows = client.execute(f"""
        SELECT report_date, SUM(total_amount) as total
        FROM financial_report FINAL
        WHERE {where}
        GROUP BY report_date
        ORDER BY report_date
    """)
    terminal_daily = {r[0].strftime("%Y-%m-%d"): r[1] for r in daily_rows}

    launches_where = f"toDate(event_date) BETWEEN '{start_date}' AND '{end_date}'"
    if machine_id:
        launches_where += f" AND machine_id = {machine_id}"

    launches_count_result = client.execute(f"""
        SELECT COUNT(*) FROM program_launches WHERE {launches_where}
    """)
    launches_count = launches_count_result[0][0] if launches_count_result else 0

    client.disconnect()

    query = select(
        func.date(Transaction.paid_at).label("day"),
        func.sum(Transaction.paid_amount).label("total")
    ).where(
        Transaction.status.in_(["paid", "machine_started"]),
        func.date(Transaction.paid_at) >= start_date_obj,
        func.date(Transaction.paid_at) <= end_date_obj,
    )
    if machine_id:
        query = query.where(Transaction.machine_id == machine_id)
    query = query.group_by(func.date(Transaction.paid_at))

    result = await db.execute(query)
    app_daily = {row.day.strftime("%Y-%m-%d"): float(row.total or 0) for row in result.all()}

    app_transactions_count_query = select(func.count()).select_from(Transaction).where(
        Transaction.status.in_(["paid", "machine_started"]),
        func.date(Transaction.paid_at) >= start_date_obj,
        func.date(Transaction.paid_at) <= end_date_obj,
    )
    if machine_id:
        app_transactions_count_query = app_transactions_count_query.where(Transaction.machine_id == machine_id)

    app_count_result = await db.execute(app_transactions_count_query)
    app_washes_count = app_count_result.scalar() or 0

    mobile_app_total = sum(app_daily.values())

    all_dates = sorted(set(terminal_daily.keys()) | set(app_daily.keys()))
    daily_chart = [
        {
            "date": d,
            "total": terminal_daily.get(d, 0) + app_daily.get(d, 0)
        }
        for d in all_dates
    ]

    total_revenue = (s[0] or 0) + mobile_app_total
    total_washes = launches_count + app_washes_count

    return {
        "period": {"type": period, "start": start_date, "end": end_date},
        "summary": {
            "total_revenue": total_revenue,
            "cash": s[1] or 0,
            "cashless": s[2] or 0,
            "qr": s[3] or 0,
            "mobile_app": mobile_app_total,
            "total_washes": total_washes,
            "avg_check": round(total_revenue / total_washes, 2) if total_washes else 0,
        },
        "daily_chart": daily_chart
    }