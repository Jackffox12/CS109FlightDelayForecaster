"""Hierarchical Bayesian model for flight delays with random effects and weather covariates."""

from __future__ import annotations

import pickle
from pathlib import Path

import arviz as az
import bambi as bmb
import duckdb
import numpy as np
import pandas as pd

__all__ = [
    "HierarchicalDelayModel",
    "train_hierarchical_model",
    "load_hierarchical_model",
]

DEFAULT_DB = Path("data/flights.duckdb")
MODELS_DIR = Path("models")


class HierarchicalDelayModel:
    """Hierarchical Bayesian model for flight delay prediction.

    Uses Bambi (PyMC backend) to model delays with:
    - Fixed effects: carrier, origin, dest, dep_hour, weather variables
    - Random effects: route-specific intercepts (carrier:origin:dest)
    """

    def __init__(self, model: bmb.Model = None, trace: az.InferenceData = None):
        self.model = model
        self.trace = trace
        self._fitted = False

    def fit(
        self,
        df: pd.DataFrame,
        draws: int = 2000,
        tune: int = 1000,
        target_accept: float = 0.9,
    ) -> None:
        """Fit the hierarchical model to training data.

        Parameters
        ----------
        df : pd.DataFrame
            Training data with columns: late, carrier, origin, dest, dep_hour,
            wx_temp_c, wx_wind_kt, wx_precip_mm
        draws : int
            Number of posterior samples to draw
        tune : int
            Number of tuning samples
        target_accept : float
            Target acceptance rate for NUTS sampler
        """
        # Prepare data
        df_clean = self._prepare_data(df, for_prediction=False)

        # Build dynamic formula based on data variability
        formula = self._get_dynamic_formula(df_clean)

        print("🔧 Building hierarchical model...")
        print(f"   Formula: {formula}")
        self.model = bmb.Model(formula, df_clean, family="bernoulli")

        print("📊 Model summary:")
        print(f"   - Observations: {len(df_clean):,}")
        print(f"   - Carriers: {df_clean['carrier'].nunique()}")
        print(f"   - Origins: {df_clean['origin'].nunique()}")
        print(f"   - Destinations: {df_clean['dest'].nunique()}")
        print(f"   - Routes: {df_clean['route'].nunique()}")
        print(f"   - Hours: {df_clean['dep_hour'].nunique()}")

        print(f"🚀 Fitting model with {draws} draws, {tune} tune samples...")

        # Fit with NUTS sampler
        self.trace = self.model.fit(
            draws=draws,
            tune=tune,
            target_accept=target_accept,
            random_seed=42,
            chains=2,
            cores=2,
        )

        self._fitted = True
        print("✅ Model fitting complete!")

        # Print convergence diagnostics
        self._print_diagnostics()

    def predict(self, df: pd.DataFrame, return_mean: bool = True) -> np.ndarray:
        """Make predictions on new data.

        Parameters
        ----------
        df : pd.DataFrame
            New data with same columns as training data
        return_mean : bool
            If True, return posterior mean predictions. If False, return full posterior samples.

        Returns
        -------
        np.ndarray
            Predicted probabilities of delay
        """
        if not self._fitted:
            raise ValueError("Model must be fitted before making predictions")

        if self.trace is None:
            raise ValueError("No trace data available for prediction")

        df_clean = self._prepare_data(df, for_prediction=True)

        if self.model is not None:
            # Full prediction with model
            posterior_pred = self.model.predict(
                self.trace, data=df_clean, kind="response"
            )
        else:
            # Simplified prediction using intercept only (for loaded models without full model object)
            intercept_samples = self.trace.posterior["Intercept"].values.flatten()
            # Apply logistic transformation to get probabilities
            logits = intercept_samples[:, np.newaxis]  # Shape: (n_samples, 1)
            probabilities = 1 / (1 + np.exp(-logits))  # Logistic function
            # Replicate for each observation
            posterior_pred = np.tile(probabilities, (1, len(df_clean)))

        if return_mean:
            return posterior_pred.mean(axis=0)
        else:
            return posterior_pred

    def save(self, filepath: Path | str) -> None:
        """Save the fitted model to disk."""
        if not self._fitted:
            raise ValueError("Cannot save unfitted model")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Save using arviz netcdf format for PyMC compatibility
        trace_path = filepath.with_suffix(".nc")
        az.to_netcdf(self.trace, trace_path)

        # Save model metadata separately
        metadata = {
            "model_formula": str(self.model.formula),
            "model_family": str(self.model.family),
            "fitted": self._fitted,
            "trace_path": str(trace_path),
        }

        with open(filepath, "wb") as f:
            pickle.dump(metadata, f)

        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"💾 Model saved to {filepath} ({file_size_mb:.1f} MB)")

    @classmethod
    def load(cls, filepath: Path | str) -> "HierarchicalDelayModel":
        """Load a fitted model from disk."""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        with open(filepath, "rb") as f:
            metadata = pickle.load(f)

        # Load trace from netcdf
        trace_path = Path(metadata["trace_path"])
        if trace_path.exists():
            trace = az.from_netcdf(trace_path)
        else:
            trace = None
            print("⚠️  Warning: Trace data not found - predictions may not work")

        instance = cls(model=None, trace=trace)
        instance._fitted = metadata["fitted"]

        print(f"📂 Model metadata loaded from {filepath}")
        return instance

    def _prepare_data(
        self, df: pd.DataFrame, for_prediction: bool = False
    ) -> pd.DataFrame:
        """Prepare data for modeling by cleaning and feature engineering."""
        df_clean = df.copy()

        # Create route identifier for random effects
        df_clean["route"] = (
            df_clean["carrier"] + ":" + df_clean["origin"] + ":" + df_clean["dest"]
        )

        # Handle missing weather data
        weather_cols = ["wx_temp_c", "wx_wind_kt", "wx_precip_mm"]
        for col in weather_cols:
            if col in df_clean.columns:
                # Fill missing values with median
                median_val = df_clean[col].median()
                df_clean[col] = df_clean[col].fillna(median_val)
            else:
                # Create column with default values if missing
                df_clean[col] = 0.0

        # Ensure dep_hour is numeric
        df_clean["dep_hour"] = pd.to_numeric(df_clean["dep_hour"], errors="coerce")
        df_clean["dep_hour"] = df_clean["dep_hour"].fillna(12)  # Default to noon

        # Handle the target variable
        if "late" in df_clean.columns:
            # Convert late to numeric if boolean
            if df_clean["late"].dtype == bool:
                df_clean["late"] = df_clean["late"].astype(int)
        elif not for_prediction:
            # If we're training and 'late' is missing, that's an error
            raise ValueError("Target variable 'late' is required for training")

        # Drop rows with any remaining missing values in key columns
        required_cols = ["carrier", "origin", "dest", "dep_hour"] + weather_cols
        if not for_prediction and "late" in df_clean.columns:
            required_cols.append("late")

        df_clean = df_clean.dropna(subset=required_cols)

        return df_clean

    def _get_dynamic_formula(self, df: pd.DataFrame) -> str:
        """Build formula dynamically based on data variability and enhanced features."""
        base_formula = "late ~ 1"

        # Core categorical variables
        if df["carrier"].nunique() > 1:
            base_formula += " + carrier"
        if df["origin"].nunique() > 1:
            base_formula += " + origin"
        if df["dest"].nunique() > 1:
            base_formula += " + dest"

        # Time-based features
        if df["dep_hour"].nunique() > 1:
            base_formula += " + dep_hour"

        # Enhanced temporal features (if available)
        if "month" in df.columns and df["month"].nunique() > 1:
            base_formula += " + month"
        if "day_of_week" in df.columns and df["day_of_week"].nunique() > 1:
            base_formula += " + day_of_week"
        if "is_weekend" in df.columns:
            base_formula += " + is_weekend"
        if "quarter" in df.columns and df["quarter"].nunique() > 1:
            base_formula += " + quarter"

        # Cyclical encoding (continuous variables)
        cyclical_vars = ["month_sin", "month_cos", "dow_sin", "dow_cos"]
        for var in cyclical_vars:
            if var in df.columns and df[var].std() > 0:
                base_formula += f" + {var}"

        # Seasonal indicators
        seasonal_vars = ["is_holiday_season", "is_summer_season"]
        for var in seasonal_vars:
            if var in df.columns:
                base_formula += f" + {var}"

        # Route and airport features
        if "time_category" in df.columns and df["time_category"].nunique() > 1:
            base_formula += " + time_category"
        if "route_complexity" in df.columns and df["route_complexity"].nunique() > 1:
            base_formula += " + route_complexity"
        if "origin_congestion" in df.columns and df["origin_congestion"].nunique() > 1:
            base_formula += " + origin_congestion"
        if "dest_congestion" in df.columns and df["dest_congestion"].nunique() > 1:
            base_formula += " + dest_congestion"

        # Weather variables (if they have variation)
        weather_cols = ["wx_temp_c", "wx_wind_kt", "wx_precip_mm"]
        for col in weather_cols:
            if col in df.columns and df[col].std() > 0:
                base_formula += f" + {col}"

        # Interaction terms (for better modeling)
        # Only add if we have sufficient data
        if len(df) > 1000:
            if all(col in df.columns for col in ["carrier", "origin_congestion"]):
                if (
                    df["carrier"].nunique() > 1
                    and df["origin_congestion"].nunique() > 1
                ):
                    base_formula += " + carrier:origin_congestion"

            if all(col in df.columns for col in ["time_category", "route_complexity"]):
                if (
                    df["time_category"].nunique() > 1
                    and df["route_complexity"].nunique() > 1
                ):
                    base_formula += " + time_category:route_complexity"

        # Random effects for routes (if we have multiple routes)
        if "route" in df.columns and df["route"].nunique() > 1:
            base_formula += " + (1|route)"

            # Add route-specific time effects if enough data
            if len(df) > 5000 and df["dep_hour"].nunique() > 1:
                base_formula += " + (dep_hour|route)"

        return base_formula

    def _print_diagnostics(self) -> None:
        """Print model convergence diagnostics."""
        print("\n📈 Convergence Diagnostics:")

        # R-hat convergence diagnostic
        rhat = az.rhat(self.trace)
        rhat_values = []
        for var in rhat.data_vars:
            rhat_vals = rhat[var].values.flatten()
            rhat_values.extend(rhat_vals[~np.isnan(rhat_vals)])

        if rhat_values:
            max_rhat = max(rhat_values)
            print(
                f"   - Max R-hat: {max_rhat:.3f} {'✅' if max_rhat < 1.1 else '⚠️ (>1.1 indicates convergence issues)'}"
            )

        # Effective sample size
        ess = az.ess(self.trace)
        ess_values = []
        for var in ess.data_vars:
            ess_vals = ess[var].values.flatten()
            ess_values.extend(ess_vals[~np.isnan(ess_vals)])

        if ess_values:
            min_ess = min(ess_values)
            print(
                f"   - Min ESS: {min_ess:.0f} {'✅' if min_ess > 400 else '⚠️ (low effective sample size)'}"
            )


def _load_training_data(
    start_year: int, end_year: int, db_path: Path = DEFAULT_DB
) -> pd.DataFrame:
    """Load training data from database with weather enrichment."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    query = """
        SELECT 
            f.carrier,
            f.origin, 
            f.dest,
            f.dep_hour,
            f.late,
            w.temp_c as wx_temp_c,
            w.wind_kt as wx_wind_kt, 
            w.precip_mm as wx_precip_mm
        FROM historic_flights f
        LEFT JOIN historic_weather w ON (
            f.origin = w.airport 
            AND f.flight_date::DATE = w.date 
            AND f.dep_hour = w.hour
        )
        WHERE strftime('%Y', f.flight_date)::INTEGER >= ?
          AND strftime('%Y', f.flight_date)::INTEGER <= ?
          AND f.dep_hour IS NOT NULL
    """

    with duckdb.connect(str(db_path)) as conn:
        df = conn.execute(query, (start_year, end_year)).fetch_df()

    print(f"📊 Loaded {len(df):,} training records from {start_year}-{end_year}")
    return df


def train_hierarchical_model(
    start_year: int,
    end_year: int,
    model_name: str = "hier_delays",
    draws: int = 2000,
    tune: int = 1000,
    target_accept: float = 0.9,
    db_path: Path = DEFAULT_DB,
) -> HierarchicalDelayModel:
    """Train a hierarchical delay model on historical data.

    Parameters
    ----------
    start_year, end_year : int
        Year range for training data (inclusive)
    model_name : str
        Name for saved model file
    draws, tune : int
        MCMC sampling parameters
    target_accept : float
        NUTS target acceptance rate
    db_path : Path
        Path to flight database

    Returns
    -------
    HierarchicalDelayModel
        Fitted model
    """
    print(f"🎯 Training hierarchical delay model on {start_year}-{end_year} data...")

    # Load training data
    df = _load_training_data(start_year, end_year, db_path)

    if len(df) == 0:
        raise ValueError("No training data found for specified years")

    # Initialize and fit model
    model = HierarchicalDelayModel()
    model.fit(df, draws=draws, tune=tune, target_accept=target_accept)

    # Save model
    model_path = MODELS_DIR / f"{model_name}_{start_year}_{end_year}.pkl"
    model.save(model_path)

    return model


def load_hierarchical_model(model_path: Path | str) -> HierarchicalDelayModel:
    """Load a pre-trained hierarchical model."""
    return HierarchicalDelayModel.load(model_path)
