#!/usr/bin/env bash
# One-command retrieval eval from a fresh clone: `make eval-repro`.
#
# Starts the pgvector container, makes backend/.venv if it is missing, fetches the
# arXiv corpus PDFs (sha256-checked), ingests the corpus deterministically, then
# runs the retrieval ablation + refusal sweep.
#
# The report goes to eval/runs/repro.md (gitignored) so the committed docs/eval.md,
# which also holds the older generation section, is not overwritten. Compare the
# two retrieval tables; retrieval eval is deterministic.
#
# With no GEMINI_API_KEY (env or backend/.env), the multi-query row, the only
# retrieval row that calls an LLM, is skipped so the run costs nothing.
#
# Env overrides: PYTHON (interpreter used to build the venv, default python3),
# REPORT (output path, default eval/runs/repro.md), EVAL_DATABASE_URL (default: the
# local compose Postgres; pinned so a cloud DATABASE_URL in backend/.env is never used).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
REPORT="${REPORT:-eval/runs/repro.md}"
VENV="backend/.venv"
PY="$VENV/bin/python"
# Env vars beat backend/.env in pydantic-settings, so ingest and eval both hit local.
export DATABASE_URL="${EVAL_DATABASE_URL:-postgresql+asyncpg://lumina:lumina@localhost:5433/lumina}"

step() { printf '\n==> %s\n' "$*"; }

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker and re-run 'make eval-repro'." >&2
  exit 1
fi

step "Starting Postgres + pgvector (host port 5433)"
docker compose up -d --wait postgres

if [ ! -x "$PY" ]; then
  step "Creating $VENV with $PYTHON"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r backend/requirements.txt
fi

step "Fetching corpus PDFs"
"$PY" scripts/fetch_papers.py

step "Ingesting the eval corpus (migrations run first)"
"$PY" backend/scripts/ingest_corpus.py

EXTRA=()
has_key() {
  [ -n "${GEMINI_API_KEY:-}" ] && return 0
  grep -E '^GEMINI_API_KEY=.+' backend/.env 2>/dev/null | grep -qv 'your_key_here'
}
if ! has_key; then
  echo "No GEMINI_API_KEY found: skipping the multi-query row (it calls an LLM)."
  EXTRA+=(--skip-llm-rows)
fi

step "Running retrieval eval"
mkdir -p "$(dirname "$REPORT")"
"$PY" eval/run_eval.py --retrieval-only --report "$REPORT" ${EXTRA[@]+"${EXTRA[@]}"}

step "Done. Report: $REPORT (compare with docs/eval.md)"
