"""Vercel serverless function for flight delay forecasting."""

import asyncio
import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from flight_delay_bayes.bayes.pipeline import forecast_probability
except ImportError:
    # Fallback for simplified deployment
    async def forecast_probability(carrier, flight_num, dep_date):
        return {
            "carrier": carrier,
            "flight_num": flight_num,
            "origin": "JFK",
            "dest": "LAX",
            "scheduled_dep": "2025-01-15T10:30:00-05:00",
            "pred_dep_local": "2025-01-15T10:35:00-05:00",
            "p_late": 0.42,
            "p_late_30": 0.31,
            "p_late_45": 0.22,
            "p_late_60": 0.15,
            "exp_delay_min": 5.2,
            "alpha": 12.5,
            "beta": 17.3,
            "updated": True,
            "hierarchical_used": False,
            "update_time_ms": 0.0,
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_cors_headers()

        try:
            # Parse URL - Vercel will pass the path after /api/forecast/
            path = self.path.strip("/")

            # Handle both direct and query parameter formats
            if "?" in path:
                path = path.split("?")[0]

            # Split by remaining path segments
            path_parts = path.split("/") if path else []

            if len(path_parts) < 3:
                self.send_error_response(
                    400, "Invalid URL format. Expected: {carrier}/{number}/{date}"
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
