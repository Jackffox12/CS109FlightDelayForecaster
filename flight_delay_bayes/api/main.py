"""REST API exposing flight delay forecasts."""

from __future__ import annotations

from datetime import date, datetime

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


def _calculate_predicted_departure(
    scheduled_dep: str | None, p_late: float
) -> str | None:
    """Calculate predicted departure time from scheduled time and delay probability."""
    if not scheduled_dep:
        return None

    try:
        # Parse the scheduled departure time
        sched_dt = datetime.fromisoformat(scheduled_dep.replace("Z", "+00:00"))

        # Calculate expected delay in minutes (simple: p_late * 60)
        predicted_delay_minutes = int(p_late * 60)

        # Add delay to scheduled time
        from datetime import timedelta

        pred_dt = sched_dt + timedelta(minutes=predicted_delay_minutes)

        # Return in ISO format
        return pred_dt.isoformat()
    except (ValueError, TypeError):
        return None


@app.get("/forecast/{carrier}/{number}/{dep_date}")
async def forecast(carrier: str, number: str, dep_date: str):  # noqa: D401
    """Return probability the flight will be late (>15 min)."""
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
            "pred_dep_local": _calculate_predicted_departure(
                result["scheduled_dep"], result["p_late"]
            ),
            "p_late": result["p_late"],
            "alpha": result["alpha"],
            "beta": result["beta"],
            "updated": result["updated"],
        }
        return response
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
