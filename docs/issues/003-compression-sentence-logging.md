# ISSUE-003: Log dropped sentences in BM25 compression for Wave 3 debugging

**Priority:** P1 — before Wave 3 HHEM integration
**Status:** Open → Fixed (see commit)
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

BM25 compression hits 71.9% — nearly double the 40% target. This is great for tokens but may be dropping sentences the LLM actually needs for faithful answers.

When Wave 3 starts scoring faithfulness with HHEM, the first failure mode to investigate is "did compression cut relevant context?" Without logging which sentences were dropped, this is impossible to debug.

## Fix

Add debug-level logging to `BM25Compressor.compress()` that records:
- Which sentences were kept (indices + text)
- Which were dropped (indices + text)
- BM25 scores for all sentences
- The query they were scored against

This doesn't change any behavior — purely observability for Wave 3 debugging.
