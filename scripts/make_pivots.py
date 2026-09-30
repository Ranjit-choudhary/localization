"""
Generate one pivot table (system x language) per metric from the merged
metric_scores.csv, so each metric is available as a standalone CSV for
analysis and for pasting into paper tables.

These are DERIVED views: metric_scores.csv remains the source of truth.
Re-runnable anytime; safe to regenerate.

Usage:
    python scripts/make_pivots.py
"""
import pandas as pd
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "metrics" / "results"
MERGED = RESULTS_DIR / "metric_scores.csv"
PIVOT_DIR = RESULTS_DIR / "pivots"

# All metric columns that may be present (lexical + neural). CometKiwi lives in
# its own file (metrics/cometkiwi/) and is handled by that script's pivot.
METRICS = ["bleu", "meteor", "chrf", "rouge_l", "ter", "comet", "bertscore"]

# Language column order for readable tables
LANG_ORDER = ["de", "fr", "zh", "es", "ja", "hi", "ar", "bn", "mr", "pa", "ta", "te"]


def main():
    if not MERGED.exists():
        raise SystemExit(f"Merged results not found: {MERGED}. Run merge_metric_results.py first.")

    df = pd.read_csv(MERGED)
    PIVOT_DIR.mkdir(parents=True, exist_ok=True)

    made = []
    for metric in METRICS:
        if metric not in df.columns:
            continue  # metric group not computed yet
        pivot = df.pivot(index="system", columns="lang", values=metric)
        # order columns by LANG_ORDER where present
        cols = [c for c in LANG_ORDER if c in pivot.columns]
        pivot = pivot[cols]
        out = PIVOT_DIR / f"pivot_{metric}.csv"
        pivot.to_csv(out)
        made.append(out.name)
        print(f"[done] {out.name}")

    if not made:
        print("No metric columns found in merged CSV; nothing to pivot.")
    else:
        print(f"\nWrote {len(made)} per-metric pivot tables to {PIVOT_DIR}/")


if __name__ == "__main__":
    main()
