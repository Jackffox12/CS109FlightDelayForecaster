"""Tests for walk-forward validation."""

import numpy as np
import pandas as pd
import pytest

from flight_delay_bayes.eval.walk_forward import (
    WalkForwardValidator,
    print_validation_summary,
)


def test_expected_calibration_error():
    """Test ECE calculation."""
    validator = WalkForwardValidator()

    # Perfect calibration
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.1, 0.9, 0.9])  # Use values slightly away from 0/1
    ece = validator._expected_calibration_error(y_true, y_prob, n_bins=2)
    assert ece < 0.2  # Should be low for well-calibrated predictions

    # Poor calibration
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.9, 0.9, 0.1, 0.1])  # Completely wrong
    ece = validator._expected_calibration_error(y_true, y_prob, n_bins=2)
    assert ece >= 0.5  # Should be high for poorly calibrated predictions


def test_validation_summary_empty():
    """Test summary with empty results."""
    empty_df = pd.DataFrame()
    # Should not crash
    print_validation_summary(empty_df)


def test_validation_summary_with_data():
    """Test summary with sample data."""
    # Create sample results
    results_df = pd.DataFrame(
        {
            "test_year": [2019, 2020, 2021],
            "train_size": [1000, 1500, 2000],
            "test_size": [300, 400, 500],
            "baseline_brier": [0.250, 0.245, 0.240],
            "hier_brier": [0.120, 0.115, 0.110],
            "baseline_auc": [0.60, 0.62, 0.65],
            "hier_auc": [0.72, 0.75, 0.78],
            "baseline_ece": [0.15, 0.14, 0.13],
            "hier_ece": [0.08, 0.07, 0.06],
            "brier_improvement": [0.130, 0.130, 0.130],
            "hier_wins": [True, True, True],
        }
    )

    # Should not crash and show acceptance criteria
    print_validation_summary(results_df)


def test_metrics_edge_cases():
    """Test metric calculation with edge cases."""
    validator = WalkForwardValidator()

    # Test with all same predictions
    y_true = np.array([0, 1, 0, 1])
    y_prob = np.array([0.5, 0.5, 0.5, 0.5])
    ece = validator._expected_calibration_error(y_true, y_prob)
    assert 0 <= ece <= 1

    # Test with extreme values (single prediction)
    y_true = np.array([1])
    y_prob = np.array([0.1])  # Low confidence, but true label is 1
    ece = validator._expected_calibration_error(y_true, y_prob)
    assert 0 <= ece <= 1  # Should be between 0 and 1


if __name__ == "__main__":
    pytest.main([__file__])
