# Golden Dataset

Seed evaluation queries for the Enterprise AI Pipeline.

## Structure

- `queries/rag_general.jsonl` — General RAG queries with expected answers
- `queries/regression.jsonl` — Queries from production failures (grows over time)

## Format

Each line is a JSON object:
```json
{"query": "...", "expected_answer": "...", "tags": ["..."]}
```
