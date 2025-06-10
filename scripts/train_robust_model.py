#!/usr/bin/env python3
"""Train robust hierarchical model with expanded dataset."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from flight_delay_bayes.bayes.hier_model import HierarchicalDelayModel


def load_robust_training_data(
    db_path: Path = Path("data/flights_expanded.duckdb"),
) -> pd.DataFrame:
    """Load training data with focused feature set for stability."""
    with duckdb.connect(str(db_path)) as conn:
        df = conn.execute(
            """
            SELECT flight_date, carrier, origin, dest, dep_hour, 
                   dep_delay_minutes, late
            FROM historic_flights
            WHERE extract(year from flight_date) <= 2022  -- Use 2021-2022 for training
            ORDER BY flight_date
        """
        ).fetch_df()

    print(f"📊 Loaded {len(df):,} training flights")

    # Add essential features only (avoid numerical instability)
    df["flight_date"] = pd.to_datetime(df["flight_date"])
    df["month"] = df["flight_date"].dt.month
    df["day_of_week"] = df["flight_date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Time of day categories (stable categorical)
    def categorize_hour(hour):
        if 5 <= hour <= 8:
            return "early_morning"
        elif 9 <= hour <= 14:
            return "midday"
        elif 15 <= hour <= 18:
            return "afternoon"
        elif 19 <= hour <= 22:
            return "evening"
        else:
            return "night"

    df["time_category"] = df["dep_hour"].apply(categorize_hour)

    # Create route identifier
    df["route"] = df["carrier"] + ":" + df["origin"] + ":" + df["dest"]

    # Add basic weather simulation (more stable than complex features)
    np.random.seed(42)
    df["wx_temp_c"] = np.random.normal(15, 8, len(df))
    df["wx_wind_kt"] = np.random.exponential(6, len(df))
    df["wx_precip_mm"] = np.random.exponential(1.5, len(df)) * (
        np.random.random(len(df)) < 0.25
    )

    print("✨ Feature summary:")
    print(f"   - Carriers: {df['carrier'].nunique()}")
    print(f"   - Routes: {df['route'].nunique()}")
    print(f"   - Time categories: {df['time_category'].value_counts().to_dict()}")
    print(f"   - Delay rate: {df['late'].mean():.1%}")

    return df


def train_robust_model():
    """Train a robust, stable hierarchical model."""
    print("🎯 Training robust hierarchical model...")

    # Load data
    df = load_robust_training_data()

    if len(df) == 0:
        print("❌ No training data found!")
        return None

    # Focused feature set for stability
    model = HierarchicalDelayModel()

    # Train with conservative settings for stability
    print("🚀 Training with focused feature set...")
    model.fit(df, draws=1000, tune=500, target_accept=0.85)

    # Save model
    model_path = Path("models/hier_robust_2021_2022.pkl")
    model.save(model_path)

    print(f"💾 Robust model saved to {model_path}")

    # Test quick predictions
    print("🔮 Testing predictions on training routes...")

    # Sample a few routes for testing
    test_routes = [
        ("DL", "JFK", "LAX", 8),  # Cross-country morning
        ("DL", "LAX", "JFK", 23),  # Red-eye
        ("AA", "DFW", "LAX", 16),  # Afternoon hub
        ("SW", "MDW", "LAX", 6),  # Early Southwest
        ("B6", "JFK", "LAX", 14),  # JetBlue afternoon
    ]

    for carrier, origin, dest, dep_hour in test_routes:
        # Create test data point
        test_df = pd.DataFrame(
            {
                "carrier": [carrier],
                "origin": [origin],
                "dest": [dest],
                "dep_hour": [dep_hour],
                "month": [6],  # June
                "day_of_week": [2],  # Wednesday
                "is_weekend": [0],
                "time_category": [
                    (
                        "afternoon"
                        if 15 <= dep_hour <= 18
                        else "early_morning" if dep_hour <= 8 else "evening"
                    )
                ],
                "route": [f"{carrier}:{origin}:{dest}"],
                "wx_temp_c": [20.0],
                "wx_wind_kt": [10.0],
                "wx_precip_mm": [0.0],
            }
        )

        pred = model.predict(test_df, return_mean=True)[0]
        print(
            f"   {carrier} {origin}→{dest} {dep_hour:02d}:00: {pred:.1%} delay probability"
        )

    return model


if __name__ == "__main__":
    model = train_robust_model()
