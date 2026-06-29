from fastapi import APIRouter, Query
from app.db.clickhouse import get_clickhouse
from datetime import datetime, timedelta

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
            qr_amount,
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
                "qr_amount": r[7],
                "total_amount": r[8],
                "loyalty_msisdn": r[9],
                "event_date": r[10].isoformat() if r[10] else None,
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
            SUM(qr_amount) as qr_revenue,
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
                "qr_revenue": round(r[7], 2),
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