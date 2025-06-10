#!/usr/bin/env python3
"""Ingest the specific Kaggle flight delay dataset into DuckDB."""

from pathlib import Path

import duckdb
import pandas as pd
from tqdm import tqdm


def create_flights_table(db_path: Path):
    """Create the flights table with the correct schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            DROP TABLE IF EXISTS historic_flights
        """
        )
        conn.execute(
            """
            CREATE TABLE historic_flights (
                flight_date DATE,
                carrier VARCHAR,
                origin VARCHAR,
                dest VARCHAR,
                dep_hour INTEGER,
                dep_delay_minutes REAL,
                late BOOLEAN
            )
        """
        )


def process_kaggle_data(csv_path: Path, db_path: Path, chunk_size: int = 10000):
    """Process the Kaggle dataset and insert into DuckDB."""
    print(f"🔄 Processing {csv_path.name}...")

    create_flights_table(db_path)

    # Get total lines for progress bar
    print("📊 Counting total rows...")
    total_lines = sum(1 for _ in open(csv_path, "r")) - 1  # Subtract header
    print(f"   Total rows: {total_lines:,}")

    processed_rows = 0

    with duckdb.connect(str(db_path)) as conn:
        # Process in chunks
        chunk_iter = pd.read_csv(csv_path, chunksize=chunk_size)

        with tqdm(total=total_lines, desc="Ingesting") as pbar:
            for chunk in chunk_iter:
                # Clean and transform the chunk
                processed_chunk = process_chunk(chunk)

                if not processed_chunk.empty:
                    # Insert into database
                    conn.execute(
                        "INSERT INTO historic_flights SELECT * FROM processed_chunk"
                    )
                    processed_rows += len(processed_chunk)

                pbar.update(len(chunk))

    print(f"✅ Processed {processed_rows:,} valid flight records")
    return processed_rows


def process_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and transform a chunk of the Kaggle data."""
    # Select and rename relevant columns
    columns_map = {
        "FL_DATE": "flight_date",
        "AIRLINE": "carrier",
        "ORIGIN": "origin",
        "DEST": "dest",
        "CRS_DEP_TIME": "crs_dep_time",
        "DEP_DELAY": "dep_delay_minutes",
        "CANCELLED": "cancelled",
    }

    # Filter to only columns we have
    available_cols = [col for col in columns_map.keys() if col in df.columns]
    chunk = df[available_cols].copy()

    # Rename columns
    chunk = chunk.rename(columns=columns_map)

    # Clean data
    chunk["flight_date"] = pd.to_datetime(chunk["flight_date"], errors="coerce")
    chunk["crs_dep_time"] = pd.to_numeric(chunk["crs_dep_time"], errors="coerce")
    chunk["dep_delay_minutes"] = pd.to_numeric(
        chunk["dep_delay_minutes"], errors="coerce"
    )
    chunk["cancelled"] = pd.to_numeric(chunk["cancelled"], errors="coerce").fillna(0)

    # Create dep_hour from scheduled departure time
    chunk["dep_hour"] = (chunk["crs_dep_time"] // 100).astype("Int64")

    # Create 'late' flag (>= 15 minutes delay AND not cancelled)
    chunk["late"] = (chunk["dep_delay_minutes"] >= 15) & (chunk["cancelled"] == 0)

    # Select final columns (matching the table schema exactly)
    result = chunk[
        [
            "flight_date",
            "carrier",
            "origin",
            "dest",
            "dep_hour",
            "dep_delay_minutes",
            "late",
        ]
    ]

    # Drop rows with missing critical data
    result = result.dropna(
        subset=["flight_date", "carrier", "origin", "dest", "dep_hour"]
    )

    # Filter out extreme outliers and invalid data
    result = result[
        (result["dep_hour"] >= 0)
        & (result["dep_hour"] <= 23)
        & (result["dep_delay_minutes"] >= -60)
        & (result["dep_delay_minutes"] <= 300)
    ]

    return result


def main():
    """Main ingestion process."""
    csv_path = Path("data/kaggle_raw/flights_sample_3m.csv")
    db_path = Path("data/flights_real.duckdb")

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        print("🔧 Run: python scripts/download_real_data.py")
        return

    print("🛫 Ingesting Real Kaggle Flight Data")
    print("=" * 50)
    print(f"📁 Source: {csv_path}")
    print(f"💾 Target: {db_path}")

    # Process the data
    total_rows = process_kaggle_data(csv_path, db_path, chunk_size=50000)

    # Verify the result
    with duckdb.connect(str(db_path)) as conn:
        # Basic stats
        stats = conn.execute(
            """
            SELECT 
                COUNT(*) as total_flights,
                COUNT(DISTINCT carrier) as carriers,
                COUNT(DISTINCT origin) as origins,
                COUNT(DISTINCT dest) as destinations,
                AVG(CASE WHEN late THEN 1.0 ELSE 0.0 END) as delay_rate,
                MIN(flight_date) as min_date,
                MAX(flight_date) as max_date
            FROM historic_flights
        """
        ).fetchone()

        print("\n📈 Database Summary:")
        print(f"   Total flights: {stats[0]:,}")
        print(f"   Carriers: {stats[1]}")
        print(f"   Origin airports: {stats[2]}")
        print(f"   Destination airports: {stats[3]}")
        print(f"   Delay rate: {stats[4]:.1%}")
        print(f"   Date range: {stats[5]} to {stats[6]}")

        # Top carriers
        print("\n🏢 Top carriers:")
        carriers = conn.execute(
            """
            SELECT carrier, COUNT(*) as flights, 
                   AVG(CASE WHEN late THEN 1.0 ELSE 0.0 END) as delay_rate
            FROM historic_flights 
            GROUP BY carrier 
            ORDER BY flights DESC 
            LIMIT 8
        """
        ).fetchall()

        for carrier, flights, delay_rate in carriers:
            print(f"   {carrier}: {flights:,} flights ({delay_rate:.1%} delay rate)")

    print("\n✅ Real flight data ready for training!")
    print("📊 Run: python scripts/train_fast_model.py")


if __name__ == "__main__":
    main()
