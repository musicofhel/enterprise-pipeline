"""Golden dataset expansion and versioning.

Imports annotated production failures, deduplicates by embedding similarity,
validates entries, appends to the golden dataset, and maintains version metadata.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()

FAILURE_CATEGORIES = [
    "retrieval_failure",
    "hallucination",
    "wrong_route",
    "context_gap",
    "compression_loss",
    "other",
]


class GoldenDatasetManager:
    """Manage golden evaluation dataset with versioning and dedup."""

    def __init__(
        self,
        dataset_dir: Path = Path("golden_dataset"),
        embed_fn: Any | None = None,
        dedup_threshold: float = 0.95,
    ) -> None:
        self._dataset_dir = dataset_dir
        self._embed_fn = embed_fn
        self._dedup_threshold = dedup_threshold

    def _read_metadata(self) -> dict[str, Any]:
        """Read or initialize metadata.json."""
        meta_path = self._dataset_dir / "metadata.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text())  # type: ignore[no-any-return]
        return {
            "version": "1.0.0",
            "last_updated": datetime.now(UTC).strftime("%Y-%m-%d"),
            "total_examples": 0,
            "by_source": {},
            "history": [],
        }

    def _write_metadata(self, meta: dict[str, Any]) -> None:
        self._dataset_dir.mkdir(parents=True, exist_ok=True)
        meta_path = self._dataset_dir / "metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2, default=str))

    def _bump_version(self, meta: dict[str, Any]) -> str:
        """Increment minor version."""
        parts = meta["version"].split(".")
        parts[1] = str(int(parts[1]) + 1)
        parts[2] = "0"
        return ".".join(parts)

    def _load_existing_queries(self) -> list[str]:
        """Load all queries from existing dataset files."""
        queries: list[str] = []
        for jsonl_name in ["faithfulness_tests.jsonl", "promptfoo_tests.jsonl"]:
            path = self._dataset_dir / jsonl_name
            if not path.exists():
                continue
            for line in path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    q = entry.get("query") or entry.get("vars", {}).get("query", "")
                    if q:
                        queries.append(q)
                except json.JSONDecodeError:
                    continue
        return queries

    def _is_duplicate(self, query: str, existing_queries: list[str]) -> bool:
        """Check if query is a near-duplicate of any existing query."""
        if not self._embed_fn or not existing_queries:
            return False

        try:
            all_texts = [*existing_queries, query]
            embeddings = np.array(self._embed_fn(all_texts))

            new_emb = embeddings[-1]
            existing_embs = embeddings[:-1]

            # Normalize
            new_norm = new_emb / (np.linalg.norm(new_emb) or 1.0)
            norms = np.linalg.norm(existing_embs, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            existing_normed = existing_embs / norms

            similarities = existing_normed @ new_norm
            max_sim = float(np.max(similarities))

            if max_sim >= self._dedup_threshold:
                logger.info("duplicate_detected", query=query[:80], max_similarity=max_sim)
                return True

        except Exception:
            logger.warning("dedup_check_failed", query=query[:80])

        return False

    def validate_example(self, example: dict[str, Any]) -> tuple[bool, str]:
        """Validate an annotation example. Returns (valid, reason)."""
        if not example.get("query"):
            return False, "empty query"
        if not example.get("expected_answer") and not example.get("annotation", {}).get("correct_answer"):
            return False, "empty expected answer"
        failure_type = (
            example.get("category")
            or example.get("annotation", {}).get("failure_type")
        )
        if failure_type and failure_type not in FAILURE_CATEGORIES:
            return False, f"invalid failure category: {failure_type}"
        return True, "ok"

    def import_annotations(
        self,
        source_dir: Path,
        source_label: str = "annotated_failures",
    ) -> dict[str, Any]:
        """Import completed annotations into the golden dataset.

        Returns a summary dict with counts of imported, duplicates, invalid.
        """
        self._dataset_dir.mkdir(parents=True, exist_ok=True)
        existing_queries = self._load_existing_queries()

        imported = 0
        duplicates = 0
        invalid = 0
        new_promptfoo: list[str] = []
        new_deepeval: list[str] = []

        if not source_dir.exists():
            return {"imported": 0, "duplicates": 0, "invalid": 0}

        for path in sorted(source_dir.glob("*.json")):
            try:
                annotation = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                invalid += 1
                continue

            anno_data = annotation.get("annotation", {})
            correct_answer = anno_data.get("correct_answer")
            if not correct_answer:
                invalid += 1
                continue

            query = annotation.get("query", "")
            valid, reason = self.validate_example({"query": query, "expected_answer": correct_answer, "category": annotation.get("category")})
            if not valid:
                logger.warning("invalid_annotation", trace_id=annotation.get("trace_id"), reason=reason)
                invalid += 1
                continue

            # Dedup check
            if self._is_duplicate(query, existing_queries):
                duplicates += 1
                continue

            # Build dataset entries
            category = anno_data.get("failure_type", annotation.get("category", "other"))

            promptfoo_entry = {
                "vars": {
                    "query": query,
                    "context": "\n\n".join(annotation.get("context", [])) if annotation.get("context") else annotation.get("answer_given", ""),
                },
                "assert": [{"type": "python", "value": "file://scripts/eval_assertions.py"}],
            }
            new_promptfoo.append(json.dumps(promptfoo_entry, default=str))

            deepeval_entry = {
                "id": f"annotated-{annotation.get('trace_id', '')}",
                "category": category,
                "query": query,
                "context": annotation.get("context", []),
                "expected_answer": correct_answer,
                "expected_faithfulness": 0.85,
                "source": source_label,
            }
            new_deepeval.append(json.dumps(deepeval_entry, default=str))

            existing_queries.append(query)
            imported += 1

        # Append to files
        if new_promptfoo:
            pf_path = self._dataset_dir / "promptfoo_tests.jsonl"
            with open(pf_path, "a") as f:
                f.write("\n".join(new_promptfoo) + "\n")

        if new_deepeval:
            de_path = self._dataset_dir / "faithfulness_tests.jsonl"
            with open(de_path, "a") as f:
                f.write("\n".join(new_deepeval) + "\n")

        # Update metadata
        if imported > 0:
            meta = self._read_metadata()
            new_version = self._bump_version(meta)
            meta["version"] = new_version
            meta["last_updated"] = datetime.now(UTC).strftime("%Y-%m-%d")
            meta["total_examples"] = meta.get("total_examples", 0) + imported
            meta["by_source"][source_label] = meta["by_source"].get(source_label, 0) + imported
            meta["history"].append({
                "version": new_version,
                "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                "added": imported,
                "source": source_label,
            })
            self._write_metadata(meta)

        logger.info(
            "dataset_import_complete",
            imported=imported,
            duplicates=duplicates,
            invalid=invalid,
        )

        return {"imported": imported, "duplicates": duplicates, "invalid": invalid}

    def get_stats(self) -> dict[str, Any]:
        """Return dataset stats."""
        meta = self._read_metadata()
        return {
            "version": meta["version"],
            "total_examples": meta["total_examples"],
            "by_source": meta["by_source"],
            "history_entries": len(meta["history"]),
        }

    def get_coverage(self) -> dict[str, int]:
        """Count examples per failure category."""
        coverage: dict[str, int] = {cat: 0 for cat in FAILURE_CATEGORIES}

        de_path = self._dataset_dir / "faithfulness_tests.jsonl"
        if de_path.exists():
            for line in de_path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    cat = entry.get("category", "other")
                    if cat in coverage:
                        coverage[cat] += 1
                except json.JSONDecodeError:
                    continue

        return coverage
