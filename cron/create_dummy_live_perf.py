"""Creates a dummy live_perf.parquet file for testing purposes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
PERF_FILE = DATA_DIR / "live_perf.parquet"


def create_dummy_data():
    """Generates dummy data with a specific Brier score."""
    DATA_DIR.mkdir(exist_ok=True)
    np.random.seed(42)

    # Generate 30 samples within the last 7 days
    n_recent = 30
    recent_timestamps = [
        datetime.now(timezone.utc) - timedelta(hours=i * 4) for i in range(n_recent)
    ]

    # Generate 170 older samples
    n_old = 170
    old_timestamps = [
        datetime.now(timezone.utc) - timedelta(days=8) - timedelta(hours=i * 12)
        for i in range(n_old)
    ]

    timestamps = recent_timestamps + old_timestamps
    n_samples = len(timestamps)

    # Create data that results in a Brier score of ~0.141 for the recent data
    y_true = np.random.choice([True, False], n_samples, p=[0.25, 0.75])

    # Make recent predictions better than older ones
    noise_recent = np.random.normal(0, 0.25, n_recent)
    noise_old = np.random.normal(0, 0.4, n_old)
    noise = np.concatenate([noise_recent, noise_old])

    p_pred = np.clip(0.2 + y_true * 0.4 + noise, 0.01, 0.99)

    df = pd.DataFrame(
        {
            "flight_id": [f"DUMMY{i}" for i in range(n_samples)],
            "p_pred": p_pred,
            "y_true": y_true,
            "timestamp": timestamps,
        }
    )

    df.to_parquet(PERF_FILE, index=False)

    recent_df = df[df["timestamp"] >= (datetime.now(timezone.utc) - timedelta(days=7))]
    recent_brier = ((recent_df["p_pred"] - recent_df["y_true"].astype(int)) ** 2).mean()

    print(f"Dummy performance data created at: {PERF_FILE}")
    print(f"Total samples: {len(df)}, Recent samples: {len(recent_df)}")
    print(f"Recent 7-day Brier score: {recent_brier:.4f}")


if __name__ == "__main__":
    create_dummy_data()
