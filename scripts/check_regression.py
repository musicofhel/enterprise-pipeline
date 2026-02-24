#!/usr/bin/env python3
"""Check eval results for regressions.

Usage:
    python scripts/check_regression.py --max-regression-pct 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(max_regression_pct: float) -> None:
    results_dir = Path("eval_results")

    if not results_dir.exists():
        print("No eval_results/ directory found — skipping regression check")
        sys.exit(0)

    result_files = list(results_dir.glob("*.json"))
    if not result_files:
        print("No result files found — skipping regression check")
        sys.exit(0)

    regressions_found = False

    for result_file in result_files:
        with open(result_file) as f:
            data = json.load(f)

        if "baseline" not in data or "current" not in data:
            continue

        baseline = data["baseline"]
        current = data["current"]

        for metric, baseline_value in baseline.items():
            current_value = current.get(metric, baseline_value)
            if baseline_value > 0:
                regression_pct = ((baseline_value - current_value) / baseline_value) * 100
                if regression_pct > max_regression_pct:
                    print(
                        f"REGRESSION: {metric} dropped {regression_pct:.1f}% "
                        f"({baseline_value:.3f} -> {current_value:.3f})"
                    )
                    regressions_found = True

    if regressions_found:
        print(f"\nFailed: regressions exceed {max_regression_pct}% threshold")
        sys.exit(1)
    else:
        print("No regressions detected")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for eval regressions")
    parser.add_argument(
        "--max-regression-pct",
        type=float,
        default=2.0,
        help="Maximum acceptable regression percentage",
    )
    args = parser.parse_args()
    main(args.max_regression_pct)
