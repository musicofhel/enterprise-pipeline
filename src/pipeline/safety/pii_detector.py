from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()

# PII patterns -- comprehensive but not exhaustive
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_us": re.compile(r"(?<!\d)(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
    "ssn": re.compile(r"(?<!\d)\d{3}[-\s]?\d{2}[-\s]?\d{4}(?!\d)"),
    "credit_card": re.compile(r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)"),
    "ip_address": re.compile(r"(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)"),
    "date_of_birth": re.compile(r"(?i)(dob|date\s+of\s+birth|born\s+on)\s*:?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"),
    "passport": re.compile(r"(?i)(passport\s*(number|no|#)?)\s*:?\s*[A-Z0-9]{6,9}"),
    "drivers_license": re.compile(r"(?i)(driver'?s?\s*licen[sc]e\s*(number|no|#)?|DL\s*#?|licen[sc]e\s*(number|no|#))\s*:?\s*[A-Z0-9]{5,15}"),
}


class PIIDetector:
    """Detect PII in text using regex patterns. Lakera Guard PII module is Layer 2."""

    def __init__(
        self,
        patterns: dict[str, re.Pattern[str]] | None = None,
    ) -> None:
        self._patterns = patterns or PII_PATTERNS

    def detect(self, text: str) -> dict[str, Any]:
        """Detect PII types present in text."""
        found_types: list[str] = []

        for pii_type, pattern in self._patterns.items():
            if pattern.search(text):
                found_types.append(pii_type)

        return {
            "has_pii": len(found_types) > 0,
            "types": found_types,
        }

    def redact(self, text: str) -> tuple[str, dict[str, Any]]:
        """Redact detected PII from text. Returns (redacted_text, detection_result)."""
        redacted = text
        found_types: list[str] = []

        for pii_type, pattern in self._patterns.items():
            if pattern.search(redacted):
                found_types.append(pii_type)
                redacted = pattern.sub(f"[{pii_type.upper()}_REDACTED]", redacted)

        return redacted, {
            "has_pii": len(found_types) > 0,
            "types": found_types,
        }
