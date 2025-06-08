"""Data-driven delay curve calculation and prediction from historical flight data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import duckdb
import numpy as np
import pandas as pd

__all__ = ["DelayPredictor", "calculate_delay_curve", "load_delay_curve"]

DEFAULT_DB = Path("data/flights.duckdb")
MODELS_DIR = Path("models")
DELAY_CURVE_FILE = MODELS_DIR / "delay_curve.json"


class DelayPredictor:
    """Predicts expected delay minutes from late probability using a data-driven curve."""

    def __init__(self, curve_data: Dict[str, float]):
        """Initialize with delay curve parameters.

        Parameters
        ----------
        curve_data : Dict[str, float]
            Dictionary containing:
            - mean_ontime_delay: Mean delay for on-time flights (minutes)
            - mean_late_delay: Mean delay for late flights (minutes)
            - threshold_prob: Probability threshold where delays start rising
        """
        self.mean_ontime_delay = curve_data["mean_ontime_delay"]
        self.mean_late_delay = curve_data["mean_late_delay"]
        self.threshold_prob = curve_data["threshold_prob"]

    def predict_delay(self, late_probability: float) -> float:
        """Predict expected delay minutes from late probability.

        Uses piece-wise linear function:
        - Below threshold: delay = mean_ontime_delay
        - Above threshold: linear interpolation to mean_late_delay

        Parameters
        ----------
        late_probability : float
            Probability of being late (0-1)

        Returns
        -------
        float
            Expected delay in minutes
        """
        if late_probability <= self.threshold_prob:
            return self.mean_ontime_delay

        # Linear interpolation from threshold to 1.0
        progress = (late_probability - self.threshold_prob) / (
            1.0 - self.threshold_prob
        )
        return self.mean_ontime_delay + progress * (
            self.mean_late_delay - self.mean_ontime_delay
        )

    def predict_threshold_probabilities(
        self, base_late_prob: float
    ) -> Dict[str, float]:
        """Predict probabilities of exceeding different delay thresholds.

        Uses the delay curve and base probability to estimate probabilities
        for multiple delay thresholds using exponential decay assumption.

        Parameters
        ----------
        base_late_prob : float
            Base probability of being late (≥15 min)

        Returns
        -------
        Dict[str, float]
            Dictionary with keys p_late_15, p_late_30, p_late_45, p_late_60
        """
        # Start with the base 15-minute probability
        p_15 = base_late_prob

        # Get expected delay for this probability
        expected_delay = self.predict_delay(base_late_prob)

        # If expected delay is very low, all higher thresholds should be much lower
        if expected_delay < 15:
            return {
                "p_late_15": p_15,
                "p_late_30": p_15 * 0.3,
                "p_late_45": p_15 * 0.1,
                "p_late_60": p_15 * 0.05,
            }

        # Use exponential decay model for higher thresholds
        # λ = -ln(0.5) / (expected_delay - 15) gives 50% prob at expected delay
        if expected_delay > 15:
            lambda_param = 0.693 / (
                expected_delay - 15 + 1e-6
            )  # Avoid division by zero
        else:
            lambda_param = 1.0

        # Calculate probabilities using exponential survival function
        # P(delay ≥ t) = P(delay ≥ 15) * exp(-λ * (t - 15))
        p_30 = p_15 * np.exp(-lambda_param * (30 - 15))
        p_45 = p_15 * np.exp(-lambda_param * (45 - 15))
        p_60 = p_15 * np.exp(-lambda_param * (60 - 15))

        # Ensure monotonicity and reasonable bounds
        p_30 = min(p_30, p_15 * 0.8)  # At most 80% of 15-min prob
        p_45 = min(p_45, p_30 * 0.8)  # At most 80% of 30-min prob
        p_60 = min(p_60, p_45 * 0.8)  # At most 80% of 45-min prob

        return {
            "p_late_15": p_15,
            "p_late_30": max(0.0, p_30),
            "p_late_45": max(0.0, p_45),
            "p_late_60": max(0.0, p_60),
        }


def _load_historic_delays(
    start_year: int, end_year: int, db_path: Path = DEFAULT_DB
) -> pd.DataFrame:
    """Load historical flight delay data."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    query = """
        SELECT 
            dep_delay_minutes,
            late
        FROM historic_flights 
        WHERE strftime('%Y', flight_date)::INTEGER >= ?
          AND strftime('%Y', flight_date)::INTEGER <= ?
          AND dep_delay_minutes IS NOT NULL
          AND dep_delay_minutes >= -60  -- Filter extreme outliers
          AND dep_delay_minutes <= 300   -- Filter extreme outliers
    """

    with duckdb.connect(str(db_path)) as conn:
        df = conn.execute(query, (start_year, end_year)).fetch_df()

    return df


def calculate_delay_curve(
    start_year: int = 2022, end_year: int = 2023, db_path: Path = DEFAULT_DB
) -> Dict[str, float]:
    """Calculate delay curve parameters from historical data.

    Parameters
    ----------
    start_year, end_year : int
        Year range for analysis (inclusive)
    db_path : Path
        Path to database

    Returns
    -------
    Dict[str, float]
        Delay curve parameters
    """
    print(f"📊 Calculating delay curve from {start_year}-{end_year} historic data...")

    # Load delay data
    df = _load_historic_delays(start_year, end_year, db_path)

    if len(df) == 0:
        raise ValueError("No delay data found for specified years")

    print(f"   Loaded {len(df):,} flight records")

    # Calculate mean delays by category
    ontime_flights = df[~df["late"]]
    late_flights = df[df["late"]]

    mean_ontime_delay = ontime_flights["dep_delay_minutes"].mean()
    mean_late_delay = late_flights["dep_delay_minutes"].mean()

    # Calculate probability bins to find threshold where delays start rising
    df["prob_bin"] = pd.cut(df.index / len(df), bins=20, labels=False)
    bin_stats = (
        df.groupby("prob_bin")
        .agg({"dep_delay_minutes": "mean", "late": "mean"})
        .reset_index()
    )

    # Find threshold where delay starts significantly increasing
    # Look for first bin where delay > mean_ontime_delay + 5 minutes
    threshold_idx = 0
    for idx, row in bin_stats.iterrows():
        if row["dep_delay_minutes"] > mean_ontime_delay + 5:
            threshold_idx = idx
            break

    # Convert bin index to probability
    threshold_prob = threshold_idx / 20.0

    # Ensure reasonable bounds
    threshold_prob = max(0.1, min(0.8, threshold_prob))

    curve_data = {
        "mean_ontime_delay": float(mean_ontime_delay),
        "mean_late_delay": float(mean_late_delay),
        "threshold_prob": float(threshold_prob),
        "data_years": f"{start_year}-{end_year}",
        "n_flights": len(df),
        "ontime_pct": float((~df["late"]).mean() * 100),
        "late_pct": float(df["late"].mean() * 100),
    }

    print(
        f"   On-time flights: {curve_data['ontime_pct']:.1f}% (mean delay: {curve_data['mean_ontime_delay']:.1f} min)"
    )
    print(
        f"   Late flights: {curve_data['late_pct']:.1f}% (mean delay: {curve_data['mean_late_delay']:.1f} min)"
    )
    print(f"   Threshold probability: {curve_data['threshold_prob']:.3f}")

    return curve_data


def save_delay_curve(
    curve_data: Dict[str, float], filepath: Path = DELAY_CURVE_FILE
) -> None:
    """Save delay curve to JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w") as f:
        json.dump(curve_data, f, indent=2)

    print(f"💾 Delay curve saved to {filepath}")


def load_delay_curve(filepath: Path = DELAY_CURVE_FILE) -> DelayPredictor:
    """Load delay curve from JSON file."""
    if not filepath.exists():
        raise FileNotFoundError(f"Delay curve file not found: {filepath}")

    with open(filepath, "r") as f:
        curve_data = json.load(f)

    return DelayPredictor(curve_data)


def create_default_delay_curve() -> Dict[str, float]:
    """Create default delay curve when no data is available."""
    return {
        "mean_ontime_delay": 0.0,
        "mean_late_delay": 25.0,  # Reasonable default for late flights
        "threshold_prob": 0.5,
        "data_years": "default",
        "n_flights": 0,
        "ontime_pct": 80.0,
        "late_pct": 20.0,
    }
