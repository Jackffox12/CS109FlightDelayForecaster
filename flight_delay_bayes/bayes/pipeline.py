"""Pipeline to forecast probability of flight being late using priors and real-time status."""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from flight_delay_bayes.bayes.hier_online import OnlineHierarchicalUpdater
from flight_delay_bayes.bayes.prior_estimator import compute_beta_prior
from flight_delay_bayes.bayes.updater import BetaBinomialModel
from flight_delay_bayes.realtime.aviationstack import get_flight_status
from flight_delay_bayes.realtime.noaa_gridpoint import get_weather_for_flight

# Airport coordinates for weather lookups (subset of major airports)
AIRPORT_COORDS = {
    "ATL": (33.6367, -84.4281),
    "LAX": (33.9425, -118.4081),
    "ORD": (41.9786, -87.9048),
    "DFW": (32.8968, -97.0380),
    "DEN": (39.8561, -104.6737),
    "JFK": (40.6413, -73.7781),
    "SFO": (37.6213, -122.3790),
    "LAS": (36.0840, -115.1537),
    "SEA": (47.4502, -122.3088),
    "CLT": (35.2144, -80.9473),
    "MIA": (25.7959, -80.2870),
    "PHX": (33.4343, -112.0112),
    "IAH": (29.9902, -95.3368),
    "MCO": (28.4312, -81.3081),
    "EWR": (40.6895, -74.1745),
    "MSP": (44.8848, -93.2223),
    "BOS": (42.3656, -71.0096),
    "DTW": (42.2162, -83.3554),
    "PHL": (39.8744, -75.2424),
    "LGA": (40.7769, -73.8740),
    "DCA": (38.8512, -77.0402),
    "IAD": (38.9531, -77.4565),
    "BWI": (39.1754, -76.6683),
    "MDW": (41.7868, -87.7522),
    "SLC": (40.7899, -111.9791),
    "PDX": (45.5898, -122.5951),
    "SAN": (32.7338, -117.1933),
    "TPA": (27.9755, -82.5332),
    "STL": (38.7487, -90.3700),
    "CVG": (39.0488, -84.6678),
}

# Default hierarchical model path (if available)
DEFAULT_HIER_MODEL = Path("models/hier_delays_2023_2023_2023.pkl")

# Global online updater instance (initialized lazily)
_online_updater: Optional["OnlineHierarchicalUpdater"] = None

__all__ = ["forecast_probability"]


async def _get_status_async(
    carrier: str, flight_number: str, dep_date: date
) -> Dict[str, Any]:  # noqa: D401
    # run blocking IO in thread
    return await asyncio.to_thread(get_flight_status, carrier, flight_number, dep_date)


async def _get_weather_async(
    airport: str, scheduled_dep: datetime | None
) -> Dict[str, Any]:
    """Get weather data for airport/time if available."""
    if not airport or not scheduled_dep or airport not in AIRPORT_COORDS:
        return {
            "wx_temp_c": None,
            "wx_wind_kt": None,
            "wx_precip_mm": None,
            "wx_conditions": None,
            "wx_valid_time": None,
        }

    try:
        lat, lng = AIRPORT_COORDS[airport]
        weather = await get_weather_for_flight(lat, lng, scheduled_dep)
        return weather
    except Exception:
        # Return null values if weather fetch fails
        return {
            "wx_temp_c": None,
            "wx_wind_kt": None,
            "wx_precip_mm": None,
            "wx_conditions": None,
            "wx_valid_time": None,
        }


def _get_online_updater() -> Optional["OnlineHierarchicalUpdater"]:
    """Get or create the global online updater instance."""
    global _online_updater

    if _online_updater is None:
        # Try to load the hierarchical model
        if DEFAULT_HIER_MODEL.exists():
            try:
                from .hier_online import create_online_updater

                _online_updater = create_online_updater(DEFAULT_HIER_MODEL)
                print(f"📊 Loaded hierarchical model: {DEFAULT_HIER_MODEL}")
            except Exception as e:
                print(f"⚠️  Failed to load hierarchical model: {e}")
                _online_updater = None
        else:
            print(f"📭 No hierarchical model found at {DEFAULT_HIER_MODEL}")

    return _online_updater


def _extract_dep_hour(scheduled_dep_str: str) -> Optional[int]:
    """Extract departure hour from scheduled departure string."""
    if not scheduled_dep_str:
        return None

    try:
        scheduled_dep_dt = datetime.fromisoformat(
            scheduled_dep_str.replace("Z", "+00:00")
        )
        return scheduled_dep_dt.hour
    except ValueError:
        return None


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

    # 2. Weather data -------------------------------------------------------
    scheduled_dep_str = status_info.get("scheduled_dep")
    scheduled_dep_dt = None
    if scheduled_dep_str:
        try:
            scheduled_dep_dt = datetime.fromisoformat(
                scheduled_dep_str.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    weather_data = await _get_weather_async(origin, scheduled_dep_dt)

    # 3. Try hierarchical model first ----------------------------------------
    online_updater = _get_online_updater()
    dep_hour = _extract_dep_hour(status_info.get("scheduled_dep"))

    p_late = None
    hier_updated = False
    update_time_ms = 0.0

    if online_updater and dep_hour is not None:
        try:
            # Get real-time observation if available
            status = status_info.get("status")
            delay_min = status_info.get("delay_minutes")

            if status in {"active", "landed"} and delay_min is not None:
                # We have live observation - use fast conjugate update for speed
                observation = delay_min > 15

                # Prepare data for fast update
                import pandas as pd

                update_data = pd.DataFrame(
                    {
                        "carrier": [carrier],
                        "origin": [origin],
                        "dest": [dest],
                        "dep_hour": [dep_hour],
                        "late": [int(observation)],
                        "wx_temp_c": [weather_data.get("wx_temp_c") or 0.0],
                        "wx_wind_kt": [weather_data.get("wx_wind_kt") or 0.0],
                        "wx_precip_mm": [weather_data.get("wx_precip_mm") or 0.0],
                    }
                )
                update_data["route"] = f"{carrier}:{origin}:{dest}"

                # Use fast conjugate update for live scenarios (≤150ms requirement)
                start_time = time.time()
                p_late = online_updater._conjugate_update(update_data)
                update_time_ms = (time.time() - start_time) * 1000
                hier_updated = True
                print(f"🚀 Fast hierarchical update: {update_time_ms:.1f}ms")
            else:
                # No live observation - use prediction only
                p_late = online_updater.predict(
                    carrier=carrier,
                    origin=origin,
                    dest=dest,
                    dep_hour=dep_hour,
                    wx_temp_c=weather_data.get("wx_temp_c"),
                    wx_wind_kt=weather_data.get("wx_wind_kt"),
                    wx_precip_mm=weather_data.get("wx_precip_mm"),
                )
                print("📊 Used hierarchical prediction")

        except Exception as e:
            print(f"⚠️  Hierarchical model failed: {e}")
            p_late = None

    # 4. Fallback to Beta-Binomial if hierarchical failed -------------------
    if p_late is None:
        print("📈 Falling back to Beta-Binomial model")
        alpha, beta, n = compute_beta_prior(carrier, origin, dest)
        model = BetaBinomialModel(alpha, beta)

        # Optional posterior update
        updated = False
        status = status_info.get("status")
        delay_min = status_info.get("delay_minutes")
        if status in {"active", "landed"} and delay_min is not None:
            observation = int(delay_min > 15)
            model.update(observation)
            updated = True

        p_late = 1.0 - model.predictive_p_on_time()

        # Use Beta-Binomial parameters for backward compatibility
        alpha_result = model.alpha
        beta_result = model.beta
        updated_result = updated
    else:
        # Use dummy values for hierarchical model
        alpha_result = 1.0
        beta_result = 1.0
        updated_result = hier_updated

    # 5. Prepare result ------------------------------------------------------

    result = {
        "p_late": p_late,
        "alpha": alpha_result,
        "beta": beta_result,
        "updated": updated_result,
        "origin": origin,
        "dest": dest,
        "status": status_info.get("status"),
        "carrier": carrier,
        "flight_num": flight_num,
        "scheduled_dep": status_info.get("scheduled_dep"),
        "hierarchical_used": online_updater is not None and p_late is not None,
        "update_time_ms": update_time_ms,
    }

    # Add weather data
    result.update(weather_data)

    # Add aircraft data placeholders (would need additional APIs for real data)
    result.update(
        {
            "tail_number": None,  # Would need aircraft registry API
            "aircraft_age_yrs": None,  # Would need aircraft registry API
        }
    )

    return result
