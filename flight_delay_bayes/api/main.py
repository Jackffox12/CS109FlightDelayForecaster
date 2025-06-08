"""REST API exposing flight delay forecasts."""
from __future__ import annotations

import asyncio
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from flight_delay_bayes.bayes.pipeline import forecast_probability

app = FastAPI(title="Flight Delay Bayesian Forecaster API")

# Allow any origin (development). In production, restrict as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, bool]:
    """Basic health check."""
    return {"ok": True}


@app.get("/forecast/{carrier}/{number}/{dep_date}")
async def forecast(carrier: str, number: str, dep_date: str):  # noqa: D401
    """Return probability the flight will be late (>15 min)."""
    try:
        date_obj = date.fromisoformat(dep_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")
    try:
        result = await forecast_probability(carrier.upper(), number, date_obj)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result 