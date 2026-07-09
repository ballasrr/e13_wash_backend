from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.services.reports import build_report_data
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


@router.get("/preview", summary="Предпросмотр отчёта для фронта")
async def preview_report(
    machine_id: int,
    start: str = None,
    end: str = None,
    db: AsyncSession = Depends(get_db)
):
    if not start or not end:
        start, end = get_default_period()
    start = start[:10]
    end = end[:10]

    totals, days = await build_report_data(db, machine_id, start, end, refresh_today=True)

    return {
        "period": {"start": start, "end": end},
        "totals": totals,
        "days": days
    }


@router.get("/excel", summary="Скачать финансовый отчёт в Excel")
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

    totals, days = await build_report_data(db, machine_id, start, end, refresh_today=True)

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

    ws.append([
        "Всего", totals["total"], totals["cash"], totals["cashless"], totals["qr"],
        totals["banknotes"], totals["coins"], totals["cpt"], totals["mobile_app"], totals["mobile_bonus"]
    ])
    for cell in ws[2]:
        cell.font = Font(bold=True)

    for d in days:
        date_short = d["date"][5:]
        ws.append([
            date_short, d["total"], d["cash"], d["cashless"], d["qr"],
            d["banknotes"], d["coins"], d["cpt"], d["mobile_app"], d["mobile_bonus"]
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