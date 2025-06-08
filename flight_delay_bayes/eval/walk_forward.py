"""Walk-forward validation framework for comparing hierarchical vs baseline models."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score

from ..bayes.hier_model import HierarchicalDelayModel
from ..bayes.prior_estimator import compute_beta_prior
from ..bayes.updater import BetaBinomialModel
from .backtest import brier_score

__all__ = ["WalkForwardValidator", "run_walk_forward_validation"]

DEFAULT_DB = Path("data/flights.duckdb")


class WalkForwardValidator:
    """Walk-forward validation for flight delay models with expanding windows."""

    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.results: List[Dict[str, Any]] = []

    def _load_data(self, start_year: int, end_year: int) -> pd.DataFrame:
        """Load flight data for specified year range."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        query = """
            SELECT 
                f.carrier,
                f.origin, 
                f.dest,
                f.dep_hour,
                f.late,
                f.flight_date,
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
              AND f.carrier IS NOT NULL
              AND f.origin IS NOT NULL
              AND f.dest IS NOT NULL
        """

        with duckdb.connect(str(self.db_path)) as conn:
            df = conn.execute(query, (start_year, end_year)).fetch_df()

        return df

    def _expected_calibration_error(
        self, y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
    ) -> float:
        """Compute Expected Calibration Error (ECE) with n bins."""
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]

        ece = 0.0
        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
            # Find predictions in this bin
            in_bin = (y_prob > bin_lower) & (y_prob <= bin_upper)
            prop_in_bin = in_bin.mean()

            if prop_in_bin > 0:
                # Accuracy in this bin
                accuracy_in_bin = y_true[in_bin].mean()
                # Average confidence in this bin
                avg_confidence_in_bin = y_prob[in_bin].mean()
                # Add weighted difference to ECE
                ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

        return ece

    def _compute_threshold_metrics(
        self, y_true: np.ndarray, predictions_15: np.ndarray, delay_minutes: np.ndarray
    ) -> Dict[str, float]:
        """Compute Brier scores for multiple delay thresholds."""
        # Create true labels for different thresholds
        y_true_30 = (delay_minutes >= 30).astype(int)
        y_true_45 = (delay_minutes >= 45).astype(int)
        y_true_60 = (delay_minutes >= 60).astype(int)

        # For baseline model, approximate other thresholds based on 15-min predictions
        # This is a simplified approach - in a full implementation, we'd train separate models
        predictions_30 = predictions_15 * 0.6  # Rough approximation
        predictions_45 = predictions_15 * 0.4
        predictions_60 = predictions_15 * 0.25

        # Compute Brier scores for each threshold
        brier_15 = brier_score(predictions_15, y_true.astype(int))
        brier_30 = brier_score(predictions_30, y_true_30) if len(y_true_30) > 0 else 1.0
        brier_45 = brier_score(predictions_45, y_true_45) if len(y_true_45) > 0 else 1.0
        brier_60 = brier_score(predictions_60, y_true_60) if len(y_true_60) > 0 else 1.0

        return {
            "brier_15": brier_15,
            "brier_30": brier_30,
            "brier_45": brier_45,
            "brier_60": brier_60,
        }

    def _evaluate_baseline_model(
        self, train_df: pd.DataFrame, test_df: pd.DataFrame
    ) -> Dict[str, float]:
        """Evaluate baseline Beta-Binomial model with route priors."""
        print("  📈 Training baseline Beta-Binomial model...")

        # Get unique routes in test set
        test_routes = test_df[["carrier", "origin", "dest"]].drop_duplicates()

        predictions = []
        true_labels = []
        delay_minutes = []

        for _, route in test_routes.iterrows():
            carrier, origin, dest = route["carrier"], route["origin"], route["dest"]

            # Get route-specific test data
            route_test = test_df[
                (test_df["carrier"] == carrier)
                & (test_df["origin"] == origin)
                & (test_df["dest"] == dest)
            ].copy()

            if len(route_test) == 0:
                continue

            # Compute prior from training data
            alpha, beta, n = compute_beta_prior(carrier, origin, dest, self.db_path)
            model = BetaBinomialModel(alpha, beta)

            # Sequential prediction with online updating
            route_test = route_test.sort_values("flight_date")

            for _, flight in route_test.iterrows():
                # Predict before updating
                p_late = 1.0 - model.predictive_p_on_time()
                predictions.append(p_late)
                true_labels.append(int(flight["late"]))

                # Get actual delay minutes (or estimate from late flag)
                actual_delay = flight.get(
                    "dep_delay_minutes", 20 if flight["late"] else 0
                )
                delay_minutes.append(actual_delay)

                # Update model with observation
                model.update(int(flight["late"]))

        if len(predictions) == 0:
            return {"brier": 1.0, "log_loss": 10.0, "auc": 0.5, "ece": 1.0}

        y_true = np.array(true_labels)
        y_pred = np.array(predictions)
        delay_mins = np.array(delay_minutes)

        # Clip probabilities to avoid log(0)
        y_pred_clipped = np.clip(y_pred, 1e-15, 1 - 1e-15)

        try:
            auc = roc_auc_score(y_true, y_pred) if len(np.unique(y_true)) > 1 else 0.5
        except ValueError:
            auc = 0.5

        try:
            logloss = log_loss(y_true, y_pred_clipped)
        except ValueError:
            logloss = 10.0

        # Compute threshold metrics
        threshold_metrics = self._compute_threshold_metrics(y_true, y_pred, delay_mins)

        metrics = {
            "brier": brier_score(y_pred, y_true),
            "log_loss": logloss,
            "auc": auc,
            "ece": self._expected_calibration_error(y_true, y_pred),
            **threshold_metrics,  # Add threshold-specific Brier scores
        }

        print(
            f"    Baseline metrics: Brier(15min)={metrics['brier']:.4f}, Brier(30min)={metrics['brier_30']:.4f}, AUC={metrics['auc']:.4f}"
        )
        return metrics

    def _evaluate_hierarchical_model(
        self, train_df: pd.DataFrame, test_df: pd.DataFrame, fold_name: str
    ) -> Dict[str, float]:
        """Evaluate hierarchical model."""
        print("  🧠 Training hierarchical model...")

        try:
            # Train hierarchical model on training data
            model = HierarchicalDelayModel()

            # Use reduced sampling for faster evaluation
            model.fit(train_df, draws=500, tune=250, target_accept=0.85)

            # Prepare test data for prediction
            test_clean = model._prepare_data(test_df, for_prediction=True)

            # Get predictions
            print("  🔮 Generating predictions...")
            y_pred = model.predict(test_clean, return_mean=True)
            y_true = (
                test_clean["late"].values
                if "late" in test_clean.columns
                else test_df["late"].values
            )

            # Ensure arrays are aligned
            if len(y_pred) != len(y_true):
                min_len = min(len(y_pred), len(y_true))
                y_pred = y_pred[:min_len]
                y_true = y_true[:min_len]

            # Clip probabilities
            y_pred_clipped = np.clip(y_pred, 1e-15, 1 - 1e-15)

            try:
                auc = (
                    roc_auc_score(y_true, y_pred) if len(np.unique(y_true)) > 1 else 0.5
                )
            except ValueError:
                auc = 0.5

            try:
                logloss = log_loss(y_true, y_pred_clipped)
            except ValueError:
                logloss = 10.0

            metrics = {
                "brier": brier_score(y_pred, y_true),
                "log_loss": logloss,
                "auc": auc,
                "ece": self._expected_calibration_error(y_true, y_pred),
            }

            print(
                f"    Hierarchical metrics: Brier={metrics['brier']:.4f}, AUC={metrics['auc']:.4f}"
            )
            return metrics

        except Exception as e:
            print(f"    ⚠️ Hierarchical model failed: {e}")
            # Return poor metrics if training fails
            return {"brier": 1.0, "log_loss": 10.0, "auc": 0.5, "ece": 1.0}

    def run_fold(
        self, train_start: int, train_end: int, test_year: int
    ) -> Dict[str, Any]:
        """Run a single fold of walk-forward validation."""
        print(f"\n🔄 Fold: Train {train_start}-{train_end} → Test {test_year}")

        # Load data
        print(f"  📊 Loading training data ({train_start}-{train_end})...")
        train_df = self._load_data(train_start, train_end)

        print(f"  📊 Loading test data ({test_year})...")
        test_df = self._load_data(test_year, test_year)

        if len(train_df) == 0:
            print("  ❌ No training data found")
            return None

        if len(test_df) == 0:
            print("  ❌ No test data found")
            return None

        print(f"  📈 Training set: {len(train_df):,} flights")
        print(f"  📊 Test set: {len(test_df):,} flights")

        # Evaluate baseline model
        baseline_start = time.time()
        baseline_metrics = self._evaluate_baseline_model(train_df, test_df)
        baseline_time = time.time() - baseline_start

        # Evaluate hierarchical model
        hier_start = time.time()
        hier_metrics = self._evaluate_hierarchical_model(
            train_df, test_df, f"{train_start}_{train_end}_{test_year}"
        )
        hier_time = time.time() - hier_start

        # Compile results
        result = {
            "train_start": train_start,
            "train_end": train_end,
            "test_year": test_year,
            "train_size": len(train_df),
            "test_size": len(test_df),
            "baseline_brier": baseline_metrics["brier"],
            "baseline_log_loss": baseline_metrics["log_loss"],
            "baseline_auc": baseline_metrics["auc"],
            "baseline_ece": baseline_metrics["ece"],
            "hier_brier": hier_metrics["brier"],
            "hier_log_loss": hier_metrics["log_loss"],
            "hier_auc": hier_metrics["auc"],
            "hier_ece": hier_metrics["ece"],
            "baseline_time": baseline_time,
            "hier_time": hier_time,
            "brier_improvement": baseline_metrics["brier"] - hier_metrics["brier"],
            "hier_wins": hier_metrics["brier"] < baseline_metrics["brier"],
        }

        print(f"  ✅ Fold complete: Hier wins = {result['hier_wins']}")
        print(f"     Brier improvement: {result['brier_improvement']:+.4f}")

        return result

    def run_validation(
        self, start_year: int = 2019, end_year: int = 2023
    ) -> pd.DataFrame:
        """Run full walk-forward validation."""
        print(f"🚀 Starting walk-forward validation ({start_year}-{end_year})")

        results = []

        for test_year in range(start_year, end_year + 1):
            # Expanding window: train on all data before test year
            train_start = start_year - 4  # Go back 4 years for training data
            train_end = test_year - 1

            if train_end < train_start:
                print(f"⚠️ Skipping {test_year}: insufficient training data")
                continue

            result = self.run_fold(train_start, train_end, test_year)
            if result is not None:
                results.append(result)

        if not results:
            raise ValueError("No valid folds completed")

        results_df = pd.DataFrame(results)
        self.results = results

        return results_df


def run_walk_forward_validation(
    start_year: int = 2019, end_year: int = 2023, db_path: Path | str = DEFAULT_DB
) -> pd.DataFrame:
    """Run walk-forward validation and return results."""
    validator = WalkForwardValidator(db_path)
    return validator.run_validation(start_year, end_year)


def print_validation_summary(results_df: pd.DataFrame) -> None:
    """Print a summary of validation results."""
    if len(results_df) == 0:
        print("❌ No results to summarize")
        return

    print("\n" + "=" * 80)
    print("📊 WALK-FORWARD VALIDATION RESULTS")
    print("=" * 80)

    # Per-fold results
    print("\n📋 Per-Fold Results:")
    print("-" * 100)
    print(
        f"{'Year':<6} {'Train Size':<12} {'Test Size':<11} {'Baseline':<20} {'Hierarchical':<20} {'Improvement':<12} {'Winner'}"
    )
    print("-" * 100)

    for _, row in results_df.iterrows():
        baseline_str = f"{row['baseline_brier']:.4f}"
        hier_str = f"{row['hier_brier']:.4f}"
        improvement = f"{row['brier_improvement']:+.4f}"
        winner = "🧠 Hier" if row["hier_wins"] else "📈 Base"

        print(
            f"{row['test_year']:<6} {row['train_size']:<12,} {row['test_size']:<11,} "
            f"{baseline_str:<20} {hier_str:<20} {improvement:<12} {winner}"
        )

    # Aggregate statistics
    print("\n📈 Aggregate Results:")
    print("-" * 50)

    # Means
    base_brier_mean = results_df["baseline_brier"].mean()
    hier_brier_mean = results_df["hier_brier"].mean()
    brier_improvement_mean = results_df["brier_improvement"].mean()

    base_auc_mean = results_df["baseline_auc"].mean()
    hier_auc_mean = results_df["hier_auc"].mean()

    base_ece_mean = results_df["baseline_ece"].mean()
    hier_ece_mean = results_df["hier_ece"].mean()

    wins = results_df["hier_wins"].sum()
    total_folds = len(results_df)

    print(f"Baseline Brier (mean):     {base_brier_mean:.4f}")
    print(f"Hierarchical Brier (mean): {hier_brier_mean:.4f}")
    print(f"Improvement (mean):        {brier_improvement_mean:+.4f}")
    print("")
    print(f"Baseline AUC (mean):       {base_auc_mean:.4f}")
    print(f"Hierarchical AUC (mean):   {hier_auc_mean:.4f}")
    print("")
    print(f"Baseline ECE (mean):       {base_ece_mean:.4f}")
    print(f"Hierarchical ECE (mean):   {hier_ece_mean:.4f}")
    print("")
    print(f"Hierarchical wins:         {wins}/{total_folds} folds")
    print(f"Win rate:                  {wins/total_folds*100:.1f}%")

    # Check acceptance criteria
    print("\n🎯 Acceptance Criteria:")
    print("-" * 30)
    brier_ok = hier_brier_mean <= 0.125
    wins_ok = wins >= max(1, int(0.8 * total_folds))  # At least 80% of folds

    print(
        f"Hier Brier ≤ 0.125:       {'✅' if brier_ok else '❌'} ({hier_brier_mean:.4f})"
    )
    print(
        f"Wins ≥ 80% folds:         {'✅' if wins_ok else '❌'} ({wins}/{total_folds})"
    )

    overall_pass = brier_ok and wins_ok
    print(f"\nOVERALL RESULT:            {'✅ PASS' if overall_pass else '❌ FAIL'}")

    if overall_pass:
        print("\n🎉 Hierarchical model successfully beats baseline out-of-sample!")
    else:
        print("\n💥 Hierarchical model does not meet acceptance criteria.")
