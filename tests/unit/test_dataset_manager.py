"""Tests for golden dataset expansion (Wave 7.4).

Covers import, dedup, validation, versioning, export formats, and coverage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.flywheel.dataset_manager import GoldenDatasetManager


def _make_annotation(
    trace_id: str,
    query: str,
    correct_answer: str,
    category: str = "hallucination",
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "query": query,
        "context": ["Some context chunk."],
        "answer_given": "Wrong answer.",
        "faithfulness_score": 0.3,
        "category": category,
        "annotation": {
            "correct_answer": correct_answer,
            "failure_type": category,
            "notes": None,
            "annotator": "human",
            "annotated_at": "2026-02-25T00:00:00+00:00",
        },
    }


def _write_annotations(dir_path: Path, annotations: list[dict[str, Any]]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    for a in annotations:
        path = dir_path / f"{a['trace_id']}.json"
        path.write_text(json.dumps(a, indent=2))


def _seed_dataset(dataset_dir: Path, n: int = 20) -> None:
    """Seed the golden dataset with N existing examples."""
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # Create faithfulness_tests.jsonl
    lines = []
    for i in range(n):
        lines.append(json.dumps({
            "id": f"seed-{i}",
            "category": "hallucination" if i % 2 == 0 else "retrieval_failure",
            "query": f"Seed query number {i}",
            "context": ["seed context"],
            "expected_answer": f"Seed answer {i}",
            "expected_faithfulness": 0.9,
            "source": "manual",
        }))
    (dataset_dir / "faithfulness_tests.jsonl").write_text("\n".join(lines) + "\n")

    # Create metadata
    meta = {
        "version": "1.0.0",
        "last_updated": "2026-02-01",
        "total_examples": n,
        "by_source": {"manual": n},
        "history": [{"version": "1.0.0", "date": "2026-02-01", "added": n, "source": "manual"}],
    }
    (dataset_dir / "metadata.json").write_text(json.dumps(meta, indent=2))


class TestImport:
    """Test 1: Import 10 annotations into a dataset with 20 existing."""

    def test_import_grows_dataset(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_dataset(dataset_dir, n=20)

        completed_dir = tmp_path / "completed"
        annotations = [
            _make_annotation(f"t-{i}", f"New query {i}", f"Correct answer {i}")
            for i in range(10)
        ]
        _write_annotations(completed_dir, annotations)

        mgr = GoldenDatasetManager(dataset_dir=dataset_dir)
        result = mgr.import_annotations(source_dir=completed_dir)

        assert result["imported"] == 10
        meta = json.loads((dataset_dir / "metadata.json").read_text())
        assert meta["total_examples"] == 30


class TestDedup:
    """Test 2: Import a near-duplicate — should be flagged."""

    def test_duplicate_detected(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_dataset(dataset_dir, n=5)

        completed_dir = tmp_path / "completed"
        # Create annotation with query that matches an existing one
        annotations = [
            _make_annotation("dup-1", "Seed query number 0", "Some answer"),  # exact match to seed
        ]
        _write_annotations(completed_dir, annotations)

        def mock_embed(texts: list[str]) -> list[list[float]]:
            embeddings = []
            for t in texts:
                if "Seed query number 0" in t:
                    embeddings.append([1.0] * 128)
                else:
                    embeddings.append([0.0] * 128)
            return embeddings

        mgr = GoldenDatasetManager(dataset_dir=dataset_dir, embed_fn=mock_embed, dedup_threshold=0.95)
        result = mgr.import_annotations(source_dir=completed_dir)

        assert result["duplicates"] == 1
        assert result["imported"] == 0


class TestValidation:
    """Test 3: Import invalid example (empty query) — should be rejected."""

    def test_empty_query_rejected(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_dataset(dataset_dir, n=5)

        completed_dir = tmp_path / "completed"
        bad_annotation = _make_annotation("bad-1", "", "Some answer")
        _write_annotations(completed_dir, [bad_annotation])

        mgr = GoldenDatasetManager(dataset_dir=dataset_dir)
        result = mgr.import_annotations(source_dir=completed_dir)

        assert result["invalid"] == 1
        assert result["imported"] == 0


class TestVersioning:
    """Test 4: Assert metadata.json version incremented and history added."""

    def test_version_bump(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_dataset(dataset_dir, n=5)

        completed_dir = tmp_path / "completed"
        annotations = [_make_annotation("v-1", "Version test query", "Answer")]
        _write_annotations(completed_dir, annotations)

        mgr = GoldenDatasetManager(dataset_dir=dataset_dir)
        mgr.import_annotations(source_dir=completed_dir)

        meta = json.loads((dataset_dir / "metadata.json").read_text())
        assert meta["version"] == "1.1.0"
        assert len(meta["history"]) == 2
        assert meta["history"][-1]["added"] == 1
        assert meta["history"][-1]["source"] == "annotated_failures"


class TestExportFormats:
    """Test 5: Assert both JSONL files are updated."""

    def test_both_jsonl_updated(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "metadata.json").write_text(json.dumps({
            "version": "1.0.0", "last_updated": "2026-02-01",
            "total_examples": 0, "by_source": {}, "history": [],
        }))

        completed_dir = tmp_path / "completed"
        annotations = [
            _make_annotation("fmt-1", "Format test query", "Correct answer"),
        ]
        _write_annotations(completed_dir, annotations)

        mgr = GoldenDatasetManager(dataset_dir=dataset_dir)
        mgr.import_annotations(source_dir=completed_dir)

        # Promptfoo
        pf = dataset_dir / "promptfoo_tests.jsonl"
        assert pf.exists()
        pf_entry = json.loads(pf.read_text().strip().split("\n")[0])
        assert "vars" in pf_entry
        assert pf_entry["vars"]["query"] == "Format test query"

        # DeepEval
        de = dataset_dir / "faithfulness_tests.jsonl"
        assert de.exists()
        de_entry = json.loads(de.read_text().strip().split("\n")[0])
        assert de_entry["expected_answer"] == "Correct answer"
        assert de_entry["source"] == "annotated_failures"


class TestCoverage:
    """Test 6: Assert coverage report shows counts per failure category."""

    def test_coverage_by_category(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        lines = [
            json.dumps({"category": "hallucination", "query": "q1", "expected_answer": "a1"}),
            json.dumps({"category": "hallucination", "query": "q2", "expected_answer": "a2"}),
            json.dumps({"category": "retrieval_failure", "query": "q3", "expected_answer": "a3"}),
        ]
        (dataset_dir / "faithfulness_tests.jsonl").write_text("\n".join(lines) + "\n")

        mgr = GoldenDatasetManager(dataset_dir=dataset_dir)
        coverage = mgr.get_coverage()

        assert coverage["hallucination"] == 2
        assert coverage["retrieval_failure"] == 1
        assert coverage["context_gap"] == 0
        assert coverage["wrong_route"] == 0
