# ISSUE-011: Natural language PII is beyond regex scope — document known limitation

**Priority:** P3 — known limitation, documentation only
**Status:** Open
**Owner:** Security Engineer
**Created:** 2026-02-24
**Found in:** Wave 2 verification follow-up

## Problem

Input `"My social is oh seven eight oh five eleven twenty"` (SSN expressed in natural language words) was not detected by the PII detector. This is fundamentally impossible for regex — the detector would need to:

1. Recognize "oh" as "0", "seven" as "7", etc.
2. Reconstruct the digit sequence from word tokens
3. Validate the reconstructed sequence as an SSN

This requires either:
- A dedicated NER model trained on natural-language PII (e.g., Presidio with a custom recognizer, or spaCy NER)
- Lakera Guard's PII module (already wired as L2 but untested)
- An LLM-based PII detector (expensive, high latency)

## Current State

The PIIDetector docstring says "Lakera Guard PII module is Layer 2" but does not explicitly state that natural-language numbers are out of scope for L1. This should be documented.

## Acceptance Criteria

- [ ] Update PIIDetector class docstring to state: "L1 regex detects formatted PII only (digits, dashes, standard patterns). Natural-language numbers ('oh seven eight...') require L2 (Lakera Guard PII module) or a dedicated NER model."
- [ ] If compliance requirements demand catching natural-language PII, evaluate Lakera PII module or Presidio NER as L2 PII detection (separate from L2 injection detection)

## Affects

- Compliance posture for Wave 4 (FR-103: PII detection and redaction)
- Does not block Wave 3
