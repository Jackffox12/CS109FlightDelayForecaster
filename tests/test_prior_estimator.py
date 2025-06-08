"""Tests for compute_beta_prior."""

from pathlib import Path

import duckdb

from flight_delay_bayes.bayes.prior_estimator import compute_beta_prior


def test_beta_prior_empty(tmp_path: Path) -> None:
    """When no data is present, Jeffreys prior should be returned."""
    db_path = tmp_path / "test.duckdb"

    # Create empty table with schema.
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE historic_flights (
                flight_date DATE,
                carrier VARCHAR,
                origin VARCHAR,
                dest VARCHAR,
                dep_hour INTEGER,
                late BOOLEAN
            );
            """
        )

    alpha, beta, n = compute_beta_prior("DL", "SFO", "JFK", db_path)
    assert (alpha, beta, n) == (0.5, 0.5, 0)


def test_beta_prior_no_database(tmp_path: Path) -> None:
    """When database file doesn't exist, Jeffreys prior should be returned."""
    db_path = tmp_path / "nonexistent.duckdb"
    # Don't create the file

    alpha, beta, n = compute_beta_prior("DL", "SFO", "JFK", db_path)
    assert (alpha, beta, n) == (0.5, 0.5, 0)
