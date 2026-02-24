from __future__ import annotations

from src.pipeline.safety.pii_detector import PIIDetector


class TestPIIDetector:
    def setup_method(self):
        self.detector = PIIDetector()

    def test_detects_email(self):
        result = self.detector.detect("Contact me at john@example.com")
        assert result["has_pii"]
        assert "email" in result["types"]

    def test_detects_phone(self):
        result = self.detector.detect("Call me at (555) 123-4567")
        assert result["has_pii"]
        assert "phone_us" in result["types"]

    def test_detects_ssn(self):
        result = self.detector.detect("My SSN is 123-45-6789")
        assert result["has_pii"]
        assert "ssn" in result["types"]

    def test_detects_credit_card(self):
        result = self.detector.detect("Card number: 4111-1111-1111-1111")
        assert result["has_pii"]
        assert "credit_card" in result["types"]

    def test_detects_multiple_types(self):
        text = "Email: test@test.com, SSN: 123-45-6789, Phone: 555-123-4567"
        result = self.detector.detect(text)
        assert result["has_pii"]
        assert len(result["types"]) >= 3

    def test_no_pii_in_clean_text(self):
        result = self.detector.detect("What is the company refund policy?")
        assert not result["has_pii"]
        assert result["types"] == []

    def test_redact_email(self):
        redacted, result = self.detector.redact("Email me at john@example.com please")
        assert "[EMAIL_REDACTED]" in redacted
        assert "john@example.com" not in redacted
        assert result["has_pii"]

    def test_redact_ssn(self):
        redacted, _result = self.detector.redact("My SSN is 123-45-6789")
        assert "[SSN_REDACTED]" in redacted
        assert "123-45-6789" not in redacted

    def test_redact_preserves_clean_text(self):
        text = "What is the refund policy?"
        redacted, result = self.detector.redact(text)
        assert redacted == text
        assert not result["has_pii"]
