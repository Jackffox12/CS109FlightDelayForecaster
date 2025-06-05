from fastapi import FastAPI

app = FastAPI(title="Flight Delay Forecaster API")


@app.get("/health", tags=["utility"])
def health() -> dict[str, str]:
    """Simple health-check endpoint."""
    return {"status": "ok"} 