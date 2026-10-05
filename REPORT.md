# Report: what ended up in the graph, and what did not

_Status: skeleton. Filled in after the first 100+ document sync and the edit/add/delete re-sync._

## Corpus and method

- Source project, document counts (issues, merge requests), sync 1 and sync 2 numbers.
- Extraction: cognee GLiNER demo (`fastino/gliner2.5-base-v1`), embeddings fastembed `BAAI/bge-small-en-v1.5`, no LLM key.
- How "answered" is judged: `recall()` without an LLM returns chunks; a question counts as answered when the fact is in the top 5 returned chunks.
- All counts come from `scripts/graph_report.sql` against the `postgres_demo` tables.

## 1. Node types and edge types, with counts

## 2. The ten most connected nodes: meaningful or noise?

## 3. Five correct and five wrong extracted relationships, with source text

## 4. What the extraction missed that a reader would expect

## 5. Three questions the graph can answer and three it cannot (queries included)

## 6. The one change I would make first, and why

## Appendix: the second sync (edit one, add one, delete one)
