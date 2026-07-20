.PHONY: dev dev-backend dev-frontend up down test lint format ingest eval eval-retrieval

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

# Same checks CI runs, so a green local run means a green pipeline.
lint:
	cd backend && .venv/bin/ruff check app scripts tests
	cd frontend && npm run lint && npm run format:check

format:
	cd backend && .venv/bin/ruff check --fix app scripts tests
	cd frontend && npm run format

# --- Data / Eval ---
fetch-papers:
	$(PY) scripts/fetch_papers.py

ingest: fetch-papers
	$(PY) backend/scripts/ingest_corpus.py

eval:
	$(PY) eval/run_eval.py

eval-retrieval:
	$(PY) eval/run_eval.py --retrieval-only
