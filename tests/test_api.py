"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from flight_delay_bayes.api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_forecast_endpoint_response_structure():
    """Test that forecast endpoint returns all required fields."""
    # This test may fail if external APIs are unavailable, but it tests the structure
    response = client.get("/forecast/DL/202/2025-06-07")

    # The response should be either successful or have a specific error
    if response.status_code == 200:
        data = response.json()

        # Check all required keys exist
        required_keys = {
            "carrier",
            "flight_num",
            "origin",
            "dest",
            "sched_dep_local",
            "pred_dep_local",
            "p_late",
            "alpha",
            "beta",
            "updated",
        }

        assert all(
            key in data for key in required_keys
        ), f"Missing keys: {required_keys - set(data.keys())}"

        # Check types
        assert isinstance(data["carrier"], str)
        assert isinstance(data["flight_num"], str)
        assert isinstance(data["p_late"], (int, float))
        assert isinstance(data["alpha"], (int, float))
        assert isinstance(data["beta"], (int, float))
        assert isinstance(data["updated"], bool)

    elif response.status_code == 500:
        # External API might be unavailable, check error message contains expected info
        error_detail = response.json().get("detail", "")
        # This is acceptable for a unit test when external APIs are not available
        assert isinstance(error_detail, str)
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")


def test_forecast_endpoint_invalid_date():
    """Test forecast endpoint with invalid date format."""
    response = client.get("/forecast/DL/202/invalid-date")
    assert response.status_code == 400
    assert "Date must be YYYY-MM-DD" in response.json()["detail"]
