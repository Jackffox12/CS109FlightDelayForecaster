"""Bayesian online updating with a Beta prior and Bernoulli likelihood.

This module provides the BetaBinomialModel class, which supports sequential
updates given late/on-time observations and exposes predictive utilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import fsum
from pathlib import Path

from rich.pretty import Pretty
from scipy.stats import betabinom

__all__ = ["BetaBinomialModel"]


@dataclass
class BetaBinomialModel:
    """Conjugate Beta-Binomial model for flight delays.

    Parameters
    ----------
    alpha, beta
        Strictly positive shape parameters for the Beta prior. ``alpha`` counts
        late flights; ``beta`` counts on-time flights.
    """

    alpha: float
    beta: float

    def __post_init__(self) -> None:  # noqa: D401
        if self.alpha <= 0 or self.beta <= 0:
            raise ValueError("alpha and beta must be > 0")

    # ---------------------------------------------------------------------
    # Sequential update API
    # ---------------------------------------------------------------------
    def update(self, observation: int) -> None:
        """Update the posterior with a single observation.

        Parameters
        ----------
        observation
            ``1`` = late flight, ``0`` = on-time flight.
        """
        if observation not in (0, 1):
            raise ValueError("observation must be 0 (on-time) or 1 (late)")

        if observation == 1:
            self.alpha += 1
        else:
            self.beta += 1

    # ------------------------------------------------------------------
    # Predictive quantities
    # ------------------------------------------------------------------
    def predictive_p_on_time(self) -> float:
        """Return the posterior predictive probability that the *next* flight is **on-time**."""
        return self.beta / (self.alpha + self.beta)

    def predictive_cdf(self, k: int, n: int) -> float:  # noqa: D401
        """Cumulative probability of ≤ *k* late flights in the next *n* flights.

        This uses the Beta-Binomial distribution with current posterior
        parameters.
        """
        if k < 0 or n < 0 or k > n:
            raise ValueError("Require 0 ≤ k ≤ n")

        # scipy.stats.betabinom takes (n, a, b)
        return float(betabinom(n, self.alpha, self.beta).cdf(k))

    # ------------------------------------------------------------------
    # Pretty representation helpers
    # ------------------------------------------------------------------
    def __rich_repr__(self):  # noqa: D401
        yield "alpha", round(self.alpha, 3)
        yield "beta", round(self.beta, 3)
        yield "mean_late", round(self.alpha / (self.alpha + self.beta), 4)
        yield "mean_on_time", round(self.predictive_p_on_time(), 4)

    def __repr__(self) -> str:  # noqa: D401
        return f"BetaBinomialModel(alpha={self.alpha:.3f}, beta={self.beta:.3f})" 