.PHONY: dev backend frontend

# Run FastAPI backend with auto-reload
backend:
	poetry run uvicorn backend.main:app --reload --port 8000

# Run Vite + React frontend with hot-reload
frontend:
	cd frontend && npm run dev -- --port 5173

# Run both backend and frontend concurrently (Ctrl+C to stop)
dev:
	poetry run uvicorn backend.main:app --reload --port 8000 & \
	cd frontend && npm run dev -- --port 5173 