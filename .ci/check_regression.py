"""Checks for model performance regression against a target Brier score."""

import json
import sys
from pathlib import Path


def check_regression(results_path: Path, target_path: Path):
    """
    Check for model performance regression.

    Compares the Brier score from a validation run against a target value.
    Exits with a non-zero status code if performance has regressed.
    """
    if not results_path.exists():
        print(f"Error: Results file not found at {results_path}", file=sys.stderr)
        sys.exit(1)

    if not target_path.exists():
        print(f"Error: Target file not found at {target_path}", file=sys.stderr)
        sys.exit(1)

    with open(results_path) as f:
        try:
            results = json.load(f)
        except json.JSONDecodeError:
            print(
                f"Error: Invalid JSON in results file {results_path}", file=sys.stderr
            )
            sys.exit(1)

    with open(target_path) as f:
        target = json.load(f)

    if not results:
        print("Error: Results file is empty.", file=sys.stderr)
        sys.exit(1)

    # Get Brier score from the first (and only) fold
    hier_brier = results[0].get("hier_brier")
    if hier_brier is None:
        print("Error: 'hier_brier' not found in results.", file=sys.stderr)
        sys.exit(1)

    target_brier = target.get("brier_score_target")
    if target_brier is None:
        print("Error: 'brier_score_target' not found in target file.", file=sys.stderr)
        sys.exit(1)

    print("🎯 Checking Brier score against target...")
    print(f"  - Actual:   {hier_brier:.4f}")
    print(f"  - Target:   {target_brier:.4f}")

    if hier_brier > target_brier:
        print(
            f"\n❌ REGRESSION DETECTED: Brier score {hier_brier:.4f} is worse than target {target_brier:.4f}."
        )
        sys.exit(1)
    else:
        print(
            f"\n✅ PASSED: Brier score {hier_brier:.4f} is not worse than target {target_brier:.4f}."
        )
        sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python check_regression.py <path_to_results.json> <path_to_target.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    results_path = Path(sys.argv[1])
    target_path = Path(sys.argv[2])
    check_regression(results_path, target_path)
