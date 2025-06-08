"""Weather enrichment for historic flight data."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Set, Tuple

import duckdb

from ..realtime.noaa_gridpoint import NOAAError, get_gridpoint_weather

# Airport coordinates for major US airports (subset for weather lookups)
AIRPORT_COORDS = {
    "ATL": (33.6367, -84.4281),
    "LAX": (33.9425, -118.4081),
    "ORD": (41.9786, -87.9048),
    "DFW": (32.8968, -97.0380),
    "DEN": (39.8561, -104.6737),
    "JFK": (40.6413, -73.7781),
    "SFO": (37.6213, -122.3790),
    "LAS": (36.0840, -115.1537),
    "SEA": (47.4502, -122.3088),
    "CLT": (35.2144, -80.9473),
    "MIA": (25.7959, -80.2870),
    "PHX": (33.4343, -112.0112),
    "IAH": (29.9902, -95.3368),
    "MCO": (28.4312, -81.3081),
    "EWR": (40.6895, -74.1745),
    "MSP": (44.8848, -93.2223),
    "BOS": (42.3656, -71.0096),
    "DTW": (42.2162, -83.3554),
    "PHL": (39.8744, -75.2424),
    "LGA": (40.7769, -73.8740),
    "DCA": (38.8512, -77.0402),
    "IAD": (38.9531, -77.4565),
    "BWI": (39.1754, -76.6683),
    "MDW": (41.7868, -87.7522),
    "SLC": (40.7899, -111.9791),
    "PDX": (45.5898, -122.5951),
    "SAN": (32.7338, -117.1933),
    "TPA": (27.9755, -82.5332),
    "STL": (38.7487, -90.3700),
    "CVG": (39.0488, -84.6678),
    "CMH": (39.9980, -82.8919),
    "IND": (39.7173, -86.2944),
    "MKE": (42.9472, -87.8966),
    "MSY": (29.9934, -90.2581),
    "AUS": (30.1975, -97.6664),
    "SAT": (29.5337, -98.4698),
    "MCI": (39.2976, -94.7139),
    "OMA": (41.3032, -95.8941),
    "TUL": (36.1984, -95.8881),
    "OKC": (35.3931, -97.6007),
    "ABQ": (35.0402, -106.6091),
    "RNO": (39.4991, -119.7688),
    "BOI": (43.5644, -116.2228),
    "ANC": (61.1744, -149.996),
    "HNL": (21.3099, -157.8581),
}

DEFAULT_DB = Path("data/flights.duckdb")


def _create_weather_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create historic_weather table."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS historic_weather (
            airport VARCHAR,
            date DATE,
            hour INTEGER,
            temp_c REAL,
            wind_kt REAL,
            precip_mm REAL,
            conditions VARCHAR,
            valid_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (airport, date, hour)
        )
    """
    )


def _get_unique_airport_times(
    conn: duckdb.DuckDBPyConnection, start_year: int, end_year: int
) -> Set[Tuple[str, str, int]]:
    """Get unique (airport, date, hour) combinations for weather lookups."""
    query = """
        SELECT DISTINCT origin as airport, 
               flight_date::DATE as date,
               dep_hour as hour
        FROM historic_flights 
        WHERE strftime('%Y', flight_date)::INTEGER >= ? 
          AND strftime('%Y', flight_date)::INTEGER <= ?
          AND origin IN ({})
          AND dep_hour IS NOT NULL
    """.format(
        ",".join(f"'{airport}'" for airport in AIRPORT_COORDS.keys())
    )

    results = conn.execute(query, (start_year, end_year)).fetchall()
    return {(airport, date_str, hour) for airport, date_str, hour in results}


async def _fetch_weather_batch(
    airport_times: list[Tuple[str, str, int]], conn: duckdb.DuckDBPyConnection
) -> int:
    """Fetch weather data for a batch of airport/time combinations."""
    success_count = 0

    for airport, date_str, hour in airport_times:
        if airport not in AIRPORT_COORDS:
            continue

        # Check if we already have weather for this combination
        existing = conn.execute(
            "SELECT 1 FROM historic_weather WHERE airport = ? AND date = ? AND hour = ?",
            (airport, date_str, hour),
        ).fetchone()

        if existing:
            success_count += 1
            continue

        try:
            lat, lng = AIRPORT_COORDS[airport]

            # Create target datetime (assume local time = UTC for simplicity)
            target_dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:00:00+00:00")

            weather = await get_gridpoint_weather(lat, lng, target_dt)

            # Insert weather data
            conn.execute(
                """
                INSERT OR REPLACE INTO historic_weather 
                (airport, date, hour, temp_c, wind_kt, precip_mm, conditions, valid_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    airport,
                    date_str,
                    hour,
                    weather["temp_c"],
                    weather["wind_kt"],
                    weather["precip_mm"],
                    weather["conditions"],
                    weather["valid_time"],
                ),
            )

            success_count += 1

            # Small delay to be respectful to NWS API
            await asyncio.sleep(0.1)

        except (NOAAError, Exception) as e:
            print(
                f"⚠️  Failed to get weather for {airport} {date_str} {hour:02d}:00: {e}"
            )

            # Insert null record to avoid retry
            conn.execute(
                """
                INSERT OR REPLACE INTO historic_weather 
                (airport, date, hour, temp_c, wind_kt, precip_mm, conditions, valid_time)
                VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL)
            """,
                (airport, date_str, hour),
            )

    return success_count


async def _enrich_weather_async(start_year: int, end_year: int, db_path: Path) -> float:
    """Async implementation of weather enrichment."""
    with duckdb.connect(str(db_path)) as conn:
        _create_weather_table(conn)

        # Get all unique airport/time combinations
        print(
            f"🔍 Finding unique airport/time combinations for {start_year}-{end_year}..."
        )
        airport_times = _get_unique_airport_times(conn, start_year, end_year)
        total_combinations = len(airport_times)

        if total_combinations == 0:
            print("❌ No flight data found for specified years")
            return 0.0

        print(f"📊 Found {total_combinations:,} unique airport/time combinations")

        # Process in batches to avoid overwhelming the API
        batch_size = 50
        total_success = 0

        airport_times_list = list(airport_times)
        for i in range(0, len(airport_times_list), batch_size):
            batch = airport_times_list[i : i + batch_size]
            batch_success = await _fetch_weather_batch(batch, conn)
            total_success += batch_success

            print(
                f"🔄 Processed {min(i + batch_size, len(airport_times_list)):,}/{len(airport_times_list):,} combinations"
            )

        # Calculate coverage
        coverage_pct = (total_success / total_combinations) * 100
        print(
            f"✅ Weather enrichment complete: {total_success:,}/{total_combinations:,} ({coverage_pct:.1f}%)"
        )

        return coverage_pct


def enrich_historic_weather(
    start_year: int, end_year: int, db_path: Path | str = DEFAULT_DB
) -> float:
    """Enrich historic flights with weather data.

    Returns the percentage of flights with weather data available.
    """
    db_path = Path(db_path)

    if not db_path.exists():
        raise ValueError(f"Database file does not exist: {db_path}")

    return asyncio.run(_enrich_weather_async(start_year, end_year, db_path))
