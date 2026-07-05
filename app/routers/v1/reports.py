from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.db.clickhouse import get_clickhouse
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

router = APIRouter(prefix="/reports", tags=["reports"])


def get_default_period():
    now = datetime.now()
    start = now.replace(day=1).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    return start, end


@router.get("/excel", summary="Финансовый отчёт в Excel из ClickHouse")
async def export_excel(
    machine_id: int,
    start: str = None,
    end: str = None
):
    if not start or not end:
        start, end = get_default_period()

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
        FROM financial_report
        WHERE machine_id = {machine_id}
        AND report_date BETWEEN '{start}' AND '{end}'
        GROUP BY report_date
        ORDER BY report_date DESC
    """)

    client.disconnect()

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

    total_all = sum(r[1] for r in rows)
    total_cash = sum(r[2] for r in rows)
    total_cashless = sum(r[3] for r in rows)
    total_qr = sum(r[4] for r in rows)
    total_banknotes = sum(r[5] for r in rows)
    total_coins = sum(r[6] for r in rows)
    total_cpt = sum(r[7] for r in rows)
    total_mobile = sum(r[8] for r in rows)
    total_mobile_bonus = sum(r[9] for r in rows)

    ws.append([
        "Всего", total_all, total_cash, total_cashless, total_qr,
        total_banknotes, total_coins, total_cpt, total_mobile, total_mobile_bonus
    ])
    for cell in ws[2]:
        cell.font = Font(bold=True)

    for r in rows:
        date_str = r[0].strftime("%m-%d")
        ws.append([
            date_str, r[1], r[2], r[3], r[4],
            r[5], r[6], r[7], r[8], r[9]
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