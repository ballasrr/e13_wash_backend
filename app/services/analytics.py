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


async def get_all_transactions(
    db: AsyncSession,
    machine_ids: list = None,
    start: str = None,
    end: str = None,
    page: int = 1,
    page_size: int = 20,
):
    """Объединённый список транзакций: терминал (ClickHouse) + приложение (Postgres)"""

    client = get_clickhouse()
    where = f"event_date BETWEEN '{start} 00:00:00' AND '{end} 23:59:59'"
    if machine_ids:
        ids_str = ",".join(str(i) for i in machine_ids)
        where += f" AND machine_id IN ({ids_str})"

    rows = client.execute(f"""
        SELECT
            machine_id, machine_name, program_name, total_amount,
            cash_amount, card_amount, cloud_amount, loyalty_msisdn, event_date
        FROM program_launches
        WHERE {where}
        ORDER BY event_date DESC
    """)
    client.disconnect()

    terminal_items = [
        {
            "source": "terminal",
            "machine_id": r[0],
            "machine_name": r[1],
            "program_name": r[2],
            "amount": r[3],
            "payment_method": "cash" if r[4] > 0 else ("card" if r[5] > 0 else ("qr" if r[6] > 0 else "unknown")),
            "user_phone": r[7],
            "datetime": r[8],
        }
        for r in rows
    ]

    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()

    query = select(Transaction).where(
        Transaction.status.in_(["paid", "machine_started"]),
        func.date(Transaction.paid_at) >= start_date,
        func.date(Transaction.paid_at) <= end_date,
    )
    if machine_ids:
        query = query.where(Transaction.machine_id.in_(machine_ids))
    query = query.order_by(Transaction.paid_at.desc())

    result = await db.execute(query)
    app_transactions = result.scalars().all()

    app_items = [
        {
            "source": "app",
            "machine_id": t.machine_id,
            "machine_name": None,
            "program_name": t.program_name,
            "amount": t.paid_amount,
            "payment_method": t.payment_method_type,
            "user_phone": None,
            "datetime": t.paid_at,
        }
        for t in app_transactions
    ]

    all_items = terminal_items + app_items
    all_items.sort(key=lambda x: x["datetime"] or datetime.min, reverse=True)

    total_items = len(all_items)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    paginated = all_items[offset:offset + page_size]

    for item in paginated:
        if item["datetime"]:
            item["datetime"] = item["datetime"].strftime("%Y-%m-%d %H:%M:%S")

    return {
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        },
        "transactions": paginated
    }


async def get_programs_breakdown(machine_ids: list, start: str, end: str):
    """Статистика по тарифам за период — реальные деньги (без бонусов), согласовано с financial_report"""
    client = get_clickhouse()

    where = f"toDate(event_date) BETWEEN '{start}' AND '{end}'"
    if machine_ids:
        ids_str = ",".join(str(i) for i in machine_ids)
        where += f" AND machine_id IN ({ids_str})"

    rows = client.execute(f"""
        SELECT
            program_name,
            COUNT(*) as launches_count,
            SUM(cash_amount + card_amount + cloud_amount) as total_revenue,
            AVG(cash_amount + card_amount + cloud_amount) as avg_price
        FROM program_launches
        WHERE {where}
        GROUP BY program_name
        ORDER BY launches_count DESC
    """)
    client.disconnect()


    return [
        {
            "program_name": r[0],
            "launches_count": r[1],
            "total_revenue": round(r[2], 2),
            "avg_price": round(r[3], 2),
        }
        for r in rows
    ]

