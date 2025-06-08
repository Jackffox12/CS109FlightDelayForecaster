"""Backtesting utility for historic flight probability forecasts."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Tuple

import duckdb
import numpy as np

from flight_delay_bayes.bayes.prior_estimator import compute_beta_prior
from flight_delay_bayes.bayes.updater import BetaBinomialModel

DEFAULT_DB = Path("data/flights.duckdb")


def _fetch_flights(
    carrier: str, origin: str, dest: str, year: int, db_path: Path | str = DEFAULT_DB
):
    # Handle missing database file
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    
    query = (
        "SELECT flight_date, late FROM historic_flights "
        "WHERE carrier = ? AND origin = ? AND dest = ? AND strftime('%Y', flight_date) = ? "
        "ORDER BY flight_date"
    )
    try:
        with duckdb.connect(str(db_path)) as conn:
            return conn.execute(query, (carrier, origin, dest, str(year))).fetchall()
    except (duckdb.IOException, duckdb.CatalogException):
        # Database exists but can't be opened or table doesn't exist
        return []


def brier_score(pred: np.ndarray, truth: np.ndarray) -> float:
    return float(np.mean((pred - truth) ** 2))


def reliability_curve(pred: np.ndarray, truth: np.ndarray, bins: int = 10):
    bin_edges = np.linspace(0, 1, bins + 1)
    bucket_pred = np.digitize(pred, bin_edges, right=True) - 1  # 0-indexed
    out = []
    for i in range(bins):
        mask = bucket_pred == i
        if mask.any():
            out.append(
                (
                    (bin_edges[i] + bin_edges[i + 1]) / 2,
                    float(np.mean(pred[mask])),
                    float(np.mean(truth[mask])),
                    int(mask.sum()),
                )
            )
    return out


def run_backtest(
    carrier: str,
    origin: str,
    dest: str,
    year: int,
    db_path: Path | str = DEFAULT_DB,
):
    rows = _fetch_flights(carrier, origin, dest, year, db_path)
    if not rows:
        raise ValueError("No flights found for specified criteria.")

    alpha0, beta0, _ = compute_beta_prior(carrier, origin, dest, db_path)
    model = BetaBinomialModel(alpha0, beta0)

    preds = []
    truths = []

    for flight_date, late in rows:
        p_on_time = model.predictive_p_on_time()
        preds.append(1 - p_on_time)
        truths.append(int(late))
        model.update(int(late))

    pred_arr = np.array(preds, dtype=float)
    truth_arr = np.array(truths, dtype=float)

    bs = brier_score(pred_arr, truth_arr)
    mean_pred = float(pred_arr.mean())
    actual_rate = float(truth_arr.mean())
    bias = mean_pred - actual_rate

    buckets = reliability_curve(pred_arr, truth_arr)

    return {
        "n": len(rows),
        "actual_rate": actual_rate,
        "mean_pred": mean_pred,
        "brier": bs,
        "bias": bias,
        "buckets": buckets,
    } 