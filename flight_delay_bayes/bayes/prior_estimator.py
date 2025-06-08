"""Bayesian prior estimation utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import duckdb

DEFAULT_DB_PATH = Path("data/flights.duckdb")


def _query_counts(
    carrier: str, origin: str, dest: str, conn: duckdb.DuckDBPyConnection
) -> tuple[int, int]:
    """Return total (n) and late (k) counts for the given route."""
    try:
        result = conn.execute(
            """
            SELECT count(*)                           AS n,
                   sum(CASE WHEN late THEN 1 ELSE 0 END) AS k
            FROM historic_flights
            WHERE carrier = ? AND origin = ? AND dest = ?
            """,
            (carrier, origin, dest),
        ).fetchone()
    except duckdb.CatalogException:
        # Table does not exist yet.
        return 0, 0

    n: int = result[0] or 0
    k: int = result[1] or 0
    return n, k


def compute_beta_prior(
    carrier: str,
    origin: str,
    dest: str,
    db_path: str | Path | None = None,
) -> tuple[float, float, int]:
    """Compute Jeffreys-based Beta prior parameters for a given flight route.

    Parameters
    ----------
    carrier, origin, dest
        Identifiers to filter historic flights.
    db_path
        Path to the DuckDB database. Defaults to ``data/flights.duckdb`` if not
        provided.

    Returns
    -------
    alpha, beta, n
        The alpha and beta parameters for the Beta prior, and the number of
        matched rows.
    """
    db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    # If database file doesn't exist, return Jeffreys prior
    if not db_path.exists():
        alpha0 = 0.5
        beta0 = 0.5
        return alpha0, beta0, 0

    try:
        with duckdb.connect(str(db_path)) as conn:
            n, k = _query_counts(carrier, origin, dest, conn)
    except duckdb.IOException:
        # Database file exists but can't be opened
        alpha0 = 0.5
        beta0 = 0.5
        return alpha0, beta0, 0

    alpha0 = 0.5
    beta0 = 0.5
    alpha = alpha0 + k
    beta = beta0 + (n - k)
    return alpha, beta, n 