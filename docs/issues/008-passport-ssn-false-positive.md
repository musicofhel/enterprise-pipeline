# ISSUE-008: Passport number triggers SSN false positive

**Priority:** P3 — low severity, user friction
**Status:** Open
**Owner:** Security Engineer
**Created:** 2026-02-24
**Found in:** Wave 2 verification follow-up

## Problem

Input `"My passport number is 531234567"` correctly detects `passport` but also false-positives as `ssn` because the passport number is 9 contiguous digits, which matches the SSN regex `\d{3}[-\s]?\d{2}[-\s]?\d{4}`.

The redacted output becomes: `"My [PASSPORT_REDACTED] is [SSN_REDACTED]"` — double-redacting the same value with two different labels.

This also applies to any 9-digit number that happens to appear after a passport keyword. The same class of problem exists for other patterns — `078051120` (a no-delimiter SSN) could also be misidentified as a phone number.

## Suggested Fix

Two options:

**Option A — Span-based conflict resolution:** Track the character spans each pattern matches. If two patterns match overlapping spans, keep the one with higher specificity (keyword-anchored patterns like `passport` beat format-only patterns like `ssn`).

**Option B — Negative lookbehind on SSN:** Add a negative lookbehind to the SSN regex that excludes matches preceded by "passport" keyword context. Simpler but fragile — breaks if new PII types with 9-digit values are added.

Recommend Option A for correctness.

## Acceptance Criteria

- [ ] `"My passport number is 531234567"` detects only `passport`, not `ssn`
- [ ] Other SSN inputs (e.g., `"My SSN is 078-05-1120"`) still detected correctly
- [ ] No regressions on existing 16 PII test patterns (EC-2)

## Affects

- User friction from over-redaction in production
- Does not block any wave
