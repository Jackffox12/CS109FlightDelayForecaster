"""Realtime flight status retrieval via the Aviationstack API."""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any, Final

import httpx
from dotenv import load_dotenv

__all__ = ["get_flight_status"]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL: Final[str] = "https://api.aviationstack.com/v1/flights"
TIMEOUT_S: Final[float] = 5.0
MAX_RETRIES: Final[int] = 3
BACKOFF: Final[float] = 1.5  # multiplier for exponential back-off

load_dotenv()


class AviationstackError(RuntimeError):
    """Raised when a call to Aviationstack fails after retries."""


async def _fetch_with_retry(url: str, params: dict[str, Any]) -> httpx.Response:  # noqa: D401
    """Perform GET with simple exponential back-off retries."""
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        delay = 0.5
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                await asyncio.sleep(delay)
                delay *= BACKOFF
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp
            except (httpx.HTTPError, httpx.TimeoutException):
                if attempt == MAX_RETRIES:
                    raise AviationstackError("Aviationstack API request failed after retries")
                continue


async def _get_status_async(
    carrier_code: str, flight_number: str, dep_date: date
) -> dict[str, Any]:  # noqa: D401
    key = os.getenv("AVIATIONSTACK_KEY")
    if not key:
        raise RuntimeError("AVIATIONSTACK_KEY environment variable not set. See .env.example.")

    params: dict[str, Any] = {
        "access_key": key,
        "flight_date": dep_date.isoformat(),
        "airline_iata": carrier_code,
        "flight_number": flight_number,
    }

    resp = await _fetch_with_retry(API_URL, params)
    data = resp.json()

    if "data" not in data or not data["data"]:
        raise AviationstackError("No data returned from Aviationstack API.")

    flight_info = data["data"][0]  # take first match
    result = {
        "scheduled_dep": flight_info.get("departure", {}).get("scheduled"),
        "gate": flight_info.get("departure", {}).get("gate"),
        "status": flight_info.get("flight_status"),
        "delay_minutes": flight_info.get("departure", {}).get("delay"),
    }
    return result


def get_flight_status(carrier_code: str, flight_number: str, dep_date: date) -> dict[str, Any]:  # noqa: D401
    """Return current flight status information from Aviationstack.

    This is a thin synchronous wrapper around an async HTTP call for ease of
    use from synchronous code paths.
    """
    return asyncio.run(_get_status_async(carrier_code, flight_number, dep_date)) 