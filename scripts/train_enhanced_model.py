#!/usr/bin/env python3
"""Train enhanced hierarchical model with comprehensive feature engineering."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from flight_delay_bayes.bayes.hier_model import HierarchicalDelayModel


def add_enhanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add sophisticated features for better prediction accuracy."""
    df = df.copy()

    # Convert flight_date to datetime for feature extraction
    df["flight_date"] = pd.to_datetime(df["flight_date"])

    # Temporal features
    df["month"] = df["flight_date"].dt.month
    df["day_of_week"] = df["flight_date"].dt.dayofweek  # 0=Monday
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["day_of_year"] = df["flight_date"].dt.dayofyear
    df["quarter"] = df["flight_date"].dt.quarter

    # Seasonal features (cyclical encoding)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    # Holiday indicators (simplified)
    holiday_months = [11, 12, 1]  # Nov, Dec, Jan for holiday season
    summer_months = [6, 7, 8]  # Summer travel season
    df["is_holiday_season"] = df["month"].isin(holiday_months).astype(int)
    df["is_summer_season"] = df["month"].isin(summer_months).astype(int)

    # Time of day categories
    def categorize_hour(hour):
        if 5 <= hour <= 8:
            return "early_morning"
        elif 9 <= hour <= 11:
            return "morning"
        elif 12 <= hour <= 14:
            return "midday"
        elif 15 <= hour <= 18:
            return "afternoon"
        elif 19 <= hour <= 22:
            return "evening"
        else:
            return "night"

    df["time_category"] = df["dep_hour"].apply(categorize_hour)

    # Route complexity features
    # Distance categories (approximate)
    def get_route_complexity(origin, dest, carrier):
        # International routes
        international_airports = {"LHR", "ATH", "CDG", "FRA", "NRT"}
        if origin in international_airports or dest in international_airports:
            return "international"

        # Hub-to-hub routes
        hubs = {
            "DL": {"ATL", "JFK", "LGA", "BOS"},
            "AA": {"DFW", "ORD", "JFK", "LAX", "MIA"},
            "UA": {"ORD", "SFO", "EWR", "LAX", "JFK"},
            "SW": {"DAL", "MDW", "BWI", "LAX"},
            "B6": {"JFK", "BOS", "LAX"},
            "AS": {"SEA", "PDX", "ANC"},
        }

        carrier_hubs = hubs.get(carrier, set())
        if origin in carrier_hubs and dest in carrier_hubs:
            return "hub_to_hub"
        elif origin in carrier_hubs or dest in carrier_hubs:
            return "hub_connection"

        # Cross-country routes
        east_coast = {"JFK", "LGA", "EWR", "BOS", "BWI", "MIA"}
        west_coast = {"LAX", "SFO", "SEA", "PDX"}

        if (origin in east_coast and dest in west_coast) or (
            origin in west_coast and dest in east_coast
        ):
            return "cross_country"

        return "regional"

    df["route_complexity"] = df.apply(
        lambda x: get_route_complexity(x["origin"], x["dest"], x["carrier"]), axis=1
    )

    # Airport congestion tiers
    congestion_tiers = {
        "high": ["LGA", "EWR", "JFK", "ORD", "LAX", "SFO"],
        "medium": ["ATL", "DFW", "MDW", "BOS", "MIA"],
        "low": ["SEA", "PDX", "BWI", "DAL", "ANC"],
    }

    def get_congestion_tier(airport):
        for tier, airports in congestion_tiers.items():
            if airport in airports:
                return tier
        return "unknown"

    df["origin_congestion"] = df["origin"].apply(get_congestion_tier)
    df["dest_congestion"] = df["dest"].apply(get_congestion_tier)

    # Add simulated weather features (since we don't have real weather for synthetic data)
    # These would be replaced with real weather data in production
    np.random.seed(42)  # For reproducibility
    df["wx_temp_c"] = np.random.normal(15, 10, len(df))  # Temperature variation
    df["wx_wind_kt"] = np.random.exponential(8, len(df))  # Wind typically exponential
    df["wx_precip_mm"] = np.random.exponential(2, len(df)) * (
        np.random.random(len(df)) < 0.3
    )  # 30% chance of precip

    # Create route identifier for hierarchical effects
    df["route"] = df["carrier"] + ":" + df["origin"] + ":" + df["dest"]

    return df


def load_enhanced_training_data(db_path: Path) -> pd.DataFrame:
    """Load and enhance training data."""
    with duckdb.connect(str(db_path)) as conn:
        df = conn.execute(
            """
            SELECT flight_date, carrier, origin, dest, dep_hour, 
                   dep_delay_minutes, late
            FROM historic_flights
            ORDER BY flight_date
        """
        ).fetch_df()

    print(f"📊 Loaded {len(df):,} flights from database")

    # Add enhanced features
    df = add_enhanced_features(df)

    print("✨ Added enhanced features:")
    print(f"   - Route complexities: {df['route_complexity'].value_counts().to_dict()}")
    print(f"   - Time categories: {df['time_category'].value_counts().to_dict()}")
    print(f"   - Unique routes: {df['route'].nunique()}")

    return df


def train_enhanced_model(db_path: Path = Path("data/flights_expanded.duckdb")):
    """Train enhanced hierarchical model."""
    print("🎯 Training enhanced hierarchical model...")

    # Load enhanced data
    df = load_enhanced_training_data(db_path)

    # Split by year for validation
    train_df = df[df["flight_date"].dt.year <= 2022].copy()
    test_df = df[df["flight_date"].dt.year == 2023].copy()

    print(
        f"📈 Training set: {len(train_df):,} flights ({train_df['flight_date'].dt.year.min()}-{train_df['flight_date'].dt.year.max()})"
    )
    print(f"📊 Test set: {len(test_df):,} flights (2023)")
    print(f"   Train delay rate: {train_df['late'].mean():.1%}")
    print(f"   Test delay rate: {test_df['late'].mean():.1%}")

    # Initialize and train model
    model = HierarchicalDelayModel()

    # Enhanced feature set for training
    feature_columns = [
        "carrier",
        "origin",
        "dest",
        "dep_hour",
        "late",
        "month",
        "day_of_week",
        "is_weekend",
        "quarter",
        "month_sin",
        "month_cos",
        "dow_sin",
        "dow_cos",
        "is_holiday_season",
        "is_summer_season",
        "time_category",
        "route_complexity",
        "origin_congestion",
        "dest_congestion",
        "wx_temp_c",
        "wx_wind_kt",
        "wx_precip_mm",
        "route",
    ]

    train_features = train_df[feature_columns].copy()

    # Train model with more samples for better convergence
    print("🚀 Training hierarchical model with enhanced features...")
    model.fit(train_features, draws=1500, tune=750, target_accept=0.9)

    # Save enhanced model
    model_path = Path("models/hier_enhanced_2021_2022_2023.pkl")
    model.save(model_path)

    print(f"💾 Enhanced model saved to {model_path}")

    # Quick validation
    if len(test_df) > 0:
        print("📊 Validating on 2023 data...")
        test_features = test_df[feature_columns].copy()
        predictions = model.predict(test_features)

        # Calculate metrics
        from sklearn.metrics import log_loss, roc_auc_score

        y_true = test_df["late"].values
        y_pred = predictions

        try:
            auc = roc_auc_score(y_true, y_pred)
            brier = np.mean((y_pred - y_true) ** 2)
            logloss = log_loss(y_true, np.clip(y_pred, 1e-15, 1 - 1e-15))

            print("   🎯 Validation Metrics:")
            print(f"      - AUC: {auc:.3f}")
            print(f"      - Brier Score: {brier:.3f}")
            print(f"      - Log Loss: {logloss:.3f}")
            print(
                f"      - Calibration: Mean pred={y_pred.mean():.3f}, Actual={y_true.mean():.3f}"
            )

        except Exception as e:
            print(f"   ⚠️ Validation metrics failed: {e}")

    return model


if __name__ == "__main__":
    model = train_enhanced_model()
