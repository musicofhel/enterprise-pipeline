# ISSUE-005: Validate multi-query expansion recall improvement with live retrieval

**Priority:** P1 — before Wave 3 quality measurement
**Status:** Open
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

Wave 2 EC-4 ("Multi-query expansion improves recall by >=20%") was validated with simulated document sets using random number generation. The RRF algorithm is correct, but we have no evidence that:

1. The LLM-generated query rephrasings actually retrieve different relevant documents
2. The recall improvement holds on our corpus
3. The 4x retrieval cost (original + 3 variants) is justified by the quality gain

## Acceptance Criteria

- [ ] Ingest golden_dataset documents into Qdrant
- [ ] Run 50+ queries with and without multi-query expansion
- [ ] Measure Recall@10 and Recall@20 for both conditions
- [ ] Improvement must be >=20% to close EC-4
- [ ] If <20%, investigate: adjust num_queries? change expansion prompt? try different LLM?
- [ ] Document cost/latency impact vs. recall gain

## Blocked By

- Qdrant with ingested documents
- Valid OPENROUTER_API_KEY in .env

## Blocks

- Wave 3 quality measurement baseline
