# все запросы к CrestWave

import httpx
import asyncio
from app.core.config import settings

HEADERS = {
    "X-Authorization": settings.CRESTWAVE_TOKEN,
    "Content-Type": "application/json"
}

TIMEOUT = httpx.Timeout(30.0)  # 30 секунд таймаут


async def _request_with_retry(method: str, url: str, retries: int = 8, **kwargs):
    """Запрос с автоматическим повтором при сетевых ошибках (DNS flapping в Docker на Windows)"""
    last_error = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.request(method, url, headers=HEADERS, **kwargs)
                return response.json()
        except httpx.ConnectError as e:
            last_error = e
            await asyncio.sleep(1.5 * (attempt + 1))
    raise last_error


async def get_machines():
    return await _request_with_retry(
        "GET", f"{settings.CRESTWAVE_BASE_URL}/washer/v1/machines"
    )


async def get_device_status(machine_id: int):
    return await _request_with_retry(
        "GET", f"{settings.CRESTWAVE_BASE_URL}/washer/v1/machine/{machine_id}/status"
    )


async def get_summary_report(serial: str, start: str, end: str):
    return await _request_with_retry(
        "GET", f"{settings.CRESTWAVE_BASE_URL}/api/v1/summary-reports/{serial}",
        params={"start": start, "end": end}
    )


async def get_program_launches(machine_id: int, date_from: str, date_to: str):
    return await _request_with_retry(
        "GET", f"{settings.CRESTWAVE_BASE_URL}/api/v1/machines/{machine_id}/programs/launches",
        params={"dateFrom": date_from, "dateTo": date_to}
    )


async def get_post_status(machine_id: int):
    return await _request_with_retry(
        "GET", f"{settings.CRESTWAVE_BASE_URL}/api/v1/machines/{machine_id}/get_post_status"
    )


async def get_events(machine_id: int, date_from: str, date_to: str):
    return await _request_with_retry(
        "GET", f"{settings.CRESTWAVE_BASE_URL}/api/v1/machines/{machine_id}/get_events",
        params={"dateFrom": date_from, "dateTo": date_to}
    )