from __future__ import annotations

import logging
import time
import json

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .forecast import manager, RouteKey, Session

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Flight Delay Forecaster API")

# CORS for frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    duration = (time.time() - start) * 1000
    logger.info("%s %s completed in %.1fms -> %d", request.method, request.url.path, duration, response.status_code)
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Route(BaseModel):
    origin: str
    dest: str
    airline: str
    flight_num: str = Field(alias="flight_num")


class SessionResp(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/routes", response_model=list[Route], tags=["routes"])
async def routes():
    return [
        Route(origin="SFO", dest="JFK", airline="DL", flight_num="147"),
        Route(origin="LAX", dest="SEA", airline="AS", flight_num="330"),
    ]


class ForecastRequest(BaseModel):
    origin: str
    dest: str
    airline: str
    flight_num: str


@app.post("/forecast/start", response_model=SessionResp, tags=["forecast"])
async def start_forecast(req: ForecastRequest):
    route_key: RouteKey = (req.origin, req.dest, req.airline, req.flight_num)
    sess = manager.create_session(route_key)
    await sess.queue.put(sess.forecaster.predict())
    return SessionResp(session_id=sess.id)


def _sse_pack(evt: dict):
    return f"data: {json.dumps(evt)}\n\n".encode()


@app.get("/forecast/{session_id}/stream", tags=["forecast"])
async def stream_forecast(session_id: str, request: Request):
    sess: Session | None = manager.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            evt = await sess.queue.get()
            yield _sse_pack(evt)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health", tags=["utility"])
def health() -> dict[str, str]:
    return {"status": "ok"} 