#!/usr/bin/env python3
"""CLI for golden dataset expansion.

Usage:
    python scripts/expand_golden_dataset.py import --source annotations/completed/
    python scripts/expand_golden_dataset.py stats
    python scripts/expand_golden_dataset.py coverage
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.flywheel.dataset_manager import GoldenDatasetManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden dataset expansion CLI")
    subparsers = parser.add_subparsers(dest="command")

    import_p = subparsers.add_parser("import", help="Import annotations")
    import_p.add_argument("--source", required=True, help="Annotations completed dir")
    import_p.add_argument("--dataset-dir", default="golden_dataset", help="Dataset dir")

    stats_p = subparsers.add_parser("stats", help="Show dataset stats")
    stats_p.add_argument("--dataset-dir", default="golden_dataset", help="Dataset dir")

    cov_p = subparsers.add_parser("coverage", help="Show coverage by failure category")
    cov_p.add_argument("--dataset-dir", default="golden_dataset", help="Dataset dir")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    mgr = GoldenDatasetManager(dataset_dir=Path(args.dataset_dir))

    if args.command == "import":
        result = mgr.import_annotations(source_dir=Path(args.source))
        print(f"Imported: {result['imported']}")
        print(f"Duplicates: {result['duplicates']}")
        print(f"Invalid: {result['invalid']}")

    elif args.command == "stats":
        stats = mgr.get_stats()
        print(json.dumps(stats, indent=2))

    elif args.command == "coverage":
        coverage = mgr.get_coverage()
        for cat, count in sorted(coverage.items()):
            status = "covered" if count > 0 else "GAP"
            print(f"  {cat}: {count} ({status})")


if __name__ == "__main__":
    main()
