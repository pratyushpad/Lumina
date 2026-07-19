# Lumina — Production-Shaped Multimodal RAG

[![CI](https://github.com/pratyushpad/Lumina/actions/workflows/ci.yml/badge.svg)](https://github.com/pratyushpad/Lumina/actions/workflows/ci.yml)

**Live demo: [lumina-rag-two.vercel.app](https://lumina-rag-two.vercel.app)** — click
*Try the live demo* for a pre-seeded session over two classic papers; a cited answer
is one click away. (API: [prat20-lumina-api.hf.space](https://prat20-lumina-api.hf.space/docs),
free-tier hosted — first answer of the day may take a few extra seconds.)

![Lumina demo — suggested question to cited answer](docs/demo.gif)

Upload PDFs / images / text into isolated sessions, then chat with cited, grounded
answers. Built to be **measured, not vibed**: hybrid BM25+dense retrieval with RRF
fusion, a cross-encoder reranker, a local-GPU/hosted LLM provider abstraction,
per-query pipeline tracing, confidence-based refusal, and a frozen eval set with a
per-component ablation table.

## Results (10-second version)

Measured on the frozen 52-question eval set over a documented 4-document corpus
(full tables in [`docs/eval.md`](docs/eval.md), method details in
[`MODEL_CARD.md`](MODEL_CARD.md)):

| Configuration | recall@5 | MRR | NDCG@10 |
|---|---|---|---|
| dense only (MiniLM baseline) | 0.571 | 0.427 | 0.469 |
| hybrid RRF (BM25+dense) | 0.762 | 0.670 | 0.707 |
| **hybrid + cross-encoder rerank** | **0.869** | **0.795** | **0.793** |

- True Okapi BM25 beats Postgres FTS as the sparse channel on every metric
  (e.g. hybrid recall@5 0.762 vs 0.619).
- Multi-query rewriting added ~700 ms p50 and moved **no** metric — measured, and
  therefore off by default.
- Confidence refusal gate calibrated against 10 unanswerable questions
  (false-refusal / false-answer sweep in `docs/eval.md`).

## Architecture

```
                    ┌────────────── ingestion ──────────────┐
 PDF/IMG/TXT ──► Parser (PyMuPDF/pdfplumber) ──► Chunker (fixed|recursive|semantic)
                                            └──► images ──► VisionService (Gemini)
                          │ embeddings (MiniLM, 384-d)
                          ▼
                Postgres + pgvector  (chunks: HNSW cosine + tsvector, Alembic-managed)
                          │
       ┌───── retrieval pipeline (config-driven, fully traced) ─────┐
 query ─► [multi-query | HyDE]? ─► dense ANN ─┬─► RRF fusion ─► cross-encoder
                          BM25 (in-process) ──┘      (k=60)        rerank (top-5)
                          │
                          ▼ confidence gate (refuse below threshold)
                 PromptBuilder (+ injection-scan delimiters)
                          │
                          ▼
        ProviderRouter: OpenAI-compat (Groq / Ollama / vLLM) ──fallback──► Gemini
                          │  SSE stream + provider/tokens-per-sec meta
                          ▼
             React UI (citations, provider badge, per-message trace inspector)
```

- **Backend**: FastAPI, SQLAlchemy async + asyncpg, Postgres 16 + pgvector,
  Alembic, sentence-transformers (MiniLM + ms-marco cross-encoder), rank-bm25,
  google-genai, httpx, sse-starlette
- **Frontend**: React 18 + Vite + TS, Tailwind, Framer Motion, Zustand, TanStack Query

## Quickstart (Docker)

```bash
cp backend/.env.example backend/.env   # put your GEMINI_API_KEY in backend/.env
docker compose up --build
# UI: http://localhost:5173 · API: http://localhost:8000 (docs at /docs)
```

## Local dev

```bash
docker compose up -d postgres          # pgvector on host port 5433
cd backend && python3.10 -m venv .venv && .venv/bin/pip install -r requirements.txt
make dev-backend                       # migrations run automatically at startup
cd frontend && npm install && npm run dev
```

## Local LLM serving (RTX 5060 box)

The `local` provider speaks the OpenAI-compatible API, so Ollama and vLLM both work:

```bash
# on the GPU box (Windows/Linux)
ollama pull qwen2.5:7b-instruct-q4_K_M
# Windows: set OLLAMA_HOST=0.0.0.0 and allow port 11434 through the firewall
```

```bash
# in backend/.env on the machine running Lumina
LLM_PROVIDER_ORDER=local,gemini
LOCAL_LLM_BASE_URL=http://<gpu-box-ip>:11434/v1
LOCAL_LLM_MODEL=qwen2.5:7b-instruct-q4_K_M
```

Health checks are cached (30 s TTL); if the box is off, requests fall back to
Gemini automatically, and the UI badge + trace show which provider actually served
each answer, with measured tokens/sec.

The same provider slot speaks to any hosted OpenAI-compatible endpoint — the
live deployment runs Groq (`llama-3.3-70b-versatile`) as primary with Gemini
fallback, all free-tier:

```bash
LLM_PROVIDER_ORDER=local,gemini
LOCAL_LLM_BASE_URL=https://api.groq.com/openai/v1
LOCAL_LLM_MODEL=llama-3.3-70b-versatile
LOCAL_LLM_API_KEY=gsk_...
```

## Evaluation

```bash
make ingest           # deterministic corpus ingestion (stable chunk ids + manifest)
make eval-retrieval   # ablation table + refusal-threshold sweep (no LLM cost)
make eval             # + generation metrics with the LLM judge (throttled)
```

Everything lands in `docs/eval.md`. The dataset (`eval/dataset.jsonl`) is frozen;
each item's ground-truth chunk ids were verified against the corpus before freezing.

## Observability

Every query writes a trace (`traces` / `trace_stages` in Postgres): per-stage
candidates, scores, and latency for dense, BM25/FTS, fusion, rerank, vision
enrichment, and generation. In the UI, the **trace** button on any assistant
message opens the pipeline inspector; via API it's `GET /api/traces/{message_id}`.

## Guardrails

- **Refusal (two-stage)**: if the top rerank score is below `MIN_RERANK_SCORE`,
  a bi-encoder second chance re-checks the top candidates (cosine sim vs
  `MIN_BIENCODER_SIM`) — catching honest paraphrases the cross-encoder
  under-scores (query "salary" vs a chunk saying "compensation"). Only when both
  signals are weak does Lumina answer "not in your documents" without calling the
  LLM (sweep in `docs/eval.md` models the two-stage gate exactly).
- **Prompt injection**: retrieved chunks matching injection heuristics are wrapped
  in warning delimiters before entering the prompt.
- **PII**: optional regex scrub (emails/phones/SSNs/cards) at ingest via
  `PII_SCRUB_ON_INGEST=true` — regexes only, limitations documented in the source.

## API surface

- `POST /api/sessions/` · `GET /api/sessions/` · `PATCH /api/sessions/{id}` · `DELETE /api/sessions/{id}`
- `POST /api/documents/upload` (multipart) · `GET /api/documents/session/{id}` · `GET /api/documents/{id}/status` · `DELETE /api/documents/{id}`
- `POST /api/chat/{session_id}` · `GET /api/chat/{session_id}/stream?query=…` (SSE: `citations`, `token`, `meta`, `refusal`, `done`) · `GET /api/chat/{session_id}/history`
- `GET /api/traces/{message_id}` · `GET /health`

## Honest limitations

- The in-process BM25 index assumes a single backend worker and a corpus that fits
  in memory; at scale, switch to FTS-prefilter → BM25 rerank or a Postgres BM25
  extension (ParadeDB `pg_search`). The `fts` sparse mode (`ts_rank_cd`, not true
  BM25) is already wired as a single-SQL alternative.
- Generation metrics use an LLM judge (Gemini flash-lite grading Llama-3.3-70B
  answers — cross-family, which reduces but does not eliminate judge bias).
  Absolute scores should still be read with skepticism; the retrieval ablation
  deltas are the primary signal. See `MODEL_CARD.md`.
- The eval questions share vocabulary with their source chunks, which favors
  lexical (BM25) retrieval; dense retrieval would fare relatively better on
  paraphrased queries.
- All RAG components are implemented directly (no LangChain/LlamaIndex), so every
  number in `docs/eval.md` maps to code in this repo.

## Tests

```bash
make test   # RRF math, BM25 fixtures, guardrails, chunkers + live-Postgres integration
```
