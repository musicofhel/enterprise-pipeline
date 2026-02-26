#!/usr/bin/env python3
"""CLI for running weekly failure triage.

Usage:
    python scripts/run_failure_triage.py --days 7 --output reports/triage/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running as script from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.flywheel.failure_triage import FailureTriageService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run failure triage on recent traces")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")
    parser.add_argument("--traces-dir", type=str, default="traces/local", help="Traces directory")
    parser.add_argument("--output", type=str, default="reports/triage", help="Output directory")
    args = parser.parse_args()

    traces_dir = Path(args.traces_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    service = FailureTriageService(traces_dir=traces_dir)
    report = service.triage(days=args.days)

    # Write report
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    output_path = output_dir / f"triage-{timestamp}.json"
    output_path.write_text(json.dumps(report, indent=2, default=str))

    # Print summary
    print(f"Triage Report — {report['period']['start']} to {report['period']['end']}")
    print(f"  Total responses: {report['total_responses']}")
    print(f"  Total failures:  {report['total_failures']}")
    print(f"  Failure rate:    {report['failure_rate']:.1%}")
    print()

    if report["by_category"]:
        print("Failures by category:")
        for cat, info in sorted(report["by_category"].items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  {cat}: {info['count']}")
    else:
        print("No failures found.")

    if report["clusters"]:
        print(f"\n{len(report['clusters'])} failure cluster(s) found.")

    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
