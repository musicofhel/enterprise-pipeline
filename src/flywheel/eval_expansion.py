"""Eval suite expansion — auto-generate eval tests from annotated failures.

Reads the golden dataset, identifies coverage gaps by failure category,
and generates new eval test cases from annotated examples.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from src.flywheel.dataset_manager import FAILURE_CATEGORIES

logger = structlog.get_logger()


class EvalSuiteExpander:
    """Expand the eval suite to cover all failure categories."""

    def __init__(self, dataset_dir: Path = Path("golden_dataset")) -> None:
        self._dataset_dir = dataset_dir

    def _count_eval_tests(self) -> dict[str, int]:
        """Count existing eval tests per failure category."""
        counts: dict[str, int] = {cat: 0 for cat in FAILURE_CATEGORIES}

        de_path = self._dataset_dir / "faithfulness_tests.jsonl"
        if not de_path.exists():
            return counts

        for line in de_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                cat = entry.get("category", "other")
                if cat in counts:
                    counts[cat] += 1
            except json.JSONDecodeError:
                continue

        return counts

    def _count_golden_examples(self) -> dict[str, int]:
        """Count golden dataset examples per failure category."""
        counts: dict[str, int] = {cat: 0 for cat in FAILURE_CATEGORIES}

        de_path = self._dataset_dir / "faithfulness_tests.jsonl"
        if not de_path.exists():
            return counts

        for line in de_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                cat = entry.get("category", "other")
                if cat in counts:
                    counts[cat] += 1
            except json.JSONDecodeError:
                continue

        return counts

    def get_coverage_report(self) -> dict[str, Any]:
        """Generate coverage report showing gaps."""
        golden = self._count_golden_examples()
        eval_tests = self._count_eval_tests()

        categories: dict[str, dict[str, Any]] = {}
        gaps: list[str] = []

        for cat in FAILURE_CATEGORIES:
            g_count = golden.get(cat, 0)
            e_count = eval_tests.get(cat, 0)
            status = "covered" if e_count > 0 else "GAP"
            categories[cat] = {
                "golden_examples": g_count,
                "eval_tests": e_count,
                "coverage": status,
            }
            if status == "GAP":
                gaps.append(cat)

        return {
            "failure_categories": categories,
            "total_golden": sum(golden.values()),
            "total_eval_tests": sum(eval_tests.values()),
            "gaps": gaps,
        }

    def expand_from_annotations(
        self,
        annotations_dir: Path,
    ) -> dict[str, Any]:
        """Generate eval tests from completed annotations for gap categories.

        Returns summary of generated tests.
        """
        self._dataset_dir.mkdir(parents=True, exist_ok=True)

        existing_counts = self._count_eval_tests()
        generated = 0
        new_promptfoo: list[str] = []
        new_deepeval: list[str] = []

        if not annotations_dir.exists():
            return {"generated": 0, "categories_filled": []}

        categories_filled: list[str] = []

        for path in sorted(annotations_dir.glob("*.json")):
            try:
                annotation = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            anno_data = annotation.get("annotation", {})
            correct_answer = anno_data.get("correct_answer")
            if not correct_answer:
                continue

            category = anno_data.get("failure_type", annotation.get("category", "other"))
            query = annotation.get("query", "")
            if not query:
                continue

            # Generate Promptfoo test
            promptfoo_entry = {
                "vars": {
                    "query": query,
                    "context": "\n\n".join(annotation.get("context", [])) if annotation.get("context") else annotation.get("answer_given", ""),
                },
                "assert": [{"type": "python", "value": "file://scripts/eval_assertions.py"}],
            }
            new_promptfoo.append(json.dumps(promptfoo_entry, default=str))

            # Generate DeepEval test
            deepeval_entry = {
                "id": f"eval-{annotation.get('trace_id', '')}",
                "category": category,
                "query": query,
                "context": annotation.get("context", []),
                "expected_answer": correct_answer,
                "expected_faithfulness": 0.85,
                "source": "eval_expansion",
            }
            new_deepeval.append(json.dumps(deepeval_entry, default=str))

            if category not in categories_filled and existing_counts.get(category, 0) == 0:
                categories_filled.append(category)

            generated += 1

        # Append to dataset files
        if new_promptfoo:
            pf_path = self._dataset_dir / "promptfoo_tests.jsonl"
            with open(pf_path, "a") as f:
                f.write("\n".join(new_promptfoo) + "\n")

        if new_deepeval:
            de_path = self._dataset_dir / "faithfulness_tests.jsonl"
            with open(de_path, "a") as f:
                f.write("\n".join(new_deepeval) + "\n")

        logger.info("eval_expansion_complete", generated=generated, categories_filled=categories_filled)

        return {
            "generated": generated,
            "categories_filled": categories_filled,
        }
