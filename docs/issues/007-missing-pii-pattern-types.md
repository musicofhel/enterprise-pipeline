# ISSUE-007: Missing PII pattern types — addresses, IBANs, API tokens, MRNs

**Priority:** P2 — compliance gap before Wave 4
**Status:** Open
**Owner:** Security Engineer
**Created:** 2026-02-24
**Found in:** Wave 2 verification follow-up

## Problem

The PII detector (`src/pipeline/safety/pii_detector.py`) has 8 regex patterns but is missing 4 PII categories that appeared in the hard-case verification test:

1. **Street/mailing addresses** — "1423 Elm Street, Apt 4B, Charlotte NC 28202" was undetected
2. **IBAN / international bank account numbers** — "GB29 NWBK 6016 1331 9268 19" was undetected
3. **API keys / bearer tokens / secrets** — "sk-proj-abc123def456ghi789" was undetected
4. **Medical record numbers (MRN)** — "MRN 4421890" was undetected

Hard-case test result: 6/10 inputs had their expected PII caught. The 4 misses are all due to missing patterns, not broken patterns.

## Suggested Fix

**IBANs** — Regex-solvable. IBAN format is well-defined: 2 letter country code + 2 check digits + up to 30 alphanumeric BBAN characters. Pattern: `[A-Z]{2}\d{2}\s?[A-Z0-9]{4}(\s?[A-Z0-9]{4}){2,7}(\s?[A-Z0-9]{1,4})?`

**API keys/tokens** — Regex-solvable for known prefixes. Common patterns:
- `sk-proj-[a-zA-Z0-9]+` (OpenAI project keys)
- `sk-[a-zA-Z0-9]{20,}` (OpenAI legacy keys)
- `ghp_[a-zA-Z0-9]{36}` (GitHub PATs)
- `Bearer\s+[a-zA-Z0-9._\-]+` (generic bearer tokens)
- `AKIA[A-Z0-9]{16}` (AWS access keys)

**Addresses** — Hard for regex. US addresses have too many formats. Best handled by Lakera Guard PII module (L2) or a dedicated NER model (spaCy/Presidio).

**MRNs** — Facility-specific format, no universal pattern. Best handled by keyword proximity (e.g., "MRN" near a digit string) or Lakera L2.

## Acceptance Criteria

- [ ] IBAN pattern added and tested
- [ ] API key/token patterns added for at least OpenAI, GitHub, AWS prefixes
- [ ] Address and MRN documented as "L2/NER only" in PIIDetector docstring
- [ ] Re-run hard-case test — target 8/10 inputs caught (addresses and MRNs remain L2 scope)

## Affects

- Wave 4 compliance (FR-503 audit logging, FR-103 PII redaction before logging)
- Does not block Wave 3
