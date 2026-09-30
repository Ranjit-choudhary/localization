"""
Merge the lexical and neural metric result files into a single metric_scores.csv.

The metrics run is split for practical reasons:
    - lexical metrics (BLEU, METEOR, chrF++, ROUGE-L, TER) are CPU-friendly and
      may be computed first  -> metrics/results/metric_scores_lexical.csv
    - neural metrics (COMET, BERTScore) need a GPU and may be computed later
      -> metrics/results/metric_scores_neural.csv

This joins them by (system, lang) so every metric is computed exactly once and
nothing is overwritten. If only one file exists, it is copied through.

Usage:
    python scripts/merge_metric_results.py
"""
import os
import pandas as pd
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "metrics" / "results"
LEX = RESULTS_DIR / "metric_scores_lexical.csv"
NEU = RESULTS_DIR / "metric_scores_neural.csv"
OUT = RESULTS_DIR / "metric_scores.csv"

KEYS = ["system", "lang"]


def main():
    have_lex = LEX.exists()
    have_neu = NEU.exists()
    if not (have_lex or have_neu):
        raise SystemExit("No lexical or neural result files found to merge.")

    if have_lex and not have_neu:
        df = pd.read_csv(LEX)
        print("Only lexical results present; copying through.")
    elif have_neu and not have_lex:
        df = pd.read_csv(NEU)
        print("Only neural results present; copying through.")
    else:
        lex = pd.read_csv(LEX)
        neu = pd.read_csv(NEU)
        # drop duplicate n_strings from one side to avoid _x/_y columns
        if "n_strings" in neu.columns and "n_strings" in lex.columns:
            neu = neu.drop(columns=["n_strings"])
        df = lex.merge(neu, on=KEYS, how="outer")
        print(f"Merged {len(lex)} lexical + {len(neu)} neural rows -> {len(df)} rows.")

    df = df.sort_values(KEYS)
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(df)} rows).")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
