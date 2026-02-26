# Golden Dataset

Evaluation datasets for the Enterprise AI Pipeline.

## Files

| File | Cases | Purpose |
|------|-------|---------|
| `faithfulness_tests.jsonl` | 20 | DeepEval FaithfulnessMetric — 4 categories: grounded (5), subtle_hallucination (5), partial (5), edge_case (5) |
| `queries/rag_general.jsonl` | — | General RAG queries with expected answers |
| `queries/regression.jsonl` | — | Queries from production failures (grows over time) |
| `annotations/` | — | Human annotation data |

## Format

### faithfulness_tests.jsonl

Each line is a JSON object:
```json
{
  "id": "G01",
  "category": "grounded",
  "query": "...",
  "context": ["chunk1", "chunk2"],
  "expected_answer": "...",
  "expected_faithfulness": 0.95
}
```

Categories:
- **grounded** — answers fully supported by context (should score high)
- **subtle_hallucination** — wrong numbers, dates, or invented facts (should score low)
- **partial** — mix of grounded and fabricated claims
- **edge_case** — empty context, very long context, ambiguous queries

### queries/*.jsonl

```json
{"query": "...", "expected_answer": "...", "tags": ["..."]}
```

## Usage

```bash
# Run faithfulness eval (needs OPENROUTER_API_KEY)
pytest tests/eval/test_faithfulness.py -v

# conftest.py auto-bridges OPENROUTER_API_KEY → OPENAI_API_KEY + OPENAI_BASE_URL
# CI only needs one secret: OPENROUTER_API_KEY
```
