"""Retrieve the latest METAR observation for a given ICAO station."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Final

import httpx

__all__ = ["latest_metar"]

FEED_URL: Final[str] = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
TIMEOUT_S: Final[float] = 5.0
MAX_RETRIES: Final[int] = 3
BACKOFF: Final[float] = 1.5


class MetarError(RuntimeError):
    """Raised when METAR retrieval fails."""


async def _fetch_text_with_retry(url: str) -> str:  # noqa: D401
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        delay = 0.5
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                await asyncio.sleep(delay)
                delay *= BACKOFF
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except (httpx.HTTPError, httpx.TimeoutException):
                if attempt == MAX_RETRIES:
                    raise MetarError("Failed to fetch METAR after retries")
                continue


def _parse_metar_text(text: str) -> dict[str, Any]:  # noqa: D401
    """Very lightweight METAR parsing to extract basic fields."""
    lines = text.strip().splitlines()
    if len(lines) < 2:
        raise MetarError("Unexpected METAR format")

    obs_time_str = lines[0].strip()
    report = lines[1].strip()

    # Observation time format: YYYY/MM/DD HH:MM
    try:
        obs_dt = datetime.strptime(obs_time_str, "%Y/%m/%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise MetarError("Invalid observation time in METAR feed") from exc

    # Very naive parsing. Visibility in SM after first space number maybe optional; we'll look for 'KT' for wind, numbers before SM for visibility.
    visibility = None
    wind_speed = None
    wx_code = None

    tokens = report.split()
    for tok in tokens:
        if tok.endswith("SM") and len(tok) <= 5:
            # e.g., 10SM or 1/2SM
            visibility = tok
        elif tok.endswith("KT") and len(tok) >= 5:
            # wind group like 24015KT
            try:
                wind_speed = int(tok[-4:-2])
            except ValueError:
                pass
        elif tok in {"RA", "SN", "FG", "BR", "HZ", "TS"}:
            wx_code = tok

    return {
        "obs_time": obs_dt.isoformat(),
        "visibility": visibility,
        "wind_speed_kt": wind_speed,
        "wx_code": wx_code,
    }


async def _latest_metar_async(icao: str) -> dict[str, Any]:  # noqa: D401
    url = FEED_URL.format(icao=icao.upper())
    text = await _fetch_text_with_retry(url)
    return _parse_metar_text(text)


def latest_metar(icao: str) -> dict[str, Any]:  # noqa: D401
    """Return latest METAR observation for station ICAO.

    Synchronous wrapper around async implementation.
    """
    return asyncio.run(_latest_metar_async(icao)) 