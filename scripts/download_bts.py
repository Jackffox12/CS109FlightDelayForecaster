"""Download monthly On-Time Performance CSVs (2014-01 → 2024-12) from the U.S. BTS site in parallel.

The BTS site exposes zipped CSVs under URLs of the form:
https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_{year}_{month}.zip
where ``month`` is *not* zero-padded (January → ``1``).

This script streams each file with httpx, retries transient errors with an
exponential back-off, and shows progress via ``tqdm``. Already-downloaded files
are skipped. Output is saved under ``data/raw/`` relative to the project root.

Run:
    poetry run python scripts/download_bts.py
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path
from typing import Final, Iterable

import httpx
from tqdm.asyncio import tqdm_asyncio

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
START: Final[date] = date(2014, 1, 1)
END: Final[date] = date(2024, 12, 1)  # inclusive
BASE_URL: Final[str] = (
    "https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)"
)
DEST_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "raw"
CONCURRENT_CONNECTIONS: Final[int] = 8  # tune as needed
RETRIES: Final[int] = 3
TIMEOUT = httpx.Timeout(60.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def months_between(start: date, end: date) -> Iterable[tuple[int, int]]:
    """Yield ``(year, month)`` for every month between *start* and *end* (inclusive)."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        # increment month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1


def build_url(year: int, month: int) -> str:
    """Return BTS download URL for a given *year* and *month* (1-12)."""
    return f"{BASE_URL}_{year}_{month}.zip"


def build_path(year: int, month: int) -> Path:
    """Return local path for a given *year*/*month* download."""
    return DEST_DIR / f"on_time_performance_{year}_{month:02d}.zip"


async def download_single(
    semaphore: asyncio.Semaphore, client: httpx.AsyncClient, year: int, month: int
) -> None:
    """Download a single monthly file with retries."""
    url = build_url(year, month)
    dest = build_path(year, month)

    if dest.exists():
        return  # already downloaded

    async with semaphore:  # limit concurrency
        for attempt in range(1, RETRIES + 1):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                DEST_DIR.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                return  # success
            except Exception as exc:  # noqa: BLE001
                if attempt == RETRIES:
                    raise RuntimeError(f"Failed after {RETRIES} attempts: {url}") from exc
                await asyncio.sleep(2**attempt)  # exponential back-off


async def main() -> None:
    months = list(months_between(START, END))
    sem = asyncio.Semaphore(CONCURRENT_CONNECTIONS)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        tasks = [download_single(sem, client, y, m) for y, m in months]
        for f in tqdm_asyncio.as_completed(tasks, total=len(tasks)):
            try:
                await f
            except Exception as e:  # noqa: BLE001
                # tqdm eats exceptions without this; we still let it bubble up after logging
                print(e)
                raise


if __name__ == "__main__":
    asyncio.run(main()) 