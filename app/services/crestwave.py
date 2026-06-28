# все запросы к CrestWave 

import httpx
from app.core.config import settings

HEADERS = {
    "X-Authorization": settings.CRESTWAVE_TOKEN,
    "Content-Type": "application/json"
}


async def get_machines():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.CRESTWAVE_BASE_URL}/washer/v1/machines",
            headers=HEADERS
        )
        return response.json()


async def get_device_status(machine_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.CRESTWAVE_BASE_URL}/washer/v1/machine/{machine_id}/status",
            headers=HEADERS
        )
        return response.json()


async def get_summary_report(serial: str, start: str, end: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.CRESTWAVE_BASE_URL}/api/v1/summary-reports/{serial}",
            headers=HEADERS,
            params={"start": start, "end": end}
        )
        return response.json()


async def get_program_launches(machine_id: int, date_from: str, date_to: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.CRESTWAVE_BASE_URL}/api/v1/machines/{machine_id}/programs/launches",
            headers=HEADERS,
            params={"dateFrom": date_from, "dateTo": date_to}
        )
        return response.json()


async def get_post_status(machine_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.CRESTWAVE_BASE_URL}/api/v1/machines/{machine_id}/get_post_status",
            headers=HEADERS
        )
        return response.json()


async def get_events(machine_id: int, date_from: str, date_to: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.CRESTWAVE_BASE_URL}/api/v1/machines/{machine_id}/get_events",
            headers=HEADERS,
            params={"dateFrom": date_from, "dateTo": date_to}
        )
        return response.json()