# Wave 7 Retrospective — Data Flywheel & Continuous Improvement

**Date:** 2026-02-26
**Tests:** 352 passed, 21 skipped (DeepEval API key)

## Exit Criteria

| EC | Description | Status |
|----|-------------|--------|
| EC-1 | Feedback collected with stats + Prometheus metrics | PASS — FeedbackStatsResponse, 3 metrics, Grafana panels |
| EC-2 | Weekly failure triage produces classified report | PASS — 6 categories, clustering, top failures |
| EC-3 | Annotation pipeline: generate, submit, export | PASS — pending/completed dirs, audit trail, JSONL export |
| EC-4 | Golden dataset grows with dedup + versioning | PASS — metadata.json versioning, embedding dedup |
| EC-5 | Eval suite covers all known failure patterns | PASS — coverage report, auto-expansion from annotations |

## What Worked

- **Decomposition**: Each deliverable built cleanly on the previous one. Triage feeds annotation, annotation feeds dataset, dataset feeds eval expansion.
- **Local-first**: No Argilla/Lilac dependency. File-based annotation is simpler and testable.
- **Fast iteration**: 34 new tests written and passing in a single session.
- **Embedding dedup**: Cosine similarity threshold (0.95) prevents near-duplicate pollution.

## What Surprised

- **mypy sorted() key lambda**: `sorted(..., key=lambda f: f.get("x") if ... else float("inf"))` fails mypy because `dict.get()` returns `Any | None` which isn't `SupportsDunderLT`. Must wrap with `float()`.
- **Clustering threshold sensitivity**: Mock embeddings with shared tails ([0.1]*381) had enough overlap to merge distinct clusters. Needed orthogonal vectors for clean separation.

## What We'd Do Differently

- The annotation CLI is functional but minimal. For a team workflow, a web UI (or Argilla) would be more ergonomic.
- Clustering currently uses greedy assignment. DBSCAN or HDBSCAN would handle variable-density clusters better.
- Feedback rate tracking uses in-memory deques — doesn't survive process restarts. A persistent counter (Redis/file) would be more robust.

## Deferred Items

- Real embedding model for clustering (currently uses caller-supplied `embed_fn`)
- Argilla export format for team annotation workflows
- Automated prompt improvement suggestions based on failure patterns
- Integration with shadow mode: failures → annotation → prompt change → shadow test → promote

## Stage Assessment

| Component | Status |
|-----------|--------|
| FeedbackService extended | Real (file-based, Prometheus) |
| FailureTriageService | Real (trace scanning, classification, clustering) |
| AnnotationService | Real (file-based, audit trail) |
| GoldenDatasetManager | Real (dedup, versioning, JSONL export) |
| EvalSuiteExpander | Real (coverage report, auto-expansion) |
| Weekly flywheel script | Real (end-to-end automation) |
