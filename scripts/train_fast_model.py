#!/usr/bin/env python3
"""Fast model training using simple but effective approaches."""

import pickle
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, classification_report, roc_auc_score


def load_real_flight_data(
    db_path: Path = Path("data/flights_real.duckdb"), limit: int = 100000
) -> pd.DataFrame:
    """Load real flight data quickly."""
    if not db_path.exists():
        print(f"❌ Real data not found at {db_path}")
        print("🔧 Run: python scripts/download_real_data.py")
        return pd.DataFrame()

    print(f"📊 Loading real flight data from {db_path}...")

    with duckdb.connect(str(db_path)) as conn:
        # Get a sample of diverse data for fast training
        query = f"""
            SELECT 
                carrier,
                origin, 
                dest,
                dep_hour,
                late,
                flight_date
            FROM historic_flights 
            WHERE carrier IS NOT NULL
              AND origin IS NOT NULL
              AND dest IS NOT NULL  
              AND dep_hour IS NOT NULL
              AND late IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {limit}
        """

        try:
            df = conn.execute(query).fetch_df()
            print(f"✅ Loaded {len(df):,} real flight records")
            return df
        except Exception as e:
            print(f"❌ Failed to load data: {e}")
            return pd.DataFrame()


def create_simple_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create simple, effective features quickly."""
    df = df.copy()

    # Parse date features
    df["flight_date"] = pd.to_datetime(df["flight_date"])
    df["month"] = df["flight_date"].dt.month
    df["day_of_week"] = df["flight_date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Time of day buckets (simple, effective)
    df["is_early_morning"] = (df["dep_hour"] <= 8).astype(int)
    df["is_evening_rush"] = ((df["dep_hour"] >= 16) & (df["dep_hour"] <= 19)).astype(
        int
    )
    df["is_late_night"] = (df["dep_hour"] >= 22).astype(int)

    # High-delay airports (based on common knowledge)
    high_delay_airports = {"LGA", "EWR", "JFK", "ORD", "LAX", "SFO", "ATL", "DFW"}
    df["origin_high_delay"] = df["origin"].isin(high_delay_airports).astype(int)
    df["dest_high_delay"] = df["dest"].isin(high_delay_airports).astype(int)

    # Route popularity (proxy for congestion)
    route_counts = df.groupby(["carrier", "origin", "dest"]).size()
    df["route"] = df["carrier"] + "_" + df["origin"] + "_" + df["dest"]
    df["route_volume"] = df["route"].map(route_counts).fillna(0)
    df["is_high_volume"] = (df["route_volume"] > df["route_volume"].median()).astype(
        int
    )

    print(f"🔧 Created features for {len(df):,} flights")
    print(f"   - Delay rate: {df['late'].mean():.1%}")
    print(f"   - High-delay origins: {df['origin_high_delay'].mean():.1%}")
    print(f"   - Weekend flights: {df['is_weekend'].mean():.1%}")

    return df


def train_fast_models(df: pd.DataFrame):
    """Train multiple fast models and pick the best."""
    print("🚀 Training fast models...")

    # Prepare features
    feature_cols = [
        "dep_hour",
        "month",
        "day_of_week",
        "is_weekend",
        "is_early_morning",
        "is_evening_rush",
        "is_late_night",
        "origin_high_delay",
        "dest_high_delay",
        "is_high_volume",
    ]

    # Encode categorical variables
    df_model = df.copy()

    # One-hot encode carrier (limit to top carriers for speed)
    top_carriers = df["carrier"].value_counts().head(6).index
    for carrier in top_carriers:
        df_model[f"carrier_{carrier}"] = (df["carrier"] == carrier).astype(int)
        feature_cols.append(f"carrier_{carrier}")

    # Prepare data
    X = df_model[feature_cols].fillna(0)
    y = df_model["late"].astype(int)

    # Split data
    split_idx = int(0.8 * len(df))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"📈 Training set: {len(X_train):,} flights")
    print(f"📊 Test set: {len(X_test):,} flights")

    models = {}
    results = {}

    # Model 1: Fast Logistic Regression
    print("  🔄 Training Logistic Regression...")
    start_time = time.time()
    lr_model = LogisticRegression(random_state=42, max_iter=500)
    lr_model.fit(X_train, y_train)
    lr_time = time.time() - start_time

    lr_pred_proba = lr_model.predict_proba(X_test)[:, 1]
    lr_auc = roc_auc_score(y_test, lr_pred_proba)
    lr_brier = brier_score_loss(y_test, lr_pred_proba)

    models["logistic"] = lr_model
    results["logistic"] = {"auc": lr_auc, "brier": lr_brier, "train_time": lr_time}

    print(
        f"    ✅ Logistic: AUC={lr_auc:.3f}, Brier={lr_brier:.3f}, Time={lr_time:.1f}s"
    )

    # Model 2: Fast Random Forest (small)
    print("  🔄 Training Random Forest...")
    start_time = time.time()
    rf_model = RandomForestClassifier(
        n_estimators=50, max_depth=10, random_state=42, n_jobs=-1  # Small for speed
    )
    rf_model.fit(X_train, y_train)
    rf_time = time.time() - start_time

    rf_pred_proba = rf_model.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_pred_proba)
    rf_brier = brier_score_loss(y_test, rf_pred_proba)

    models["random_forest"] = rf_model
    results["random_forest"] = {"auc": rf_auc, "brier": rf_brier, "train_time": rf_time}

    print(
        f"    ✅ Random Forest: AUC={rf_auc:.3f}, Brier={rf_brier:.3f}, Time={rf_time:.1f}s"
    )

    # Choose best model (prefer Logistic for interpretability if close)
    if abs(lr_auc - rf_auc) < 0.02:  # If within 2% AUC, prefer Logistic
        best_model_name = "logistic"
        best_model = lr_model
    else:
        best_model_name = "random_forest" if rf_auc > lr_auc else "logistic"
        best_model = models[best_model_name]

    print(f"\n🏆 Best model: {best_model_name}")
    print(f"   AUC: {results[best_model_name]['auc']:.3f}")
    print(f"   Brier Score: {results[best_model_name]['brier']:.3f}")

    # Save models
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)

    model_path = models_dir / f"fast_delay_model_{best_model_name}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(
            {
                "model": best_model,
                "feature_cols": feature_cols,
                "model_type": best_model_name,
                "results": results[best_model_name],
                "training_stats": {
                    "n_train": len(X_train),
                    "n_test": len(X_test),
                    "delay_rate": y_train.mean(),
                },
            },
            f,
        )

    print(f"💾 Saved model to {model_path}")

    # Feature importance (if Random Forest)
    if best_model_name == "random_forest" and hasattr(
        best_model, "feature_importances_"
    ):
        print("\n📊 Top feature importances:")
        importances = list(zip(feature_cols, best_model.feature_importances_))
        importances.sort(key=lambda x: x[1], reverse=True)
        for feat, imp in importances[:8]:
            print(f"   {feat}: {imp:.3f}")

    return best_model, feature_cols, results[best_model_name]


def test_model_predictions(model, feature_cols):
    """Test the model with some example predictions."""
    print("\n🔮 Testing model predictions...")

    # Create test cases
    test_cases = [
        # [dep_hour, month, day_of_week, is_weekend, is_early_morning, is_evening_rush,
        #  is_late_night, origin_high_delay, dest_high_delay, is_high_volume, carrier_DL, etc.]
        # Early morning Delta JFK->LAX (should be low delay)
        {
            "case": "DL Early Morning JFK→LAX",
            "features": [7, 6, 2, 0, 1, 0, 0, 1, 1, 1] + [1] + [0] * 5,
        },
        # Evening rush United ORD->LAX (should be higher delay)
        {
            "case": "UA Evening Rush ORD→LAX",
            "features": [17, 6, 4, 0, 0, 1, 0, 1, 1, 1] + [0] + [0, 0, 0, 1, 0],
        },
        # Late night American LGA->DFW (should be high delay)
        {
            "case": "AA Late Night LGA→DFW",
            "features": [23, 12, 5, 1, 0, 0, 1, 1, 1, 0] + [0] + [1, 0, 0, 0, 0],
        },
        # Early Southwest regional (should be lower delay)
        {
            "case": "SW Early Regional",
            "features": [6, 3, 1, 0, 1, 0, 0, 0, 0, 0] + [0] + [0, 0, 0, 0, 1],
        },
    ]

    for test_case in test_cases:
        # Pad or trim features to match expected length
        features = test_case["features"]
        if len(features) < len(feature_cols):
            features += [0] * (len(feature_cols) - len(features))
        features = features[: len(feature_cols)]

        # Make prediction
        X_test = np.array(features).reshape(1, -1)

        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(X_test)[0, 1]
        else:
            prob = model.predict(X_test)[0]

        print(f"   {test_case['case']}: {prob:.1%} delay probability")


def main():
    """Main training function."""
    print("⚡ Fast Flight Delay Model Training")
    print("=" * 50)

    # Step 1: Load real data
    df = load_real_flight_data(limit=50000)  # Limit for speed

    if df.empty:
        print("❌ No data available. Please download real data first:")
        print("   python scripts/download_real_data.py")
        return

    # Step 2: Feature engineering
    df = create_simple_features(df)

    # Step 3: Train models
    model, feature_cols, results = train_fast_models(df)

    # Step 4: Test predictions
    test_model_predictions(model, feature_cols)

    print("\n🎯 Training complete! Best model achieved:")
    print(f"   - AUC: {results['auc']:.3f}")
    print(f"   - Brier Score: {results['brier']:.3f}")
    print(f"   - Training time: {results['train_time']:.1f}s")

    print("\n📈 Model ready for production!")
    print("   Saved to: models/fast_delay_model_*.pkl")


if __name__ == "__main__":
    main()
