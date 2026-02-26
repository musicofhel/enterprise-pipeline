#!/usr/bin/env python3
"""CLI wrapper for experiment analysis.

Usage:
    python scripts/run_experiment_analysis.py
    python scripts/run_experiment_analysis.py --traces-dir traces/local --min-traces 30
    python scripts/run_experiment_analysis.py --output report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.experimentation.analysis import ExperimentAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run experiment analysis on trace data")
    parser.add_argument(
        "--traces-dir",
        type=str,
        default="traces/local",
        help="Directory containing trace JSON files",
    )
    parser.add_argument(
        "--min-traces",
        type=int,
        default=30,
        help="Minimum traces per variant for statistical testing",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for JSON report (prints to stdout if not set)",
    )
    args = parser.parse_args()

    analyzer = ExperimentAnalyzer(traces_dir=Path(args.traces_dir))
    report = analyzer.analyze(min_traces=args.min_traces)

    report_json = json.dumps(report, indent=2, default=str)

    if args.output:
        Path(args.output).write_text(report_json)
        print(f"Report written to {args.output}")
    else:
        print(report_json)

    # Exit with error if recommendation contains "regression"
    rec = report.get("recommendation", "")
    if "regression" in rec.lower():
        sys.exit(1)


if __name__ == "__main__":
    main()
