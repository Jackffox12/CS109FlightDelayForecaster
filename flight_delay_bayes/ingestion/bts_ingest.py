"""BTS flight data ingestion from Kaggle dataset."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Iterator

import duckdb
import kaggle
import pandas as pd
from tqdm import tqdm

from flight_delay_bayes.bayes.updater import BetaBinomialModel

# Required columns from the BTS dataset
REQUIRED_COLUMNS = [
    "FL_DATE",
    "OP_UNIQUE_CARRIER", 
    "ORIGIN",
    "DEST",
    "CRS_DEP_TIME",
    "DEP_DEL15",
    "CANCELLED",
]

# Kaggle dataset identifier
KAGGLE_DATASET = "patrickzel/flight-delay-and-cancellation-dataset-2019-2023"


def check_kaggle_credentials() -> None:
    """Check if Kaggle API credentials are available."""
    username = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    
    if not username or not key:
        raise ValueError(
            "Kaggle credentials not found. Please set KAGGLE_USERNAME and KAGGLE_KEY "
            "environment variables, or configure them via `kaggle configure`."
        )


def download_kaggle_dataset(download_dir: Path) -> Path:
    """Download the flight dataset from Kaggle.
    
    Args:
        download_dir: Directory to download and extract files to
        
    Returns:
        Path to the extracted dataset directory
    """
    check_kaggle_credentials()
    
    download_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading {KAGGLE_DATASET} to {download_dir}")
    kaggle.api.dataset_download_files(
        KAGGLE_DATASET,
        path=str(download_dir),
        unzip=True
    )
    
    return download_dir


def process_csv_chunk(df_chunk: pd.DataFrame) -> pd.DataFrame:
    """Process a chunk of the CSV data with required transformations.
    
    Args:
        df_chunk: Raw DataFrame chunk from CSV
        
    Returns:
        Processed DataFrame with transformed columns
    """
    # Filter to only required columns if they exist
    available_cols = [col for col in REQUIRED_COLUMNS if col in df_chunk.columns]
    df = df_chunk[available_cols].copy()
    
    # Parse FL_DATE to date
    df["FL_DATE"] = pd.to_datetime(df["FL_DATE"], errors="coerce")
    
    # Convert CRS_DEP_TIME to hour bucket (floor(time/100))
    df["CRS_DEP_TIME"] = pd.to_numeric(df["CRS_DEP_TIME"], errors="coerce")
    df["dep_hour"] = (df["CRS_DEP_TIME"] // 100).astype("Int64")
    
    # Define "late" as (DEP_DEL15 == 1) & (CANCELLED == 0)
    df["DEP_DEL15"] = pd.to_numeric(df["DEP_DEL15"], errors="coerce")
    df["CANCELLED"] = pd.to_numeric(df["CANCELLED"], errors="coerce")
    df["late"] = (df["DEP_DEL15"] == 1) & (df["CANCELLED"] == 0)
    
    # Rename columns to match schema
    df = df.rename(columns={
        "FL_DATE": "flight_date",
        "OP_UNIQUE_CARRIER": "carrier",
        "ORIGIN": "origin", 
        "DEST": "dest",
    })
    
    # Select final columns
    result = df[["flight_date", "carrier", "origin", "dest", "dep_hour", "late"]]
    
    # Drop rows with missing critical data
    result = result.dropna(subset=["flight_date", "carrier", "origin", "dest"])
    
    return result


def create_historic_flights_table(db_path: Path) -> None:
    """Create the historic_flights table with proper schema.
    
    Args:
        db_path: Path to the DuckDB database file
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historic_flights (
                flight_date DATE,
                carrier VARCHAR,
                origin VARCHAR,
                dest VARCHAR, 
                dep_hour INTEGER,
                late BOOLEAN
            )
        """)


def load_csv_files(csv_dir: Path, db_path: Path, chunk_size: int = 10000) -> int:
    """Load CSV files from directory into DuckDB.
    
    Args:
        csv_dir: Directory containing CSV files
        db_path: Path to DuckDB database
        chunk_size: Number of rows to process at once
        
    Returns:
        Total number of rows processed
    """
    create_historic_flights_table(db_path)
    
    csv_files = list(csv_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in {csv_dir}")
    
    total_rows = 0
    
    with duckdb.connect(str(db_path)) as conn:
        for csv_file in csv_files:
            print(f"Processing {csv_file.name}")
            
            # Get total lines for progress bar
            total_lines = sum(1 for _ in open(csv_file, "r")) - 1  # Subtract header
            
            with tqdm(total=total_lines, desc=f"Loading {csv_file.name}") as pbar:
                for chunk in pd.read_csv(csv_file, chunksize=chunk_size):
                    processed_chunk = process_csv_chunk(chunk)
                    
                    if not processed_chunk.empty:
                        conn.execute(
                            "INSERT INTO historic_flights SELECT * FROM processed_chunk"
                        )
                        total_rows += len(processed_chunk)
                    
                    pbar.update(len(chunk))
    
    return total_rows


def ingest_historic_data(csv_dir: Path | str, db_path: Path | str) -> int:
    """Main function to ingest historic flight data.
    
    Args:
        csv_dir: Directory containing CSV files
        db_path: Path to DuckDB database
        
    Returns:
        Number of rows inserted
    """
    csv_dir = Path(csv_dir)
    db_path = Path(db_path)
    
    if not csv_dir.exists():
        raise ValueError(f"CSV directory does not exist: {csv_dir}")
    
    total_rows = load_csv_files(csv_dir, db_path)
    
    print(f"Wrote {total_rows:,} rows to {db_path}:historic_flights")
    return total_rows


m = BetaBinomialModel(0.5, 0.5)
print(m)                       # BetaBinomialModel(alpha=0.500, beta=0.500)
m.update(1)                    # observe late
print(m.predictive_p_on_time())
print(m.predictive_cdf(k=2, n=10)) 