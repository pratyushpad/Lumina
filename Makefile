.PHONY: dev dev-backend dev-frontend up down test ingest eval eval-retrieval

# --- Run ---
up:
	docker compose up --build

down:
	docker compose down

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# --- Quality ---
PY := backend/.venv/bin/python

test:
	cd backend && .venv/bin/python -m pytest -q

# --- Data / Eval ---
ingest:
	$(PY) backend/scripts/ingest_corpus.py

eval:
	$(PY) eval/run_eval.py

eval-retrieval:
	$(PY) eval/run_eval.py --retrieval-only
