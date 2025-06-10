"""Pipeline to forecast probability of flight being late using priors and real-time status."""

from __future__ import annotations

import asyncio
import pickle
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from flight_delay_bayes.bayes.delay_curve import (
    DelayPredictor,
    create_default_delay_curve,
    load_delay_curve,
)
from flight_delay_bayes.bayes.hier_online import OnlineHierarchicalUpdater
from flight_delay_bayes.bayes.prior_estimator import compute_beta_prior
from flight_delay_bayes.bayes.updater import BetaBinomialModel
from flight_delay_bayes.realtime.aviationstack import get_flight_status
from flight_delay_bayes.realtime.noaa_gridpoint import get_weather_for_flight

# Airport coordinates for weather lookups (expanded with international airports)
AIRPORT_COORDS = {
    # Major US airports
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
    "RSW": (26.5362, -81.7552),
    "FLL": (26.0742, -80.1506),
    "AUS": (30.1975, -97.6664),
    "SAT": (29.5337, -98.4698),
    # International airports
    "YYZ": (43.6777, -79.6248),  # Toronto Pearson
    "YVR": (49.1967, -123.1815),  # Vancouver
    "LHR": (51.4700, -0.4543),  # London Heathrow
    "CDG": (49.0097, 2.5479),  # Paris Charles de Gaulle
    "FRA": (50.0379, 8.5622),  # Frankfurt
    "AMS": (52.3105, 4.7683),  # Amsterdam Schiphol
    "NRT": (35.7720, 140.3929),  # Tokyo Narita
    "ICN": (37.4602, 126.4407),  # Seoul Incheon
    "ATH": (37.9364, 23.9445),  # Athens
    "FCO": (41.8003, 12.2389),  # Rome Fiumicino
    "MUC": (48.3538, 11.7861),  # Munich
    "ZUR": (47.4647, 8.5492),  # Zurich
    "BRU": (50.9014, 4.4844),  # Brussels
    "MAD": (40.4839, -3.5680),  # Madrid
    "BCN": (41.2974, 2.0833),  # Barcelona
    "VIE": (48.1103, 16.5697),  # Vienna
    "ARN": (59.6519, 17.9186),  # Stockholm Arlanda
    "CPH": (55.6181, 12.6561),  # Copenhagen
    "HEL": (60.3172, 24.9633),  # Helsinki
    "OSL": (60.1939, 11.1004),  # Oslo
}

# Default hierarchical model path (if available)
DEFAULT_HIER_MODEL = Path("models/hier_delays_2023_2023_2023.pkl")
EXPANDED_DB = Path("data/flights_expanded.duckdb")

# Fast model paths (new)
FAST_MODEL_PATHS = [
    Path("models/fast_delay_model_logistic.pkl"),
    Path("models/fast_delay_model_random_forest.pkl"),
]

# Global online updater instance (initialized lazily)
_online_updater: Optional["OnlineHierarchicalUpdater"] = None

# Global delay predictor instance (initialized lazily)
_delay_predictor: Optional["DelayPredictor"] = None

# Global fast model instance (initialized lazily)
_fast_model: Optional[Dict[str, Any]] = None

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


def _get_delay_predictor() -> "DelayPredictor":
    """Get or create the global delay predictor instance."""
    global _delay_predictor

    if _delay_predictor is None:
        try:
            _delay_predictor = load_delay_curve()
            print("📈 Loaded delay curve from models/delay_curve.json")
        except FileNotFoundError:
            print("⚠️  No delay curve found, using default parameters")
            default_curve = create_default_delay_curve()
            _delay_predictor = DelayPredictor(default_curve)

    return _delay_predictor


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


def _calculate_predicted_departure(
    scheduled_dep_str: str | None, exp_delay_min: float
) -> str | None:
    """Calculate predicted departure time from scheduled time and expected delay."""
    if not scheduled_dep_str:
        return None

    try:
        # Parse the scheduled departure time
        sched_dt = datetime.fromisoformat(scheduled_dep_str.replace("Z", "+00:00"))

        # Add expected delay (ensure it's not negative)
        delay_minutes = max(0, exp_delay_min)
        pred_dt = sched_dt + timedelta(minutes=delay_minutes)

        # Return in ISO format
        return pred_dt.isoformat()
    except (ValueError, TypeError):
        return None


def _get_fast_model() -> Optional[Dict[str, Any]]:
    """Get or create the global fast model instance."""
    global _fast_model

    if _fast_model is None:
        # Try to load the fast model
        for model_path in FAST_MODEL_PATHS:
            if model_path.exists():
                try:
                    with open(model_path, "rb") as f:
                        _fast_model = pickle.load(f)
                    print(f"📊 Loaded fast model: {model_path}")
                    break
                except Exception as e:
                    print(f"⚠️  Failed to load fast model {model_path}: {e}")
                    continue

        if _fast_model is None:
            print("📭 No fast model found")

    return _fast_model


def _predict_with_fast_model(
    carrier: str,
    origin: str,
    dest: str,
    dep_hour: int,
    wx_temp_c: Optional[float] = None,
    wx_wind_kt: Optional[float] = None,
    wx_precip_mm: Optional[float] = None,
) -> Optional[float]:
    """Make prediction using the fast scikit-learn model with weather integration."""
    fast_model_data = _get_fast_model()

    if not fast_model_data:
        return None

    try:
        model = fast_model_data["model"]
        feature_cols = fast_model_data["feature_cols"]

        # Create feature vector (matching training format)
        from datetime import datetime

        import pandas as pd

        # Create basic features
        features = {
            "dep_hour": dep_hour,
            "month": 6,  # Default to June
            "day_of_week": 2,  # Default to Wednesday
            "is_weekend": 0,
            "is_early_morning": 1 if dep_hour <= 8 else 0,
            "is_evening_rush": 1 if 16 <= dep_hour <= 19 else 0,
            "is_late_night": 1 if dep_hour >= 22 else 0,
        }

        # High-delay airports
        high_delay_airports = {"LGA", "EWR", "JFK", "ORD", "LAX", "SFO", "ATL", "DFW"}
        features["origin_high_delay"] = 1 if origin in high_delay_airports else 0
        features["dest_high_delay"] = 1 if dest in high_delay_airports else 0
        features["is_high_volume"] = 1  # Default to high volume route

        # Add carrier-specific features (if they exist in the model)
        carriers = ["AA", "AS", "B6", "DL", "SW", "UA"]  # Common carriers from training
        for c in carriers:
            features[f"carrier_{c}"] = 1 if carrier == c else 0

        # Create DataFrame with features in correct order
        feature_data = []
        for col in feature_cols:
            if col in features:
                feature_data.append(features[col])
            else:
                feature_data.append(0)  # Default to 0 for missing features

        # Make base prediction
        import numpy as np

        X = np.array(feature_data).reshape(1, -1)

        if hasattr(model, "predict_proba"):
            base_prob = model.predict_proba(X)[0, 1]
        else:
            base_prob = model.predict(X)[0]

        # Apply weather adjustments (enhanced impact)
        weather_multiplier = 1.0

        if wx_temp_c is not None:
            # Extreme temperatures increase delays significantly
            if wx_temp_c < 0:  # Freezing weather
                weather_multiplier *= 1.4
            elif wx_temp_c > 35:  # Very hot weather
                weather_multiplier *= 1.3
            elif wx_temp_c < 5 or wx_temp_c > 30:  # Cold or hot weather
                weather_multiplier *= 1.15

        if wx_wind_kt is not None:
            # High winds significantly increase delays
            if wx_wind_kt > 35:  # Very high winds
                weather_multiplier *= 1.6
            elif wx_wind_kt > 25:  # High winds
                weather_multiplier *= 1.3
            elif wx_wind_kt > 15:  # Moderate winds
                weather_multiplier *= 1.1

        if wx_precip_mm is not None:
            # Precipitation significantly increases delays
            if wx_precip_mm > 10:  # Heavy precipitation
                weather_multiplier *= 1.8
            elif wx_precip_mm > 5:  # Moderate precipitation
                weather_multiplier *= 1.4
            elif wx_precip_mm > 1:  # Light precipitation
                weather_multiplier *= 1.2

        # Apply weather adjustment
        adjusted_prob = min(0.95, base_prob * weather_multiplier)

        print(
            f"   🌤️  Weather adjustment: {base_prob:.3f} → {adjusted_prob:.3f} (multiplier: {weather_multiplier:.2f})"
        )

        return float(adjusted_prob)

    except Exception as e:
        print(f"⚠️  Fast model prediction failed: {e}")
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

    # 4. Try fast scikit-learn model if hierarchical failed ------------------
    if p_late is None and dep_hour is not None:
        print("🚀 Trying fast scikit-learn model...")
        p_late = _predict_with_fast_model(
            carrier=carrier,
            origin=origin,
            dest=dest,
            dep_hour=dep_hour,
            wx_temp_c=weather_data.get("wx_temp_c"),
            wx_wind_kt=weather_data.get("wx_wind_kt"),
            wx_precip_mm=weather_data.get("wx_precip_mm"),
        )

        if p_late is not None:
            print(f"✅ Fast model prediction: {p_late:.1%}")
            # Use dummy values for backward compatibility
            alpha_result = 1.0
            beta_result = 1.0
            updated_result = False
        else:
            print("⚠️  Fast model failed, falling back to Beta-Binomial")

    # 5. Final fallback to Beta-Binomial if all models failed ---------------
    if p_late is None:
        print("📈 Falling back to Beta-Binomial model")
        # Use the real data database for better priors
        db_path = (
            Path("data/flights_real.duckdb")
            if Path("data/flights_real.duckdb").exists()
            else None
        )
        alpha, beta, n = compute_beta_prior(carrier, origin, dest, db_path)
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

    # 6. Calculate expected delay and predicted departure time ---------------
    delay_predictor = _get_delay_predictor()
    exp_delay_min = delay_predictor.predict_delay(p_late)
    pred_dep_local = _calculate_predicted_departure(
        status_info.get("scheduled_dep"), exp_delay_min
    )

    # 7. Calculate multiple delay threshold probabilities --------------------
    threshold_probs = delay_predictor.predict_threshold_probabilities(p_late)

    # 8. Prepare result ------------------------------------------------------

    result = {
        "p_late": p_late,  # Keep existing for backward compatibility
        "p_late_30": threshold_probs["p_late_30"],
        "p_late_45": threshold_probs["p_late_45"],
        "p_late_60": threshold_probs["p_late_60"],
        "exp_delay_min": round(exp_delay_min, 1),
        "pred_dep_local": pred_dep_local,
        "alpha": alpha_result,
        "beta": beta_result,
        "updated": updated_result,
        "origin": origin,
        "dest": dest,
        "status": status_info.get("status"),
        "carrier": carrier,
        "flight_num": flight_num,
        "scheduled_dep": status_info.get("scheduled_dep"),
        "hierarchical_used": hier_updated,
        "fast_model_used": _get_fast_model() is not None
        and p_late is not None
        and not hier_updated,
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
