"""Pipeline to forecast probability of flight being late using priors and real-time status."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict

from flight_delay_bayes.bayes.prior_estimator import compute_beta_prior
from flight_delay_bayes.bayes.updater import BetaBinomialModel
from flight_delay_bayes.realtime.aviationstack import get_flight_status

__all__ = ["forecast_probability"]


async def _get_status_async(
    carrier: str, flight_number: str, dep_date: date
) -> Dict[str, Any]:  # noqa: D401
    # run blocking IO in thread
    return await asyncio.to_thread(get_flight_status, carrier, flight_number, dep_date)


async def forecast_probability(
    flight_iata: str, flight_num: str, dep_date: date
) -> dict[str, Any]:  # noqa: D401
    """Forecast probability that the given flight will be late (>15 min).

    Parameters
    ----------
    flight_iata
        Airline IATA code (e.g. ``"DL"``).
    flight_num
        Numeric flight number as string (e.g. ``"202"``).
    dep_date
        Scheduled departure date (local) in ``date`` object.

    """
    # 1. Real-time status ----------------------------------------------------
    status_info = await _get_status_async(flight_iata, flight_num, dep_date)
    origin = status_info.get("origin")
    dest = status_info.get("dest")
    carrier = flight_iata

    if not origin or not dest:
        raise RuntimeError(
            "Aviationstack response missing origin/destination IATA codes"
        )

    # 2. Prior from historic data -------------------------------------------
    alpha, beta, n = compute_beta_prior(carrier, origin, dest)

    model = BetaBinomialModel(alpha, beta)

    # 3. Optional posterior update ------------------------------------------
    updated = False
    status = status_info.get("status")
    delay_min = status_info.get("delay_minutes")
    if status in {"active", "landed"} and delay_min is not None:
        observation = int(delay_min > 15)
        model.update(observation)
        updated = True

    # 4. Prepare result ------------------------------------------------------
    p_late = 1.0 - model.predictive_p_on_time()
    return {
        "p_late": p_late,
        "alpha": model.alpha,
        "beta": model.beta,
        "updated": updated,
        "origin": origin,
        "dest": dest,
        "status": status,
        "carrier": carrier,
        "flight_num": flight_num,
        "scheduled_dep": status_info.get("scheduled_dep"),
    }
