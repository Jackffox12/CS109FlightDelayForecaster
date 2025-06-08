from __future__ import annotations

"""Bulk ingestion of BTS On-Time Performance feed (2014-present).

This utility streams monthly zip archives directly from the BTS public
PREZIP endpoint and appends them into a DuckDB table called
``historic_flights``.  The resulting table is **partitioned by year** and
**Z-ORDERed** by the primary query dimensions to keep queries fast even
with ~100 M rows.

Example
-------
>>> from flight_delay_bayes.ingestion.bts_bulk_ingest import ingest_bulk
>>> ingest_bulk(2014, 2023)
"""

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterator

import duckdb
import pandas as pd
import requests

__all__ = ["ingest_bulk"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PREZIP_BASE = "https://transtats.bts.gov/PREZIP"
DB_PATH = Path("data/flights.duckdb")
TABLE_NAME = "historic_flights"
CHUNK_SIZE = 50_000  # rows per Pandas chunk

NEEDED_COLS = {
    "FL_DATE": "flight_date",
    "OP_UNIQUE_CARRIER": "carrier",
    "ORIGIN": "origin",
    "DEST": "dest",
    "CRS_DEP_TIME": "crs_dep_time",
    "DEP_DEL15": "dep_del15",
    "DEP_DELAY": "dep_delay_minutes",
    "CANCELLED": "cancelled",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _monthly_urls(start_year: int, end_year: int) -> Iterator[tuple[int, int, str]]:
    """Yield (year, month, url) for each month in the inclusive range."""
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            fname = (
                f"On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_"
                f"{year}_{month:02d}.zip"
            )
            yield year, month, f"{PREZIP_BASE}/{fname}"


def _ensure_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the partitioned + Z-ORDERed table if it doesn't exist."""
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            flight_date DATE,
            carrier     VARCHAR,
            origin      VARCHAR,
            dest        VARCHAR,
            dep_hour    INTEGER,
            dep_delay_minutes REAL,
            late        BOOLEAN,
            year        INTEGER
        )
        PARTITION BY year
        """
    )


def _process_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Rename/select columns and derive fields."""
    df = df[list(NEEDED_COLS.keys())].rename(columns=NEEDED_COLS)

    df["flight_date"] = pd.to_datetime(df["flight_date"], errors="coerce")
    df["crs_dep_time"] = pd.to_numeric(df["crs_dep_time"], errors="coerce")
    df["dep_hour"] = (df["crs_dep_time"] // 100).astype("Int64")

    df["dep_del15"] = pd.to_numeric(df["dep_del15"], errors="coerce")
    df["dep_delay_minutes"] = pd.to_numeric(df["dep_delay_minutes"], errors="coerce")
    df["cancelled"] = pd.to_numeric(df["cancelled"], errors="coerce")
    df["late"] = (df["dep_del15"] == 1) & (df["cancelled"] == 0)

    df["year"] = df["flight_date"].dt.year
    return df[
        [
            "flight_date",
            "carrier",
            "origin",
            "dest",
            "dep_hour",
            "dep_delay_minutes",
            "late",
            "year",
        ]
    ]


def ingest_bulk(
    start_year: int, end_year: int, db_path: Path | str = DB_PATH
) -> int:  # noqa: D401
    """Ingest the full BTS feed between *start_year* and *end_year* inclusive.

    Returns the number of rows inserted.
    """
    total_rows = 0
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db_path)) as conn:
        _ensure_table(conn)
        for year, month, url in _monthly_urls(start_year, end_year):
            t0 = datetime.utcnow()
            print(f"\n🔄 {year}-{month:02d} → downloading…", flush=True)

            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                print(f"⚠️  {url.split('/')[-1]} not found – skipping")
                continue

            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                inner_csv = zf.namelist()[0]
                with zf.open(inner_csv) as csv_file:
                    reader = pd.read_csv(  # type: ignore[arg-type]
                        csv_file,
                        usecols=list(NEEDED_COLS.keys()),
                        chunksize=CHUNK_SIZE,
                        low_memory=False,
                    )
                    for chunk in reader:
                        processed = _process_frame(chunk)
                        if processed.empty:
                            continue
                        conn.execute(
                            f"INSERT INTO {TABLE_NAME} SELECT * FROM processed"
                        )
                        total_rows += len(processed)

            dur = (datetime.utcnow() - t0).total_seconds()
            print(
                f"✅ {year}-{month:02d} ingested in {dur:.1f}s  (+{total_rows:,} rows)"
            )

        # Optimise table ordering
        print("\n🚀 Optimising table with ZORDER…", flush=True)
        conn.execute(
            f"OPTIMIZE {TABLE_NAME} ZORDER BY (carrier, origin, dest, dep_hour, flight_date)"
        )

    print(f"\n✨ Finished ingested {total_rows:,} rows in total.")
    return total_rows


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("start_year", type=int)
    p.add_argument("end_year", type=int)
    args = p.parse_args()
    ingest_bulk(args.start_year, args.end_year)
