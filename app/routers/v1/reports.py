from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.clickhouse import get_clickhouse, save_financial_report
from app.db.postgres import get_db
from app.models.transaction import Transaction
from app.services.crestwave import get_machines, get_summary_report
from datetime import datetime, date as date_type
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

router = APIRouter(prefix="/reports", tags=["reports"])


def get_default_period():
    now = datetime.now()
    start = now.replace(day=1).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    return start, end


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


@router.get("/excel", summary="Финансовый отчёт в Excel (терминал + мобильное приложение)")
async def export_excel(
    machine_id: int,
    start: str = None,
    end: str = None,
    db: AsyncSession = Depends(get_db)
):
    if not start or not end:
        start, end = get_default_period()

    start = start[:10]
    end = end[:10]

    # принудительно обновить данные за сегодня перед формированием отчёта
    today = datetime.now().strftime("%Y-%m-%d")
    if end >= today:
        machines_data = await get_machines()
        machine = next((m for m in machines_data.get("machines", []) if m["id"] == machine_id), None)
        if machine:
            today_start = f"{today}T00:00:00"
            today_end = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            report = await get_summary_report(machine["serial"], today_start, today_end)
            save_financial_report(machine_id, machine["name"], report)

    # данные терминала из ClickHouse
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

    # данные мобильного приложения из PostgreSQL
    app_payments = await get_app_payments_by_day(db, machine_id, start, end)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"

    headers = [
        "Дата", "Общая сумма", "Наличные", "Безналичные", "Оплата по QR",
        "Банкнотами", "Монетами", "Поступление с ЦПТ",
        "Мобильное приложение (всего)", "Мобильное приложение (бонусы)"
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2E86AB")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    combined_rows = []
    for r in rows:
        date_str = r[0].strftime("%Y-%m-%d")
        app_amount = app_payments.get(date_str, 0)
        combined_rows.append({
            "date": r[0].strftime("%m-%d"),
            "cash": r[2],
            "cashless": r[3],
            "qr": r[4],
            "banknotes": r[5],
            "coins": r[6],
            "cpt": r[7],
            "mobile_total": r[8] + app_amount,
            "mobile_bonus": r[9],
            "total": r[1] + app_amount,
        })

    total_all = sum(row["total"] for row in combined_rows)
    total_cash = sum(row["cash"] for row in combined_rows)
    total_cashless = sum(row["cashless"] for row in combined_rows)
    total_qr = sum(row["qr"] for row in combined_rows)
    total_banknotes = sum(row["banknotes"] for row in combined_rows)
    total_coins = sum(row["coins"] for row in combined_rows)
    total_cpt = sum(row["cpt"] for row in combined_rows)
    total_mobile = sum(row["mobile_total"] for row in combined_rows)
    total_mobile_bonus = sum(row["mobile_bonus"] for row in combined_rows)

    ws.append([
        "Всего", total_all, total_cash, total_cashless, total_qr,
        total_banknotes, total_coins, total_cpt, total_mobile, total_mobile_bonus
    ])
    for cell in ws[2]:
        cell.font = Font(bold=True)

    for row in combined_rows:
        ws.append([
            row["date"], row["total"], row["cash"], row["cashless"], row["qr"],
            row["banknotes"], row["coins"], row["cpt"], row["mobile_total"], row["mobile_bonus"]
        ])

    ws.column_dimensions["A"].width = 12
    for col in "BCDEFGHIJ":
        ws.column_dimensions[col].width = 16

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"report_{machine_id}_{start}_{end}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )