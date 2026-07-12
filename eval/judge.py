"""RAGAS-style generation metrics via LLM-judge rubric prompts.

Implements the four RAGAS metric definitions (faithfulness, answer relevancy,
context precision, context recall) as direct judge prompts against the Gemini
API — no framework dependency, every prompt inspectable below.

Honesty caveats (also stated in MODEL_CARD.md):
- The judge is Gemini and the generator is Gemini: same-family judging inflates
  scores (self-evaluation bias). Treat absolute values with skepticism; the
  ablation DELTAS between configs are the meaningful signal.
- Calls are throttled (JUDGE_DELAY_S between calls) for free-tier rate limits.
"""
import asyncio
import json
import logging
import re

logger = logging.getLogger("lumina.eval.judge")

JUDGE_DELAY_S = 2.0

_JSON_RE = re.compile(r"\{[^{}]*\}")

_FAITHFULNESS = """You are grading a RAG system's answer for FAITHFULNESS.
Decompose the ANSWER into its atomic factual statements. For each statement,
decide whether it is supported by the CONTEXT (directly stated or a clear
paraphrase). Opinions explicitly labeled as such are excluded from grading.

CONTEXT:
{context}

ANSWER:
{answer}

Return ONLY JSON: {{"supported": <number of supported statements>, "total": <total statements>}}"""

_ANSWER_RELEVANCY = """You are grading how well an ANSWER addresses a QUESTION.
Score 1.0 if the answer directly and completely addresses the question,
0.5 if it partially addresses it or pads with off-topic content,
0.0 if it does not address the question. Intermediate values allowed.

QUESTION: {question}

ANSWER:
{answer}

Return ONLY JSON: {{"score": <0.0-1.0>}}"""

_CONTEXT_PRECISION = """You are grading retrieved CONTEXT CHUNKS for a QUESTION with a known REFERENCE answer.
For each chunk, decide if it is USEFUL for producing the reference answer
(contains part of the needed evidence).

QUESTION: {question}
REFERENCE ANSWER: {reference}

CHUNKS:
{chunks}

Return ONLY JSON: {{"useful": <number of useful chunks>, "total": <total chunks>}}"""

_CONTEXT_RECALL = """You are grading whether retrieved CONTEXT covers a REFERENCE answer.
Decompose the REFERENCE answer into its atomic factual statements. For each,
decide whether the CONTEXT contains the evidence for it.

REFERENCE ANSWER: {reference}

CONTEXT:
{context}

Return ONLY JSON: {{"covered": <number of covered statements>, "total": <total statements>}}"""


def _parse_json(text: str) -> dict:
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError(f"judge returned no JSON: {text[:200]!r}")
    return json.loads(m.group(0))


class Judge:
    """Thin wrapper around the app's LLM service with throttling."""

    def __init__(self, llm_generate, delay_s: float = JUDGE_DELAY_S):
        # llm_generate: async (system, user) -> (text, meta)
        self._generate = llm_generate
        self._delay_s = delay_s

    async def _ask(self, prompt: str) -> dict:
        text, _ = await self._generate(
            "You are a strict, literal grader. Output only the requested JSON.", prompt
        )
        await asyncio.sleep(self._delay_s)
        return _parse_json(text)

    async def faithfulness(self, context: str, answer: str) -> float:
        r = await self._ask(_FAITHFULNESS.format(context=context, answer=answer))
        return r["supported"] / r["total"] if r.get("total") else 0.0

    async def answer_relevancy(self, question: str, answer: str) -> float:
        r = await self._ask(_ANSWER_RELEVANCY.format(question=question, answer=answer))
        return float(r.get("score", 0.0))

    async def context_precision(self, question: str, reference: str, chunks: list[str]) -> float:
        numbered = "\n\n".join(f"[chunk {i+1}]\n{c}" for i, c in enumerate(chunks))
        r = await self._ask(
            _CONTEXT_PRECISION.format(question=question, reference=reference, chunks=numbered)
        )
        return r["useful"] / r["total"] if r.get("total") else 0.0

    async def context_recall(self, reference: str, context: str) -> float:
        r = await self._ask(_CONTEXT_RECALL.format(reference=reference, context=context))
        return r["covered"] / r["total"] if r.get("total") else 0.0
