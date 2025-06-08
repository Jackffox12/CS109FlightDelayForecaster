"""NOAA NWS gridpoint API client for weather data around flight departure times."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import httpx

__all__ = ["get_weather_for_flight", "get_gridpoint_weather"]

# NWS API endpoints
NWS_BASE = "https://api.weather.gov"
USER_AGENT = "flight-delay-bayes/1.0 (github.com/user/flight-delay-bayes)"

# Cache gridpoint lookups to avoid repeated API calls
_gridpoint_cache: Dict[str, Dict[str, Any]] = {}


class NOAAError(Exception):
    """Raised when NOAA API calls fail."""


async def _fetch_json(url: str, session: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch JSON from NWS API with proper user agent."""
    headers = {"User-Agent": USER_AGENT}

    resp = await session.get(url, headers=headers, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


async def _get_gridpoint_info(
    lat: float, lng: float, session: httpx.AsyncClient
) -> Dict[str, str]:
    """Get gridpoint information for a lat/lng coordinate."""
    cache_key = f"{lat:.4f},{lng:.4f}"

    if cache_key in _gridpoint_cache:
        return _gridpoint_cache[cache_key]

    url = f"{NWS_BASE}/points/{lat:.4f},{lng:.4f}"

    try:
        data = await _fetch_json(url, session)
        properties = data.get("properties", {})

        gridpoint_info = {
            "gridId": properties.get("gridId", ""),
            "gridX": str(properties.get("gridX", "")),
            "gridY": str(properties.get("gridY", "")),
            "forecast_url": properties.get("forecast", ""),
            "forecast_hourly_url": properties.get("forecastHourly", ""),
        }

        _gridpoint_cache[cache_key] = gridpoint_info
        return gridpoint_info

    except (httpx.HTTPError, KeyError) as e:
        raise NOAAError(f"Failed to get gridpoint for {lat}, {lng}: {e}")


async def get_gridpoint_weather(
    lat: float, lng: float, target_time: datetime
) -> Dict[str, Any]:
    """Get weather data for a specific location and time via NWS gridpoint API.

    Parameters
    ----------
    lat, lng
        Latitude and longitude of the location
    target_time
        Target datetime (should be timezone-aware)

    Returns
    -------
    Weather data dict with keys:
        - temp_c: Temperature in Celsius
        - wind_kt: Wind speed in knots
        - precip_mm: Precipitation in mm
        - conditions: Weather conditions description
        - valid_time: ISO string of when forecast is valid
    """
    async with httpx.AsyncClient() as session:
        try:
            # Get gridpoint information
            gridpoint = await _get_gridpoint_info(lat, lng, session)

            # Fetch hourly forecast
            forecast_url = gridpoint["forecast_hourly_url"]
            if not forecast_url:
                raise NOAAError("No hourly forecast URL available")

            forecast_data = await _fetch_json(forecast_url, session)

            # Find the forecast period closest to target time
            periods = forecast_data.get("properties", {}).get("periods", [])

            best_period = None
            min_time_diff = timedelta(days=999)

            for period in periods:
                start_time_str = period.get("startTime", "")
                if not start_time_str:
                    continue

                try:
                    start_time = datetime.fromisoformat(
                        start_time_str.replace("Z", "+00:00")
                    )
                    time_diff = abs(target_time - start_time)

                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        best_period = period

                except ValueError:
                    continue

            if not best_period:
                raise NOAAError("No suitable forecast period found")

            # Extract weather data
            temp_f = best_period.get("temperature", 0)
            temp_c = (temp_f - 32) * 5 / 9  # Convert F to C

            wind_speed = best_period.get("windSpeed", "0 mph")
            wind_kt = 0
            try:
                # Parse wind speed like "10 mph" -> 10 knots (rough conversion)
                speed_str = wind_speed.split()[0]
                wind_mph = float(speed_str)
                wind_kt = wind_mph * 0.868976  # mph to knots
            except (ValueError, IndexError):
                wind_kt = 0

            # For precipitation, we'll need to check probabilityOfPrecipitation
            precip_prob = best_period.get("probabilityOfPrecipitation", {})
            if isinstance(precip_prob, dict):
                precip_pct = precip_prob.get("value", 0) or 0
            else:
                precip_pct = 0

            # Rough estimate: convert precip probability to mm (very approximate)
            precip_mm = precip_pct * 0.1 if precip_pct > 50 else 0

            return {
                "temp_c": round(temp_c, 1),
                "wind_kt": round(wind_kt, 1),
                "precip_mm": round(precip_mm, 1),
                "conditions": best_period.get("shortForecast", ""),
                "valid_time": best_period.get("startTime", ""),
                "gridpoint": f"{gridpoint['gridId']}/{gridpoint['gridX']},{gridpoint['gridY']}",
            }

        except httpx.HTTPError as e:
            raise NOAAError(f"HTTP error fetching weather: {e}")
        except Exception as e:
            raise NOAAError(f"Unexpected error fetching weather: {e}")


async def get_weather_for_flight(
    airport_lat: float, airport_lng: float, scheduled_dep: datetime
) -> Dict[str, Any]:
    """Get weather data for a flight departure.

    Fetches weather in 3-hour window around scheduled departure.
    """
    if scheduled_dep.tzinfo is None:
        # Assume UTC if no timezone
        scheduled_dep = scheduled_dep.replace(tzinfo=timezone.utc)

    try:
        weather = await get_gridpoint_weather(airport_lat, airport_lng, scheduled_dep)
        return {
            "wx_temp_c": weather["temp_c"],
            "wx_wind_kt": weather["wind_kt"],
            "wx_precip_mm": weather["precip_mm"],
            "wx_conditions": weather["conditions"],
            "wx_valid_time": weather["valid_time"],
        }
    except NOAAError:
        # Return null values if weather fetch fails
        return {
            "wx_temp_c": None,
            "wx_wind_kt": None,
            "wx_precip_mm": None,
            "wx_conditions": None,
            "wx_valid_time": None,
        }
