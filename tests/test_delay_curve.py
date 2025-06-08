"""Tests for delay curve functionality."""

from datetime import datetime

import pytest

from flight_delay_bayes.bayes.delay_curve import (
    DelayPredictor,
    create_default_delay_curve,
)
from flight_delay_bayes.bayes.pipeline import _calculate_predicted_departure


def test_delay_predictor_basic():
    """Test basic delay predictor functionality."""
    curve_data = {
        "mean_ontime_delay": 2.0,
        "mean_late_delay": 25.0,
        "threshold_prob": 0.3,
    }

    predictor = DelayPredictor(curve_data)

    # Below threshold should return on-time delay
    assert predictor.predict_delay(0.1) == 2.0
    assert predictor.predict_delay(0.3) == 2.0

    # Above threshold should interpolate
    delay_at_50pct = predictor.predict_delay(0.5)
    assert delay_at_50pct > 2.0
    assert delay_at_50pct < 25.0

    # At maximum should return late delay
    assert predictor.predict_delay(1.0) == 25.0


def test_delay_predictor_edge_cases():
    """Test edge cases for delay predictor."""
    curve_data = create_default_delay_curve()
    predictor = DelayPredictor(curve_data)

    # Test boundary values
    assert predictor.predict_delay(0.0) >= 0
    assert predictor.predict_delay(1.0) >= 0

    # Test that delay increases with probability
    delay_low = predictor.predict_delay(0.1)
    delay_high = predictor.predict_delay(0.9)
    assert delay_high >= delay_low


def test_predicted_departure_never_earlier():
    """Test that predicted departure is never earlier than scheduled."""
    scheduled_times = [
        "2024-01-15T10:30:00-05:00",
        "2024-06-01T14:45:00+00:00",
        "2024-12-25T08:15:00-08:00",
    ]

    # Test with various expected delays
    delays = [0.0, 5.5, 15.2, 30.8, 60.0]

    for scheduled_str in scheduled_times:
        scheduled_dt = datetime.fromisoformat(scheduled_str.replace("Z", "+00:00"))

        for delay_min in delays:
            pred_dep_str = _calculate_predicted_departure(scheduled_str, delay_min)

            if pred_dep_str:  # None is acceptable for invalid inputs
                pred_dep_dt = datetime.fromisoformat(
                    pred_dep_str.replace("Z", "+00:00")
                )

                # Predicted departure should never be earlier than scheduled
                assert (
                    pred_dep_dt >= scheduled_dt
                ), f"Predicted {pred_dep_dt} is earlier than scheduled {scheduled_dt}"

                # The difference should be approximately the expected delay
                diff_minutes = (pred_dep_dt - scheduled_dt).total_seconds() / 60
                assert (
                    abs(diff_minutes - delay_min) < 0.1
                ), f"Expected delay {delay_min}, got {diff_minutes}"


def test_predicted_departure_invalid_inputs():
    """Test predicted departure with invalid inputs."""
    # None scheduled time
    assert _calculate_predicted_departure(None, 10.0) is None

    # Invalid time format
    assert _calculate_predicted_departure("invalid-time", 10.0) is None

    # Negative delay should be clamped to 0
    result = _calculate_predicted_departure("2024-01-15T10:30:00-05:00", -10.0)
    if result:
        scheduled_dt = datetime.fromisoformat("2024-01-15T10:30:00-05:00")
        pred_dt = datetime.fromisoformat(result)
        assert pred_dt == scheduled_dt  # No delay applied for negative input


def test_delay_curve_interpolation():
    """Test the piece-wise linear interpolation logic."""
    curve_data = {
        "mean_ontime_delay": 0.0,
        "mean_late_delay": 30.0,
        "threshold_prob": 0.4,
    }

    predictor = DelayPredictor(curve_data)

    # At threshold, should be at on-time delay
    assert predictor.predict_delay(0.4) == 0.0

    # Halfway between threshold and 1.0 should be halfway between delays
    midpoint_prob = 0.4 + (1.0 - 0.4) / 2  # 0.7
    expected_delay = 0.0 + 0.5 * (30.0 - 0.0)  # 15.0
    assert abs(predictor.predict_delay(midpoint_prob) - expected_delay) < 0.01

    # Just above threshold should be very close to on-time delay
    assert predictor.predict_delay(0.41) < 1.0


if __name__ == "__main__":
    pytest.main([__file__])
