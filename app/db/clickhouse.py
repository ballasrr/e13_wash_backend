from clickhouse_driver import Client
from app.core.config import settings
from datetime import datetime


def get_clickhouse():
    return Client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD
    )


def init_clickhouse():
    client = get_clickhouse()

    client.execute("""
        CREATE TABLE IF NOT EXISTS device_events (
            id UInt64,
            machine_id UInt32,
            machine_name String,
            description String,
            event_date DateTime,
            status String,
            event_type String,
            params String,
            session_id String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (machine_id, event_date)
    """)

    client.execute("""
        CREATE TABLE IF NOT EXISTS program_launches (
            machine_id UInt32,
            machine_name String,
            program_id String,
            program_name String,
            program_price Float64,
            cash_amount Float64,
            card_amount Float64,
            bonus_amount Float64,
            qr_amount Float64,
            total_amount Float64,
            loyalty_msisdn String,
            event_date DateTime,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (machine_id, event_date)
    """)

    client.disconnect()


def save_device_events(machine_id: int, machine_name: str, events: list):
    """Сохранить события устройства в ClickHouse"""
    if not events:
        return

    client = get_clickhouse()
    rows = []

    for event in events:
        try:
            event_date = datetime.fromisoformat(event.get("edat", "").replace("T", " "))
        except:
            event_date = datetime.now()

        rows.append((
            event.get("id", 0),
            machine_id,
            machine_name,
            event.get("description", ""),
            event_date,
            event.get("status", ""),
            event.get("type", ""),
            str(event.get("params", "")),
            str(event.get("session_id", "") or ""),
        ))

    client.execute("INSERT INTO device_events (id, machine_id, machine_name, description, event_date, status, event_type, params, session_id) VALUES", rows)
    client.disconnect()


def save_program_launches(machine_id: int, machine_name: str, launches: list):
    """Сохранить запуски программ в ClickHouse"""
    if not launches:
        return

    client = get_clickhouse()
    rows = []

    for launch in launches:
        details = launch.get("event_details", {})
        payment = launch.get("payment_type", {})

        try:
            event_date = datetime.fromisoformat(launch.get("event_date", "").replace("T", " "))
        except:
            event_date = datetime.now()

        rows.append((
            machine_id,
            machine_name,
            str(details.get("program_id", "")),
            details.get("program_name", ""),
            float(details.get("program_price", 0) or 0),
            float(payment.get("cash_payment_amt", 0) or 0),
            float(payment.get("card_payment_amt", 0) or 0),
            float(payment.get("bonus_account_amt", 0) or 0),
            float(payment.get("qr_payment_amt", 0) or 0),
            float(launch.get("payment_type_description", {}).get("total_amt", 0) or 0),
            details.get("loyalty_msisdn", "") or "",
            event_date,
        ))

    client.execute("INSERT INTO program_launches (machine_id, machine_name, program_id, program_name, program_price, cash_amount, card_amount, bonus_amount, qr_amount, total_amount, loyalty_msisdn, event_date) VALUES", rows)
    client.disconnect()