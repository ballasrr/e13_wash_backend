from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.clickhouse import get_clickhouse, save_financial_report
from app.models.transaction import Transaction
from app.services.crestwave import get_machines, get_summary_report
from datetime import datetime


async def get_app_payments_by_day(db: AsyncSession, machine_id: int, start: str, end: str):
    """Получить суммы оплат через мобильное приложение по дням из PostgreSQL"""
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()

    result = await db.execute(
        select(
            func.date(Transaction.paid_at).label("day"),
            func.sum(Transaction.paid_amount).label("total")
        )
        .where(
            Transaction.machine_id == machine_id,
            Transaction.status.in_(["paid", "machine_started"]),
            func.date(Transaction.paid_at) >= start_date,
            func.date(Transaction.paid_at) <= end_date,
        )
        .group_by(func.date(Transaction.paid_at))
    )
    rows = result.all()
    return {row.day.strftime("%Y-%m-%d"): float(row.total or 0) for row in rows}


async def build_report_data(db: AsyncSession, machine_id: int, start: str, end: str, refresh_today: bool = False):
    """Собрать финансовый отчёт — терминал (ClickHouse) + мобильное приложение (Postgres)"""
    if refresh_today:
        today = datetime.now().strftime("%Y-%m-%d")
        if end >= today:
            machines_data = await get_machines()
            machine = next((m for m in machines_data.get("machines", []) if m["id"] == machine_id), None)
            if machine:
                today_start = f"{today}T00:00:00"
                today_end = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                report = await get_summary_report(machine["serial"], today_start, today_end)
                save_financial_report(machine_id, machine["name"], report)

    client = get_clickhouse()
    rows = client.execute(f"""
        SELECT
            report_date,
            SUM(total_amount) as total,
            SUM(cash) as cash,
            SUM(cashless) as cashless,
            SUM(qr) as qr,
            SUM(banknotes) as banknotes,
            SUM(coins) as coins,
            SUM(cpt_income) as cpt,
            SUM(mobile_app_total) as mobile_total,
            SUM(mobile_app_bonus) as mobile_bonus
        FROM financial_report FINAL
        WHERE machine_id = {machine_id}
        AND report_date BETWEEN '{start}' AND '{end}'
        GROUP BY report_date
        ORDER BY report_date DESC
    """)
    client.disconnect()

    app_payments = await get_app_payments_by_day(db, machine_id, start, end)

    days = []
    for r in rows:
        date_str = r[0].strftime("%Y-%m-%d")
        app_amount = app_payments.get(date_str, 0)
        days.append({
            "date": date_str,
            "cash": r[2],
            "cashless": r[3],
            "qr": r[4],
            "banknotes": r[5],
            "coins": r[6],
            "cpt": r[7],
            "mobile_app": r[8] + app_amount,
            "mobile_bonus": r[9],
            "total": r[1] + app_amount,
        })

    totals = {
        "total": sum(d["total"] for d in days),
        "cash": sum(d["cash"] for d in days),
        "cashless": sum(d["cashless"] for d in days),
        "qr": sum(d["qr"] for d in days),
        "banknotes": sum(d["banknotes"] for d in days),
        "coins": sum(d["coins"] for d in days),
        "cpt": sum(d["cpt"] for d in days),
        "mobile_app": sum(d["mobile_app"] for d in days),
        "mobile_bonus": sum(d["mobile_bonus"] for d in days),
    }

    return totals, days