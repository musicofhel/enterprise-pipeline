"""Tests for the synthetic test dataset.

Validates that the synthetic dataset exists, has sufficient size,
and all entries have required fields.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SYNTHETIC_DATASET_PATH = Path("golden_dataset/synthetic_tests.jsonl")


@pytest.fixture
def synthetic_entries() -> list[dict]:
    """Load all entries from the synthetic dataset."""
    if not SYNTHETIC_DATASET_PATH.exists():
        pytest.skip("Synthetic dataset not generated yet")
    entries = []
    with open(SYNTHETIC_DATASET_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


class TestSyntheticDataset:
    """Tests for synthetic test data quality and coverage."""

    def test_dataset_exists(self) -> None:
        assert SYNTHETIC_DATASET_PATH.exists(), "Synthetic dataset not found — run generate_synthetic_tests.py"

    def test_minimum_50_cases(self, synthetic_entries: list[dict]) -> None:
        assert len(synthetic_entries) >= 50, f"Only {len(synthetic_entries)} cases, need >= 50"

    def test_all_entries_have_required_fields(self, synthetic_entries: list[dict]) -> None:
        required = {"query", "expected_route", "source_doc"}
        for i, entry in enumerate(synthetic_entries):
            missing = required - entry.keys()
            assert not missing, f"Entry {i} missing fields: {missing}"

    def test_queries_are_non_empty(self, synthetic_entries: list[dict]) -> None:
        for i, entry in enumerate(synthetic_entries):
            assert entry["query"].strip(), f"Entry {i} has empty query"

    def test_multiple_source_docs(self, synthetic_entries: list[dict]) -> None:
        sources = {e["source_doc"] for e in synthetic_entries}
        assert len(sources) >= 5, f"Only {len(sources)} source docs, need >= 5 for diversity"

    def test_has_out_of_scope_cases(self, synthetic_entries: list[dict]) -> None:
        oos = [e for e in synthetic_entries if e.get("out_of_scope")]
        assert len(oos) >= 3, f"Only {len(oos)} out-of-scope cases, need >= 3"

    def test_routes_are_valid(self, synthetic_entries: list[dict]) -> None:
        valid_routes = {"rag_knowledge_base", "direct_llm", "sql_structured_data", "api_lookup", "escalate_human"}
        for i, entry in enumerate(synthetic_entries):
            assert entry["expected_route"] in valid_routes, f"Entry {i} has invalid route: {entry['expected_route']}"
