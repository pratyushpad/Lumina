from app.services.retrieval.sparse import bm25_rank_corpus, tokenize


def _corpus(docs: dict[str, str]) -> list[tuple[str, list[str]]]:
    return [(cid, tokenize(text)) for cid, text in docs.items()]


def test_tokenizer_lowercases_and_strips_punctuation_and_stopwords():
    assert tokenize("The QUICK, brown fox!") == ["quick", "brown", "fox"]
    assert tokenize("") == []


def test_bm25_ranks_exact_term_match_first():
    corpus = _corpus(
        {
            "c1": "The reciprocal rank fusion algorithm combines ranked lists.",
            "c2": "Postgres provides full text search with tsvector columns.",
            "c3": "Cats sleep most of the day and hunt at night.",
        }
    )
    ranked = bm25_rank_corpus("reciprocal rank fusion", corpus, top_k=3)
    assert ranked[0][0] == "c1"
    # c3 shares no terms with the query — must not appear (score <= 0 filtered)
    assert all(cid != "c3" for cid, _ in ranked)


def test_bm25_idf_prefers_rare_term_document():
    # "pgvector" appears once in the corpus; "search" appears everywhere.
    corpus = _corpus(
        {
            "common1": "search systems and search engines do search ranking",
            "common2": "search interfaces improve search experiences",
            "rare": "pgvector adds vector similarity search to Postgres",
        }
    )
    ranked = bm25_rank_corpus("pgvector search", corpus, top_k=3)
    assert ranked[0][0] == "rare"


def test_bm25_known_expected_order():
    corpus = _corpus(
        {
            "a": "hybrid retrieval fuses bm25 and dense embeddings",
            "b": "dense embeddings capture semantic similarity",
            "c": "bm25 is a lexical ranking function",
        }
    )
    ranked = bm25_rank_corpus("bm25 lexical ranking", corpus, top_k=3)
    ids = [cid for cid, _ in ranked]
    assert ids[0] == "c"  # matches all three query terms
    assert "a" in ids and "b" not in ids  # b shares no query terms


def test_bm25_empty_inputs():
    assert bm25_rank_corpus("anything", [], top_k=5) == []
    corpus = _corpus({"x": "some text"})
    assert bm25_rank_corpus("", corpus, top_k=5) == []


def test_bm25_top_k_truncates():
    corpus = _corpus({f"c{i}": f"retrieval document number {i}" for i in range(10)})
    ranked = bm25_rank_corpus("retrieval document", corpus, top_k=3)
    assert len(ranked) == 3
