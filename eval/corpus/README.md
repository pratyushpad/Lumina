# Eval Corpus

Fixed document set for the Lumina evaluation harness. Ingested deterministically by
`make ingest` (sorted filename order, sha256-derived document ids, deterministic
chunking) into the `eval-corpus` session; `manifest.json` (generated) records the
chunk ids each run produces so `eval/dataset.jsonl` can reference ground-truth
chunks stably.

| File | Source | License / provenance |
|---|---|---|
| `attention_is_all_you_need.pdf` | arXiv:1706.03762v7 (Vaswani et al., 2017) | arXiv.org perpetual non-exclusive license; figure- and table-heavy — exercises PDF image extraction |
| `rag_knowledge_intensive_nlp.pdf` | arXiv:2005.11401v4 (Lewis et al., 2020) | arXiv.org perpetual non-exclusive license |
| `lumina_design_doc.md` | Authored for this project | Original |
| `rag_evaluation_guide.md` | Authored for this project | Original |

Do not edit these files after the eval set is frozen — chunk ids derive from their
content and order, and `dataset.jsonl` references those ids.
