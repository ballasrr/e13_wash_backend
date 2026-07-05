from clickhouse_driver import Client
from app.core.config import settings
from datetime import datetime
import hashlib


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
        ) ENGINE = ReplacingMergeTree(created_at)
        ORDER BY (machine_id, event_date, id)
    """)

    client.execute("""
        CREATE TABLE IF NOT EXISTS program_launches (
            id String,
            machine_id UInt32,
            machine_name String,
            program_id String,
            program_name String,
            program_price Float64,
            cash_amount Float64,
            card_amount Float64,
            bonus_amount Float64,
            cloud_amount Float64,
            loyalty_card_amount Float64,
            total_amount Float64,
            loyalty_msisdn String,
            event_date DateTime,
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(created_at)
        ORDER BY (machine_id, event_date, id)
    """)

    client.execute("""
        CREATE TABLE IF NOT EXISTS financial_report (
            machine_id UInt32,
            machine_name String,
            report_date Date,
            total_amount Float64,
            cash Float64,
            cashless Float64,
            qr Float64,
            banknotes Float64,
            coins Float64,
            cpt_income Float64,
            mobile_app_total Float64,
            mobile_app_bonus Float64,
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(created_at)
        ORDER BY (machine_id, report_date)
    """)

    client.disconnect()


def save_device_events(machine_id: int, machine_name: str, events: list):
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

    client.execute(
        "INSERT INTO device_events (id, machine_id, machine_name, description, event_date, status, event_type, params, session_id) VALUES",
        rows
    )
    client.disconnect()


def save_program_launches(machine_id: int, machine_name: str, launches: list):
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

        loyalty_msisdn = details.get("loyalty_msisdn", "") or ""
        program_name = details.get("program_name", "")
        program_id = str(details.get("program_id", ""))
        cash_amount = float(payment.get("cash_payment_amt", 0) or 0)
        card_amount = float(payment.get("card_payment_amt", 0) or 0)
        bonus_amount = float(payment.get("bonus_account_amt", 0) or 0)
        cloud_amount = float(payment.get("cloud_amt", 0) or 0)
        loyalty_card_amount = float(payment.get("loyalty_card_amt", 0) or 0)
        total_amount = float(launch.get("payment_type_description", {}).get("total_amt", 0) or 0)

        raw_key = f"{machine_id}|{event_date}|{program_id}|{program_name}|{total_amount}|{loyalty_msisdn}|{cash_amount}|{card_amount}"
        unique_id = hashlib.md5(raw_key.encode()).hexdigest()

        rows.append((
            unique_id,
            machine_id,
            machine_name,
            program_id,
            program_name,
            float(details.get("program_price", 0) or 0),
            cash_amount,
            card_amount,
            bonus_amount,
            cloud_amount,
            loyalty_card_amount,
            total_amount,
            loyalty_msisdn,
            event_date,
        ))

    client.execute(
        "INSERT INTO program_launches (id, machine_id, machine_name, program_id, program_name, program_price, cash_amount, card_amount, bonus_amount, cloud_amount, loyalty_card_amount, total_amount, loyalty_msisdn, event_date) VALUES",
        rows
    )
    client.disconnect()


def save_financial_report(machine_id: int, machine_name: str, report: list):
    """Сохранить финансовый отчёт по дням с полной разбивкой оплат"""
    if not report or not isinstance(report, list):
        return

    daily = {}
    for item in report:
        date_str = item.get("date")
        report_type = item.get("washerReportType")
        amount = item.get("amount", 0) or 0

        if not date_str:
            continue

        # берём только дату YYYY-MM-DD, отбрасывая время
        day_key = date_str[:10]

        if day_key not in daily:
            daily[day_key] = {}

        daily[day_key][report_type] = daily[day_key].get(report_type, 0) + amount

    if not daily:
        return

    client = get_clickhouse()
    rows = []

    for date_str, types in daily.items():
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        cash = types.get("cash", 0)
        cashless = types.get("cashless", 0)
        qr = types.get("qr", 0)
        banknotes = types.get("banknotes", cash)
        coins = types.get("coins", 0)
        cpt_income = types.get("cpt", 0)
        mobile_app_total = types.get("mobileApp", 0)
        mobile_app_bonus = types.get("mobileAppBonus", 0)
        total = cash + cashless + qr + mobile_app_total

        rows.append((
            machine_id,
            machine_name,
            report_date,
            total,
            cash,
            cashless,
            qr,
            banknotes,
            coins,
            cpt_income,
            mobile_app_total,
            mobile_app_bonus,
        ))

    client.execute(
        "INSERT INTO financial_report (machine_id, machine_name, report_date, total_amount, cash, cashless, qr, banknotes, coins, cpt_income, mobile_app_total, mobile_app_bonus) VALUES",
        rows
    )
    client.disconnect()