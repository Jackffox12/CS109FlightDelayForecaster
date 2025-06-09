"""Vercel serverless function for flight delay forecasting."""

import asyncio
import json
import os
import random
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Mock flight routes for demonstration
DEMO_ROUTES = {
    "DL": {
        "202": {"origin": "JFK", "dest": "ATH"},
        "1": {"origin": "JFK", "dest": "LAX"},
        "88": {"origin": "ATL", "dest": "LAX"},
    },
    "AA": {
        "1": {"origin": "JFK", "dest": "LAX"},
        "100": {"origin": "DFW", "dest": "LAX"},
    },
    "UA": {
        "1": {"origin": "EWR", "dest": "SFO"},
        "328": {"origin": "ORD", "dest": "SFO"},
    },
}


async def forecast_probability(carrier, flight_num, dep_date):
    """Mock forecast for Vercel deployment (no ML dependencies)."""
    # Get route info or use defaults
    route = DEMO_ROUTES.get(carrier, {}).get(
        flight_num, {"origin": "JFK", "dest": "LAX"}
    )

    # Generate realistic mock data with some randomness
    random.seed(hash(f"{carrier}{flight_num}{dep_date}"))  # Consistent for same input

    base_delay_prob = 0.15 + random.random() * 0.4  # 15-55%

    # Create realistic threshold probabilities (decreasing)
    p_late_30 = base_delay_prob * (0.6 + random.random() * 0.2)  # 60-80% of base
    p_late_45 = p_late_30 * (0.6 + random.random() * 0.2)  # 60-80% of 30min
    p_late_60 = p_late_45 * (0.5 + random.random() * 0.3)  # 50-80% of 45min

    exp_delay = 2 + base_delay_prob * 25  # 2-15 minutes expected delay

    # Create scheduled departure (8 hours from now for demo)
    scheduled_dt = datetime.now() + timedelta(hours=8)
    pred_dt = scheduled_dt + timedelta(minutes=exp_delay)

    return {
        "carrier": carrier,
        "flight_num": flight_num,
        "origin": route["origin"],
        "dest": route["dest"],
        "scheduled_dep": scheduled_dt.isoformat() + "Z",
        "pred_dep_local": pred_dt.isoformat() + "Z",
        "p_late": round(base_delay_prob, 3),
        "p_late_30": round(p_late_30, 3),
        "p_late_45": round(p_late_45, 3),
        "p_late_60": round(p_late_60, 3),
        "exp_delay_min": round(exp_delay, 1),
        "alpha": 12.5 + random.random() * 10,
        "beta": 17.3 + random.random() * 15,
        "updated": True,
        "hierarchical_used": False,
        "update_time_ms": random.random() * 100,
        "wx_temp_c": 15 + random.random() * 20,
        "wx_wind_kt": random.random() * 25,
        "wx_precip_mm": random.random() * 5 if random.random() > 0.7 else 0,
        "wx_conditions": random.choice(
            ["Clear", "Partly Cloudy", "Cloudy", "Light Rain"]
        ),
        "status": "scheduled",
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_cors_headers()

        try:
            # Debug: log the actual path received
            print(f"DEBUG: Received path: '{self.path}'")

            # For Vercel dynamic routing, the path will be something like:
            # /DL/202/2025-06-08 (without /api/forecast prefix)
            path = self.path.strip("/")
            print(f"DEBUG: Stripped path: '{path}'")

            # Handle both direct and query parameter formats
            if "?" in path:
                path = path.split("?")[0]
                print(f"DEBUG: Path after query removal: '{path}'")

            # Split by path segments
            path_parts = path.split("/") if path else []
            print(f"DEBUG: Path parts: {path_parts}")

            if len(path_parts) < 3:
                self.send_error_response(
                    400,
                    f"Invalid URL format. Expected: {{carrier}}/{{number}}/{{date}}. Received path: '{self.path}', parts: {path_parts}",
                )
                return

            carrier = path_parts[0].upper()
            flight_number = path_parts[1]
            date_str = path_parts[2]

            # Validate date format
            try:
                dep_date = date.fromisoformat(date_str)
            except ValueError:
                self.send_error_response(400, "Date must be YYYY-MM-DD")
                return

            # Get forecast
            result = asyncio.run(forecast_probability(carrier, flight_number, dep_date))

            # Format response
            response_data = {
                "carrier": result["carrier"],
                "flight_num": result["flight_num"],
                "origin": result.get("origin", "JFK"),
                "dest": result.get("dest", "LAX"),
                "sched_dep_local": result.get("scheduled_dep"),
                "pred_dep_local": result.get("pred_dep_local"),
                "p_late": result["p_late"],
                "p_late_30": result["p_late_30"],
                "p_late_45": result["p_late_45"],
                "p_late_60": result["p_late_60"],
                "exp_delay_min": result["exp_delay_min"],
                "alpha": result["alpha"],
                "beta": result["beta"],
                "updated": result["updated"],
                "hierarchical_used": result.get("hierarchical_used", False),
                "update_time_ms": result.get("update_time_ms", 0.0),
                "wx_temp_c": result.get("wx_temp_c"),
                "wx_wind_kt": result.get("wx_wind_kt"),
                "wx_precip_mm": result.get("wx_precip_mm"),
                "wx_conditions": result.get("wx_conditions"),
                "wx_valid_time": result.get("wx_valid_time"),
                "tail_number": result.get("tail_number"),
                "aircraft_age_yrs": result.get("aircraft_age_yrs"),
            }

            self.send_json_response(200, response_data)

        except Exception as e:
            print(f"DEBUG: Exception occurred: {e}")
            self.send_error_response(500, str(e))

    def do_OPTIONS(self):
        self.send_cors_headers()
        self.send_response(200)
        self.end_headers()

    def send_cors_headers(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_error_response(self, status_code, message):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"detail": message}).encode())
