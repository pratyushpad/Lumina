"""Lumina evaluation harness: retrieval ablations + RAGAS-style generation metrics.

Usage (from repo root, after `make ingest`):
    make eval-retrieval   # retrieval metrics only — cheap, no LLM calls except multi-query
    make eval             # + generation & judge metrics on the production config (LLM calls, throttled)

Runs each ablation RetrievalConfig against the exact production RetrievalPipeline
code path over the frozen eval/dataset.jsonl, writes a run JSON under eval/runs/
and regenerates docs/eval.md.
"""
import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO_ROOT))
os.chdir(BACKEND)  # so backend/.env and relative storage paths resolve

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("lumina.eval")
logger.setLevel(logging.INFO)

DATASET = REPO_ROOT / "eval" / "dataset.jsonl"
RUNS_DIR = REPO_ROOT / "eval" / "runs"

# The ablation ladder. Order tells the resume story: each row adds one component.
ABLATIONS: list[tuple[str, dict]] = [
    ("dense only (baseline)", {"mode": "dense", "rerank": False}),
    ("sparse only (BM25)", {"mode": "sparse", "sparse_method": "bm25", "rerank": False}),
    ("hybrid RRF (BM25+dense)", {"mode": "hybrid_rrf", "sparse_method": "bm25", "rerank": False}),
    ("hybrid RRF (FTS+dense)", {"mode": "hybrid_rrf", "sparse_method": "fts", "rerank": False}),
    ("hybrid + rerank", {"mode": "hybrid_rrf", "sparse_method": "bm25", "rerank": True}),
    (
        "hybrid + rerank + multi-query",
        {"mode": "hybrid_rrf", "sparse_method": "bm25", "rerank": True,
         "query_transform": "multi_query"},
    ),
]

# Config whose retrieved context feeds generation + judge metrics (production default)
GENERATION_CONFIG = "hybrid + rerank"


def load_dataset() -> list[dict]:
    items = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    answerable = [i for i in items if i.get("relevant_chunk_ids")]
    logger.info("Loaded %d eval items (%d answerable)", len(items), len(answerable))
    return items


async def eval_retrieval(items: list[dict], mq_delay: float = 13.0) -> list[dict]:
    from app.services.retrieval.pipeline import RetrievalConfig, RetrievalPipeline

    from eval.metrics import aggregate, ndcg_at_k, recall_at_k, reciprocal_rank

    rows = []
    for name, overrides in ABLATIONS:
        cfg = RetrievalConfig(top_k_candidates=50, top_k_final=10, **overrides)
        pipeline = RetrievalPipeline(cfg)
        per_query, latencies, retrieved_map = [], [], {}
        for item in items:
            if not item.get("relevant_chunk_ids"):
                continue
            if cfg.query_transform != "none":
                # Free-tier Gemini is 5 RPM; without spacing, rewrites 429 and
                # silently fall back to the raw query, invalidating this row.
                await asyncio.sleep(mq_delay)
            t0 = time.perf_counter()
            results = await pipeline.run(item["question"], _doc_ids())
            latencies.append((time.perf_counter() - t0) * 1000)
            retrieved = [r.chunk_id for r in results]
            retrieved_map[item["qid"]] = retrieved
            rel = item["relevant_chunk_ids"]
            per_query.append(
                {
                    "recall@5": recall_at_k(retrieved, rel, 5),
                    "recall@10": recall_at_k(retrieved, rel, 10),
                    "mrr": reciprocal_rank(retrieved, rel),
                    "ndcg@10": ndcg_at_k(retrieved, rel, 10),
                }
            )
        agg = aggregate(per_query)
        agg["p50_latency_ms"] = statistics.median(latencies)
        rows.append(
            {"config": name, "overrides": overrides, "metrics": agg,
             "retrieved": retrieved_map, "n": len(per_query)}
        )
        logger.info(
            "%-32s recall@5=%.3f recall@10=%.3f mrr=%.3f ndcg@10=%.3f p50=%dms",
            name, agg["recall@5"], agg["recall@10"], agg["mrr"], agg["ndcg@10"],
            int(agg["p50_latency_ms"]),
        )
    return rows


async def eval_generation(items: list[dict], judge_delay: float) -> dict:
    """Generate answers with the production config and grade them with the judge."""
    from app.services.generation.llm import LLMService
    from app.services.generation.prompt_builder import PromptBuilder
    from app.services.retrieval.pipeline import RetrievalConfig, RetrievalPipeline

    from eval.judge import Judge
    from eval.metrics import aggregate

    overrides = dict(ABLATIONS)[GENERATION_CONFIG]
    cfg = RetrievalConfig(top_k_candidates=50, top_k_final=5, **overrides)
    pipeline = RetrievalPipeline(cfg)
    builder = PromptBuilder()
    llm = LLMService.get()
    judge = Judge(llm.generate, delay_s=judge_delay)

    per_query = []
    for i, item in enumerate(items):
        if not item.get("relevant_chunk_ids"):
            continue
        q, ref = item["question"], item["reference_answer"]
        chunks = await pipeline.run(q, _doc_ids())
        context_texts = [c.text for c in chunks]
        context = "\n\n".join(context_texts)

        answer, _ = await llm.generate(
            builder.build_system_prompt(), builder.build_user_prompt(q, chunks)
        )
        await asyncio.sleep(judge_delay)

        try:
            scores = {
                "faithfulness": await judge.faithfulness(context, answer),
                "answer_relevancy": await judge.answer_relevancy(q, answer),
                "context_precision": await judge.context_precision(q, ref, context_texts),
                "context_recall": await judge.context_recall(ref, context),
            }
        except Exception as e:
            logger.warning("judge failed on %s: %s — skipping item", item["qid"], e)
            continue
        per_query.append(scores)
        logger.info("[%d/%d] %s %s", i + 1, len(items), item["qid"],
                    {k: round(v, 2) for k, v in scores.items()})

    agg = aggregate(per_query)
    return {"config": GENERATION_CONFIG, "metrics": agg, "n": len(per_query)}


def _doc_ids() -> list[str]:
    manifest = json.loads((REPO_ROOT / "eval" / "corpus" / "manifest.json").read_text())
    return [d["document_id"] for d in manifest["documents"].values()]


async def main() -> None:
    ap = argparse.ArgumentParser(description="Lumina eval harness")
    ap.add_argument("--retrieval-only", action="store_true",
                    help="skip generation + judge metrics (no LLM cost)")
    ap.add_argument("--judge-delay", type=float, default=13.0,
                    help="seconds between LLM calls (free tier is 5 RPM)")
    ap.add_argument("--mq-delay", type=float, default=13.0,
                    help="seconds between queries in query-transform configs")
    args = ap.parse_args()

    items = load_dataset()
    run: dict = {
        "timestamp": datetime.utcnow().isoformat(),
        "dataset_size": len(items),
        "retrieval": await eval_retrieval(items, mq_delay=args.mq_delay),
    }
    if not args.retrieval_only:
        run["generation"] = await eval_generation(items, args.judge_delay)

    RUNS_DIR.mkdir(exist_ok=True)
    out = RUNS_DIR / f"run_{run['timestamp'].replace(':', '-')}.json"
    slim = {**run, "retrieval": [
        {k: v for k, v in row.items() if k != "retrieved"} for row in run["retrieval"]
    ]}
    out.write_text(json.dumps(slim, indent=2))
    logger.info("Run written to %s", out)

    from eval.report import write_report

    write_report(slim, REPO_ROOT / "docs" / "eval.md")
    logger.info("Report written to docs/eval.md")


if __name__ == "__main__":
    asyncio.run(main())
