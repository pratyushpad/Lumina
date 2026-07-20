"""ChatService turn orchestration: event order, the refusal short-circuit, and
error containment. Persistence and the LLM are faked so these stay DB-free."""
import json

import pytest

from app.services import chat_service as cs
from app.services.chat_service import ChatService, Turn
from app.services.generation.providers.base import GenResult
from app.services.retrieval.types import RetrievalResult
from app.services.tracing import Tracer


def _result(chunk_id="c1", score=0.9) -> RetrievalResult:
    r = RetrievalResult(
        chunk_id=chunk_id,
        document_id="doc1",
        text="Residual connections ease optimization of very deep networks.",
        page_num=1,
        filename="resnet.pdf",
        distance=0.1,
    )
    r.relevance_score = score
    return r


def _turn(query="why residual connections?") -> Turn:
    chunks = [_result()]
    t = Turn(
        query=query,
        session_id="s1",
        tracer=Tracer(query, session_id="s1"),
        chunks=chunks,
        retrieval_ms=12,
    )
    t.citations = [cs.to_citation(c) for c in chunks]
    return t


class _FakeLLM:
    def __init__(self, tokens=("Residual ", "connections ", "help.")):
        self.tokens = tokens
        self.called = False

    async def generate_stream_events(self, system, user):
        self.called = True
        for tok in self.tokens:
            yield tok
        yield GenResult(
            text="".join(self.tokens),
            prompt_tokens=100,
            completion_tokens=3,
            duration_s=0.5,
            provider="local",
            model="llama-3.3-70b-versatile",
        )


@pytest.fixture
def patched(monkeypatch):
    """Wire ChatService to fakes: fixed retrieval, no DB, a scripted LLM."""
    llm = _FakeLLM()
    turn = _turn()

    async def fake_retrieve(self, query, session_id, document_ids):
        turn.query = query
        return turn

    async def fake_persist(self, turn, answer, model_used, gen_ms, citations=None):
        fake_persist.calls.append(
            {"answer": answer, "model_used": model_used, "gen_ms": gen_ms}
        )
        return "msg-1"

    fake_persist.calls = []

    monkeypatch.setattr(ChatService, "retrieve", fake_retrieve)
    monkeypatch.setattr(ChatService, "persist_turn", fake_persist)
    monkeypatch.setattr(ChatService, "build_prompt", lambda self, t: ("sys", "usr"))
    monkeypatch.setattr(cs.LLMService, "get", classmethod(lambda cls: llm))
    return {"llm": llm, "turn": turn, "persist": fake_persist}


async def _collect(agen):
    return [json.loads(ev["data"]) async for ev in agen]


@pytest.mark.asyncio
async def test_stream_emits_citations_tokens_meta_then_done(patched, monkeypatch):
    monkeypatch.setattr(ChatService, "should_refuse", lambda self, t: False)
    events = await _collect(ChatService().stream("q", "s1", ["doc1"]))

    kinds = [e["type"] for e in events]
    assert kinds[0] == "citations"
    assert kinds[-1] == "done"
    assert kinds.count("token") == 3
    # citations must precede every token so the UI can render chips first
    assert kinds.index("citations") < kinds.index("token")
    assert kinds.index("meta") == len(kinds) - 2
    assert events[-1]["data"]["message_id"] == "msg-1"
    assert patched["persist"].calls[0]["answer"] == "Residual connections help."


@pytest.mark.asyncio
async def test_refusal_short_circuits_before_the_llm(patched, monkeypatch):
    monkeypatch.setattr(ChatService, "should_refuse", lambda self, t: True)
    events = await _collect(ChatService().stream("capital of France?", "s1", ["doc1"]))

    assert [e["type"] for e in events] == ["refusal", "done"]
    assert events[0]["data"] == cs.REFUSAL_MESSAGE
    # The whole point of the gate: no tokens are spent on an unanswerable query.
    assert patched["llm"].called is False
    assert patched["persist"].calls[0]["model_used"] == cs.REFUSAL_LABEL


@pytest.mark.asyncio
async def test_stream_failure_does_not_leak_internals(patched, monkeypatch):
    def boom(self, t):
        raise RuntimeError("asyncpg://user:hunter2@db.internal timed out")

    monkeypatch.setattr(ChatService, "should_refuse", boom)
    events = await _collect(ChatService().stream("q", "s1", ["doc1"]))

    assert events[-1]["type"] == "error"
    assert events[-1]["data"] == cs.STREAM_ERROR_MESSAGE
    assert "hunter2" not in json.dumps(events)
    assert "asyncpg" not in json.dumps(events)


@pytest.mark.asyncio
async def test_blocking_answer_matches_stream_content(patched, monkeypatch):
    monkeypatch.setattr(ChatService, "should_refuse", lambda self, t: False)

    async def fake_generate_result(system, user):
        return GenResult(
            text="Residual connections help.",
            prompt_tokens=100,
            completion_tokens=3,
            duration_s=0.5,
            provider="local",
            model="llama-3.3-70b-versatile",
        )

    patched["llm"].generate_result = fake_generate_result
    msg_id, content, citations, retrieval_ms, gen_ms, model = await ChatService().answer(
        "q", "s1", ["doc1"]
    )

    assert msg_id == "msg-1"
    assert content == "Residual connections help."
    assert model == "local:llama-3.3-70b-versatile"
    assert retrieval_ms == 12
    assert gen_ms == 500
    assert citations[0].filename == "resnet.pdf"
