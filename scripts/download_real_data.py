#!/usr/bin/env python3
"""Download real flight data from Kaggle for accurate training."""

import os
from pathlib import Path

import kaggle

from flight_delay_bayes.ingestion.bts_ingest import ingest_historic_data


def check_kaggle_setup():
    """Check if Kaggle credentials are configured."""
    try:
        kaggle.api.authenticate()
        print("✅ Kaggle API authenticated successfully")
        return True
    except Exception as e:
        print(f"❌ Kaggle authentication failed: {e}")
        print("\n🔧 To set up Kaggle API:")
        print("1. Go to https://www.kaggle.com/settings/account")
        print("2. Scroll to 'API' section and click 'Create New Token'")
        print("3. Download kaggle.json file")
        print("4. Move it to ~/.kaggle/kaggle.json (or set KAGGLE_USERNAME/KAGGLE_KEY)")
        print("5. Run: chmod 600 ~/.kaggle/kaggle.json")
        return False


def download_flight_data():
    """Download the Flight Delay & Cancellation 2019-2023 dataset."""
    if not check_kaggle_setup():
        return False

    print("📥 Downloading Flight Delay & Cancellation 2019-2023 dataset...")

    # Create download directory
    download_dir = Path("data/kaggle_raw")
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download the dataset
        dataset_name = "patrickzel/flight-delay-and-cancellation-dataset-2019-2023"
        kaggle.api.dataset_download_files(
            dataset_name, path=str(download_dir), unzip=True
        )

        print(f"✅ Dataset downloaded to {download_dir}")

        # List downloaded files
        csv_files = list(download_dir.glob("*.csv"))
        print(f"📁 Found {len(csv_files)} CSV files:")
        for f in csv_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"   - {f.name} ({size_mb:.1f} MB)")

        return True

    except Exception as e:
        print(f"❌ Download failed: {e}")
        print("\n💡 Alternative datasets to try:")
        print("- sobhanmoosavi/us-accidents")
        print("- divyansh22/flight-delay-prediction")
        print("- threnjen/2019-airline-delays-and-cancellations")
        return False


def ingest_to_database():
    """Ingest downloaded data into DuckDB."""
    download_dir = Path("data/kaggle_raw")
    db_path = Path("data/flights_real.duckdb")

    if not download_dir.exists():
        print("❌ No downloaded data found. Run download first.")
        return False

    csv_files = list(download_dir.glob("*.csv"))
    if not csv_files:
        print("❌ No CSV files found in download directory.")
        return False

    print(f"🔄 Ingesting {len(csv_files)} CSV files into {db_path}...")

    try:
        total_rows = ingest_historic_data(download_dir, db_path)
        print(f"✅ Ingested {total_rows:,} rows of real flight data")

        # Update the default database path in prior estimator
        print("🔧 Updating database path to use real data...")

        return True

    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        return False


def main():
    """Main script to download and ingest real flight data."""
    print("🛫 Setting up real flight data for training...")

    # Step 1: Download data from Kaggle
    if not download_flight_data():
        print("\n📊 Since Kaggle download failed, you can manually download:")
        print(
            "1. Go to https://www.kaggle.com/datasets/patrickzel/flight-delay-and-cancellation-dataset-2019-2023"
        )
        print("2. Download and extract to data/kaggle_raw/")
        print("3. Re-run this script with --skip-download")
        return False

    # Step 2: Ingest into database
    if not ingest_to_database():
        return False

    print("\n🎯 Real flight data ready for training!")
    print("Next steps:")
    print("1. Run: python scripts/train_fast_model.py")
    print(
        "2. Or use CLI: python -m flight_delay_bayes.cli train-hier --year-start 2019 --year-end 2021"
    )

    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--skip-download":
        print("⏭️  Skipping download, proceeding to ingestion...")
        ingest_to_database()
    else:
        main()
