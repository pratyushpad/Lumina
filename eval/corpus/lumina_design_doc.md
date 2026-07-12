# Lumina System Design Document

## Overview

Lumina is a multimodal retrieval-augmented generation platform. Users upload PDF,
text, markdown, or image documents into isolated sessions, then ask questions that
are answered strictly from the uploaded material with inline citations to the
source document and page number.

## Ingestion pipeline

Uploaded files pass through a three-stage ingestion pipeline. The parser extracts
text blocks, tables, and embedded images using PyMuPDF and pdfplumber. Extracted
images are saved to a processed-images directory and served statically to the
frontend. The chunker splits text blocks into overlapping chunks; the default
strategy is recursive splitting, which prefers paragraph boundaries, then line
breaks, then sentence boundaries, with a chunk size of 800 characters and an
overlap of 150 characters. Tables are never split: each extracted table becomes a
single chunk regardless of length. Image regions produce dedicated image-caption
chunks flagged with the path of the associated image.

Two alternative chunking strategies exist for experimentation. The fixed strategy
cuts hard character windows with overlap and ignores document structure entirely.
The semantic strategy embeds individual sentences and places chunk boundaries
where the cosine similarity between consecutive sentences drops below the 25th
percentile of the document's similarity distribution.

## Retrieval subsystem

Retrieval is hybrid. The dense channel embeds the query with the all-MiniLM-L6-v2
sentence transformer, which produces 384-dimensional normalized vectors, and
searches a pgvector HNSW index using cosine distance. The sparse channel uses the
Okapi BM25 ranking function computed in-process over tokenized chunks with a
shared lowercase alphanumeric tokenizer; a Postgres full-text-search alternative
based on ts_rank_cd can be selected instead. The two ranked lists are fused with
Reciprocal Rank Fusion, where each list contributes one divided by the quantity
sixty plus rank. The fused top fifty candidates are passed to a cross-encoder
reranker, ms-marco-MiniLM-L-6-v2, which scores each query-chunk pair directly;
the top five reranked chunks become the generation context.

Optional query transformations widen recall before retrieval. Multi-query
rewriting asks the language model for three alternative phrasings and fuses the
result lists of all four queries. HyDE generates a hypothetical answer passage
and embeds that passage in place of the raw query for the dense channel only.

## Storage

All application state lives in a single PostgreSQL database with the pgvector
extension. The chunks table stores chunk text, metadata, a generated tsvector
column for full-text search, and the 384-dimensional embedding. Chunk deletion
cascades from document deletion, and document deletion cascades from session
deletion. Uploaded originals are kept on disk under a per-session upload
directory, and extracted images under the processed directory.

## Session model

Every conversation happens inside a session. A session owns its documents and
its message history. Retrieval is always scoped to the documents of the active
session: both the dense SQL query and the BM25 candidate set filter by the
session's document identifiers before any scoring happens, so content from one
session can never appear in another session's answers.
