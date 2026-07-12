# A Practical Guide to Evaluating Retrieval-Augmented Generation

## Why evaluation is the hard part

A RAG system that "seems to work" is worthless as evidence. Retrieval quality and
answer quality must be measured separately, because a fluent answer can be built
on the wrong evidence and a correct retrieval can still be summarized badly. The
standard practice is a fixed evaluation set of questions with known ground-truth
source passages, kept frozen so that every pipeline change is measured against
the same target.

## Retrieval metrics

Recall at k measures the fraction of ground-truth relevant chunks that appear in
the top k retrieved results, averaged over questions. It answers the question
"did the right evidence show up at all". Mean Reciprocal Rank, abbreviated MRR,
is the average over questions of one divided by the rank of the first relevant
chunk; it rewards putting a correct passage at the very top. Normalized
Discounted Cumulative Gain at 10, abbreviated NDCG at 10, sums graded relevance
discounted by the logarithm of the rank position and normalizes by the ideal
ordering, so it rewards ranking all relevant evidence high rather than just the
first hit.

A practical rule of thumb: recall at k is the ceiling on answer quality, because
the generator cannot cite what was never retrieved. Improve recall first, then
precision of the top ranks.

## Generation metrics in the RAGAS family

Faithfulness measures whether every claim in the generated answer is supported by
the retrieved context; it is estimated by decomposing the answer into atomic
statements and checking each statement against the context with a judge model.
Answer relevancy measures whether the answer actually addresses the question
rather than being on-topic filler. Context precision measures what fraction of
the retrieved chunks were actually useful for answering, penalizing padded
context windows. Context recall measures whether the retrieved context covers
the reference answer, penalizing missing evidence.

Judge-model scores come with a caveat: when the same model family generates the
answers and judges them, scores are systematically inflated. This is called
self-evaluation bias. Cross-model judging, where a different model family grades
the answers, is the honest configuration when it is available.

## The ablation table

The single most informative artifact in a RAG evaluation is an ablation table:
one row per pipeline configuration, starting from a dense-only baseline and
adding one component at a time — hybrid sparse-plus-dense fusion, then a
cross-encoder reranker, then query rewriting. Each row reports the same metric
columns. The table attributes improvement to specific components and exposes
components that cost latency without moving quality. A configuration change that
does not move any metric should be reverted, no matter how fashionable it is.

## Common failure modes

Chunking failures dominate in practice. Chunks that cut tables in half, or that
split a definition from its term, produce retrievals that look relevant but
cannot support a complete answer. Tokenization mismatches between the index side
and the query side silently zero out sparse retrieval. Finally, evaluation sets
drafted by a language model and never verified by a human tend to contain
questions whose stated ground-truth chunk does not actually contain the answer;
every generated item must be checked against its source chunk before it enters
the frozen set.
