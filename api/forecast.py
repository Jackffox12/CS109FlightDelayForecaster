"""Flight forecast endpoint for Vercel deployment."""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


def get_mock_forecast(carrier, flight_num, date_str):
    """Simple mock forecast without async."""
    return {
        "carrier": carrier,
        "flight_num": flight_num,
        "origin": "JFK",
        "dest": "LAX",
        "sched_dep_local": "2025-06-08T15:30:00Z",
        "pred_dep_local": "2025-06-08T15:35:00Z",
        "p_late": 0.25,
        "p_late_30": 0.15,
        "p_late_45": 0.10,
        "p_late_60": 0.05,
        "exp_delay_min": 5.0,
        "alpha": 15.0,
        "beta": 20.0,
        "updated": True,
        "hierarchical_used": False,
        "update_time_ms": 0.0,
        "wx_temp_c": 22.0,
        "wx_wind_kt": 10.0,
        "wx_precip_mm": 0.0,
        "wx_conditions": "Clear",
        "wx_valid_time": None,
        "tail_number": None,
        "aircraft_age_yrs": None,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            print(f"DEBUG: Path: {self.path}")
            print(f"DEBUG: Query: {query_params}")

            # Get parameters
            carrier = query_params.get("carrier", ["DL"])[0]
            flight_number = query_params.get("number", ["202"])[0]
            date_str = query_params.get("date", ["2025-06-08"])[0]

            # Get mock forecast
            result = get_mock_forecast(carrier, flight_number, date_str)

            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            print(f"ERROR: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
