#!/usr/bin/env python3
"""Check eval results for regressions.

Usage:
    python scripts/check_regression.py --max-regression-pct 2
    python scripts/check_regression.py --promptfoo-results eval_results/promptfoo_output.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check_eval_results(max_regression_pct: float) -> bool:
    """Check eval_results/ JSON files for regressions. Returns True if regressions found."""
    results_dir = Path("eval_results")

    if not results_dir.exists():
        print("No eval_results/ directory found — skipping regression check")
        return False

    result_files = [f for f in results_dir.glob("*.json") if f.name != "promptfoo_output.json"]
    if not result_files:
        print("No result files found — skipping regression check")
        return False

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

    return regressions_found


def check_promptfoo_results(
    promptfoo_path: str, max_regression_pct: float
) -> bool:
    """Parse Promptfoo JSON output and compare pass rates across providers.

    Returns True if candidate regresses relative to current by more than threshold.
    """
    path = Path(promptfoo_path)
    if not path.exists():
        print(f"Promptfoo results not found: {promptfoo_path} — skipping")
        return False

    with open(path) as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("No Promptfoo results found — skipping")
        return False

    # Group pass rates by prompt (provider)
    prompt_stats: dict[str, dict[str, int]] = {}

    for result in results:
        prompt_id = result.get("prompt", {}).get("label", "unknown")
        if prompt_id not in prompt_stats:
            prompt_stats[prompt_id] = {"total": 0, "passed": 0}

        prompt_stats[prompt_id]["total"] += 1
        if result.get("success", False):
            prompt_stats[prompt_id]["passed"] += 1

    if len(prompt_stats) < 2:
        print("Need at least 2 prompts to compare — skipping regression check")
        return False

    # Compute pass rates
    pass_rates: dict[str, float] = {}
    for prompt_id, stats in prompt_stats.items():
        rate = stats["passed"] / max(stats["total"], 1)
        pass_rates[prompt_id] = rate
        print(f"  {prompt_id}: {rate:.1%} ({stats['passed']}/{stats['total']})")

    # Find current (first prompt) and candidate (second prompt)
    prompt_ids = list(pass_rates.keys())
    current_rate = pass_rates[prompt_ids[0]]
    candidate_rate = pass_rates[prompt_ids[1]]

    if current_rate > 0:
        regression_pct = ((current_rate - candidate_rate) / current_rate) * 100
    else:
        regression_pct = 0.0

    if regression_pct > max_regression_pct:
        print(
            f"\nPROMPTFOO REGRESSION: candidate pass rate dropped {regression_pct:.1f}% "
            f"({current_rate:.1%} -> {candidate_rate:.1%})"
        )
        return True

    print(f"\nPromptfoo: no regression (delta: {regression_pct:+.1f}%)")
    return False


def main(max_regression_pct: float, promptfoo_results: str | None = None) -> None:
    regressions = check_eval_results(max_regression_pct)

    if promptfoo_results:
        promptfoo_regression = check_promptfoo_results(promptfoo_results, max_regression_pct)
        regressions = regressions or promptfoo_regression

    if regressions:
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
    parser.add_argument(
        "--promptfoo-results",
        type=str,
        default=None,
        help="Path to Promptfoo JSON output file",
    )
    args = parser.parse_args()
    main(args.max_regression_pct, args.promptfoo_results)
