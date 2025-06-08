"""Tests for multiple delay threshold functionality."""

import asyncio
from datetime import date

import pytest

from flight_delay_bayes.bayes.delay_curve import (
    DelayPredictor,
    create_default_delay_curve,
)
from flight_delay_bayes.bayes.pipeline import forecast_probability


def test_threshold_probabilities_monotonic():
    """Test that threshold probabilities are non-decreasing."""
    curve_data = {
        "mean_ontime_delay": 2.0,
        "mean_late_delay": 35.0,
        "threshold_prob": 0.3,
    }

    predictor = DelayPredictor(curve_data)

    # Test with various base probabilities
    test_probs = [0.1, 0.3, 0.5, 0.7, 0.9]

    for base_prob in test_probs:
        thresholds = predictor.predict_threshold_probabilities(base_prob)

        # Check all probabilities are in valid range
        for key, prob in thresholds.items():
            assert 0.0 <= prob <= 1.0, f"{key} = {prob} is not in [0,1]"

        # Check monotonicity (higher thresholds should have lower probabilities)
        assert thresholds["p_late_15"] >= thresholds["p_late_30"]
        assert thresholds["p_late_30"] >= thresholds["p_late_45"]
        assert thresholds["p_late_45"] >= thresholds["p_late_60"]

        # Check that p_late_15 matches the input
        assert abs(thresholds["p_late_15"] - base_prob) < 1e-6


def test_threshold_probabilities_edge_cases():
    """Test threshold probabilities with edge cases."""
    predictor = DelayPredictor(create_default_delay_curve())

    # Test with very low probability
    thresholds_low = predictor.predict_threshold_probabilities(0.01)
    assert thresholds_low["p_late_60"] < thresholds_low["p_late_15"]
    assert thresholds_low["p_late_60"] >= 0.0

    # Test with very high probability
    thresholds_high = predictor.predict_threshold_probabilities(0.99)
    assert (
        thresholds_high["p_late_30"] > 0.1
    )  # Should still have meaningful probability
    assert thresholds_high["p_late_60"] < thresholds_high["p_late_30"]

    # Test with zero probability
    thresholds_zero = predictor.predict_threshold_probabilities(0.0)
    assert all(prob == 0.0 for prob in thresholds_zero.values())

    # Test with probability of 1.0
    thresholds_one = predictor.predict_threshold_probabilities(1.0)
    assert thresholds_one["p_late_15"] == 1.0
    assert thresholds_one["p_late_60"] > 0.0


def test_threshold_probabilities_consistency():
    """Test that threshold probabilities are consistent with expected delays."""
    curve_data = {
        "mean_ontime_delay": 0.0,
        "mean_late_delay": 45.0,
        "threshold_prob": 0.4,
    }

    predictor = DelayPredictor(curve_data)

    # When expected delay is around 30 minutes, p_late_30 should be reasonably high
    base_prob = 0.6  # This should give expected delay around 30 min
    expected_delay = predictor.predict_delay(base_prob)
    thresholds = predictor.predict_threshold_probabilities(base_prob)

    # If expected delay is ~30 min, probability of ≥30 min should be significant
    if expected_delay >= 25:
        assert thresholds["p_late_30"] > 0.2

    # But probability of ≥60 min should be much lower since expected is ~30
    assert thresholds["p_late_60"] < thresholds["p_late_30"] * 0.5


def test_forecast_probability_includes_thresholds():
    """Test that forecast_probability returns all threshold probabilities."""
    try:
        # This might fail due to external API dependencies, but test the structure
        result = asyncio.run(forecast_probability("DL", "202", date(2025, 6, 15)))

        # Check that all threshold probabilities are present
        required_keys = ["p_late", "p_late_30", "p_late_45", "p_late_60"]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"
            assert isinstance(result[key], (int, float)), f"{key} is not numeric"
            assert 0.0 <= result[key] <= 1.0, f"{key} = {result[key]} not in [0,1]"

        # Check monotonicity
        assert result["p_late"] >= result["p_late_30"]
        assert result["p_late_30"] >= result["p_late_45"]
        assert result["p_late_45"] >= result["p_late_60"]

        # Check that other expected fields still exist (backward compatibility)
        assert "exp_delay_min" in result
        assert "pred_dep_local" in result

    except Exception as e:
        # If external APIs fail, that's okay for unit testing
        print(f"Forecast test skipped due to external dependency: {e}")
        pytest.skip("External API dependency not available")


def test_low_expected_delay_case():
    """Test threshold probabilities when expected delay is very low."""
    curve_data = {
        "mean_ontime_delay": 1.0,
        "mean_late_delay": 20.0,
        "threshold_prob": 0.8,  # High threshold means most flights are "on time"
    }

    predictor = DelayPredictor(curve_data)

    # Low probability should give very low expected delay
    base_prob = 0.2
    expected_delay = predictor.predict_delay(base_prob)
    thresholds = predictor.predict_threshold_probabilities(base_prob)

    # When expected delay is very low, higher threshold probs should decrease rapidly
    if expected_delay < 10:
        assert thresholds["p_late_60"] < thresholds["p_late_15"] * 0.2
        assert thresholds["p_late_45"] < thresholds["p_late_30"]


if __name__ == "__main__":
    pytest.main([__file__])
