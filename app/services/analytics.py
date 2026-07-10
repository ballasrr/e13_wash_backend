from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.clickhouse import get_clickhouse
from app.models.transaction import Transaction
from datetime import datetime


async def get_app_revenue_by_day(db: AsyncSession, start_date: str, end_date: str, machine_id: int = None):
    """Суммы и количество оплат через мобильное приложение по дням из PostgreSQL"""
    start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

    query = select(
        func.date(Transaction.paid_at).label("day"),
        func.sum(Transaction.paid_amount).label("total")
    ).where(
        Transaction.status.in_(["paid", "machine_started"]),
        func.date(Transaction.paid_at) >= start_obj,
        func.date(Transaction.paid_at) <= end_obj,
    )
    if machine_id:
        query = query.where(Transaction.machine_id == machine_id)
    query = query.group_by(func.date(Transaction.paid_at))

    result = await db.execute(query)
    daily = {row.day.strftime("%Y-%m-%d"): float(row.total or 0) for row in result.all()}

    count_query = select(func.count()).select_from(Transaction).where(
        Transaction.status.in_(["paid", "machine_started"]),
        func.date(Transaction.paid_at) >= start_obj,
        func.date(Transaction.paid_at) <= end_obj,
    )
    if machine_id:
        count_query = count_query.where(Transaction.machine_id == machine_id)

    count_result = await db.execute(count_query)
    washes_count = count_result.scalar() or 0

    return daily, washes_count


def resolve_period(period: str, start: str = None, end: str = None):
    """Определить start/end по типу периода"""
    now = datetime.now()

    if period == "today":
        return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
    elif period == "month":
        return now.replace(day=1).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
    elif period == "all":
        return "2020-01-01", now.strftime("%Y-%m-%d")
    else:
        start_date = start[:10] if start else now.replace(day=1).strftime("%Y-%m-%d")
        end_date = end[:10] if end else now.strftime("%Y-%m-%d")
        return start_date, end_date


async def build_dashboard_data(db: AsyncSession, machine_id: int, period: str, start: str, end: str):
    """Собрать сводные данные дашборда — терминал (ClickHouse) + приложение (Postgres)"""
    start_date, end_date = resolve_period(period, start, end)

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

    launches_count_result = client.execute(f"SELECT COUNT(*) FROM program_launches WHERE {launches_where}")
    launches_count = launches_count_result[0][0] if launches_count_result else 0

    client.disconnect()

    app_daily, app_washes_count = await get_app_revenue_by_day(db, start_date, end_date, machine_id)
    mobile_app_total = sum(app_daily.values())

    all_dates = sorted(set(terminal_daily.keys()) | set(app_daily.keys()))
    daily_chart = [
        {"date": d, "total": terminal_daily.get(d, 0) + app_daily.get(d, 0)}
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