"""REST API exposing flight delay forecasts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from flight_delay_bayes.bayes.pipeline import forecast_probability

app = FastAPI(title="Flight Delay Bayesian Forecaster API")

# Allow any origin (development). In production, restrict as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data")
PERF_FILE = DATA_DIR / "live_perf.parquet"


class LogOutcomePayload(BaseModel):
    """Payload for logging a flight's predicted vs. actual outcome."""

    flight_id: str
    p_pred: float = Field(
        ...,
        ge=0,
        le=1,
        description="Predicted probability of being late",
    )
    y_true: bool = Field(
        ..., description="True outcome (True if late, False if on-time)"
    )


@app.post("/log-outcome")
async def log_outcome(payload: LogOutcomePayload):
    """Log a live flight outcome to persisted storage (Parquet file)."""
    DATA_DIR.mkdir(exist_ok=True)

    new_record = payload.dict()
    new_record["timestamp"] = datetime.now(timezone.utc)
    new_df = pd.DataFrame([new_record])

    try:
        if PERF_FILE.exists():
            existing_df = pd.read_parquet(PERF_FILE)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        combined_df.to_parquet(PERF_FILE, index=False)
        return {"status": "ok", "rows": len(combined_df)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to write to performance log: {e}"
        )


@app.get("/health")
def health() -> dict[str, bool]:
    """Basic health check."""
    return {"ok": True}


@app.get("/forecast/{carrier}/{number}/{dep_date}")
async def forecast(carrier: str, number: str, dep_date: str):  # noqa: D401
    """Return probability the flight will be late (>15 min) with weather data."""
    try:
        date_obj = date.fromisoformat(dep_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")
    try:
        result = await forecast_probability(carrier.upper(), number, date_obj)

        # Transform to requested format
        response = {
            "carrier": result["carrier"],
            "flight_num": result["flight_num"],
            "origin": result["origin"],
            "dest": result["dest"],
            "sched_dep_local": result["scheduled_dep"],
            "pred_dep_local": result["pred_dep_local"],
            "p_late": result["p_late"],
            "p_late_30": result["p_late_30"],
            "p_late_45": result["p_late_45"],
            "p_late_60": result["p_late_60"],
            "exp_delay_min": result["exp_delay_min"],
            "alpha": result["alpha"],
            "beta": result["beta"],
            "updated": result["updated"],
            # Hierarchical model info
            "hierarchical_used": result.get("hierarchical_used", False),
            "update_time_ms": result.get("update_time_ms", 0.0),
            # Weather data
            "wx_temp_c": result.get("wx_temp_c"),
            "wx_wind_kt": result.get("wx_wind_kt"),
            "wx_precip_mm": result.get("wx_precip_mm"),
            "wx_conditions": result.get("wx_conditions"),
            "wx_valid_time": result.get("wx_valid_time"),
            # Aircraft data
            "tail_number": result.get("tail_number"),
            "aircraft_age_yrs": result.get("aircraft_age_yrs"),
        }
        return response
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
