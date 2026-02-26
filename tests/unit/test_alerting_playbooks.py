"""Tests for alerting playbooks (Deliverable 6.5)."""
from __future__ import annotations

import re
from pathlib import Path

PLAYBOOK_PATH = Path("docs/runbooks/alerting-playbooks.md")

# All Prometheus alert conditions referenced in our metrics
EXPECTED_ALERTS = [
    "Retrieval Quality p50 Drop >10%",
    "Retrieval Empty Result Rate >5%",
    "Retrieval p95 Below 0.3",
    "HHEM Faithfulness Below Threshold",
    "HHEM Faithfulness in Warning Zone",
    "Embedding Drift Detected",
    "Retrieval Quality p50 Drop >5%",
    "Daily Ragas Scores Declining",
    "Shadow Mode Circuit Breaker Triggered",
    "LLM Cost Spike",
    "Injection Attempt Spike",
]

REQUIRED_SECTIONS = ["Trigger", "Investigation", "Remediation"]


class TestAlertingPlaybooks:
    def test_playbook_exists(self) -> None:
        """Playbook file exists."""
        assert PLAYBOOK_PATH.exists(), f"Playbook not found at {PLAYBOOK_PATH}"

    def test_every_alert_has_playbook(self) -> None:
        """Every expected alert has a matching section in the playbook."""
        content = PLAYBOOK_PATH.read_text()
        for alert in EXPECTED_ALERTS:
            assert alert in content, f"Missing playbook for alert: {alert}"

    def test_every_playbook_has_required_sections(self) -> None:
        """Every playbook section has Trigger, Investigation, and Remediation."""
        content = PLAYBOOK_PATH.read_text()

        # Split into sections by ## headers
        sections = re.split(r"\n## ", content)
        playbook_sections = [s for s in sections if (s.strip() and "CRITICAL:" in s) or "WARN:" in s]

        assert len(playbook_sections) >= len(EXPECTED_ALERTS), (
            f"Expected {len(EXPECTED_ALERTS)} playbook sections, found {len(playbook_sections)}"
        )

        for section in playbook_sections:
            section_title = section.split("\n")[0].strip()
            for req in REQUIRED_SECTIONS:
                assert f"**{req}:**" in section or f"**{req}**" in section, (
                    f"Section '{section_title}' missing '{req}' subsection"
                )
