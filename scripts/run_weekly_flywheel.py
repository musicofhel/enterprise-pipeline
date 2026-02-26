#!/usr/bin/env python3
"""Weekly flywheel automation — one command to run the full cycle.

Usage:
    # Phase 1: Triage + generate annotation tasks
    python scripts/run_weekly_flywheel.py --week 2026-W09

    # Phase 2: After annotation, import + expand + report
    python scripts/run_weekly_flywheel.py --week 2026-W09 --continue
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.flywheel.annotation import AnnotationService
from src.flywheel.dataset_manager import GoldenDatasetManager
from src.flywheel.eval_expansion import EvalSuiteExpander
from src.flywheel.failure_triage import FailureTriageService


def phase_1(
    week: str,
    traces_dir: Path,
    annotations_dir: Path,
    reports_dir: Path,
    days: int,
) -> None:
    """Phase 1: Triage + generate annotation tasks."""
    print(f"=== Weekly Flywheel — {week} (Phase 1: Triage) ===\n")

    # Step 1: Failure triage
    print("Step 1: Scanning traces for failures...")
    triage = FailureTriageService(traces_dir=traces_dir)
    report = triage.triage(days=days)

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"triage-{week}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))

    print(f"  Total responses: {report['total_responses']}")
    print(f"  Total failures:  {report['total_failures']}")
    print(f"  Failure rate:    {report['failure_rate']:.1%}")
    if report["by_category"]:
        print("  By category:")
        for cat, info in sorted(report["by_category"].items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"    {cat}: {info['count']}")

    # Step 2: Generate annotation tasks
    print("\nStep 2: Generating annotation tasks...")
    annotator = AnnotationService(annotations_dir=annotations_dir)
    count = annotator.generate_tasks(report)
    pending = annotator.get_pending_count()

    print(f"  New tasks: {count}")
    print(f"  Total pending: {pending}")

    print("\n--- Phase 1 Complete ---")
    print(f"Triage report: {report_path}")
    print("\nNext: Annotate pending tasks with:")
    print(f"  python scripts/annotate.py --annotations-dir {annotations_dir} next")
    print(f"  python scripts/annotate.py --annotations-dir {annotations_dir} submit --trace-id ID ...")
    print("\nThen re-run with --continue:")
    print(f"  python scripts/run_weekly_flywheel.py --week {week} --continue")


def phase_2(
    week: str,
    annotations_dir: Path,
    dataset_dir: Path,
) -> None:
    """Phase 2: Import annotations + expand eval suite + report."""
    print(f"=== Weekly Flywheel — {week} (Phase 2: Import & Expand) ===\n")

    completed_dir = annotations_dir / "completed"

    # Step 5: Import annotations into golden dataset
    print("Step 5: Importing annotations into golden dataset...")
    mgr = GoldenDatasetManager(dataset_dir=dataset_dir)

    before_meta = mgr._read_metadata()
    before_count = before_meta.get("total_examples", 0)

    result = mgr.import_annotations(source_dir=completed_dir)
    print(f"  Imported:   {result['imported']}")
    print(f"  Duplicates: {result['duplicates']}")
    print(f"  Invalid:    {result['invalid']}")

    after_meta = mgr._read_metadata()
    after_count = after_meta.get("total_examples", 0)
    print(f"  Dataset: {before_count} → {after_count} examples (v{after_meta.get('version', '?')})")

    # Step 6: Expand eval suite
    print("\nStep 6: Expanding eval suite...")
    expander = EvalSuiteExpander(dataset_dir=dataset_dir)
    expansion = expander.expand_from_annotations(completed_dir)
    print(f"  Tests generated: {expansion['generated']}")
    if expansion["categories_filled"]:
        print(f"  New categories covered: {', '.join(expansion['categories_filled'])}")

    # Step 7: Coverage report
    print("\nStep 7: Coverage report...")
    coverage = expander.get_coverage_report()
    for cat, info in sorted(coverage["failure_categories"].items()):
        status = info["coverage"]
        marker = "  " if status == "covered" else "!!"
        print(f"  {marker} {cat}: {info['eval_tests']} tests ({status})")

    if coverage["gaps"]:
        print(f"\n  Gaps remaining: {', '.join(coverage['gaps'])}")
    else:
        print("\n  All failure categories covered!")

    print("\n--- Phase 2 Complete ---")
    print(f"Dataset version: {after_meta.get('version', '?')}")
    print(f"Total examples: {after_count}")
    print(f"Total eval tests: {coverage['total_eval_tests']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly flywheel automation")
    parser.add_argument("--week", required=True, help="Week identifier (e.g., 2026-W09)")
    parser.add_argument("--continue", dest="continue_phase", action="store_true", help="Run phase 2 (import + expand)")
    parser.add_argument("--traces-dir", default="traces/local", help="Traces directory")
    parser.add_argument("--annotations-dir", default="annotations", help="Annotations directory")
    parser.add_argument("--reports-dir", default="reports/triage", help="Reports directory")
    parser.add_argument("--dataset-dir", default="golden_dataset", help="Golden dataset directory")
    parser.add_argument("--days", type=int, default=7, help="Lookback days for triage")
    args = parser.parse_args()

    if args.continue_phase:
        phase_2(
            week=args.week,
            annotations_dir=Path(args.annotations_dir),
            dataset_dir=Path(args.dataset_dir),
        )
    else:
        phase_1(
            week=args.week,
            traces_dir=Path(args.traces_dir),
            annotations_dir=Path(args.annotations_dir),
            reports_dir=Path(args.reports_dir),
            days=args.days,
        )


if __name__ == "__main__":
    main()
