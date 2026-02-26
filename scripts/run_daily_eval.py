"""CLI wrapper for daily Ragas eval.

Usage:
    python scripts/run_daily_eval.py [--sample-size 50] [--output eval_results/daily/]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily Ragas eval on recent traces")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="Number of traces to sample (default: 50)",
    )
    parser.add_argument(
        "--traces-dir",
        default="traces/local",
        help="Directory containing trace JSON files (default: traces/local)",
    )
    parser.add_argument(
        "--output",
        default="eval_results/daily",
        help="Output directory for reports (default: eval_results/daily/)",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=24,
        help="Hours to look back for traces (default: 24)",
    )
    args = parser.parse_args()

    from src.observability.daily_eval import DailyEvalRunner

    runner = DailyEvalRunner(
        traces_dir=Path(args.traces_dir),
        output_dir=Path(args.output),
        sample_size=args.sample_size,
        lookback_hours=args.lookback_hours,
    )

    report = runner.run()
    print(json.dumps(report, indent=2))

    if report.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
