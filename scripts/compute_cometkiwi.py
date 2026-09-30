"""
Compute CometKiwi reference-free quality estimation scores.

CometKiwi evaluates translation quality using ONLY source + hypothesis,
without any reference translation. This provides independent validation
of system rankings.

Usage:
    python scripts/compute_cometkiwi.py --all
    python scripts/compute_cometkiwi.py --system qwen25_coder_7b --lang de

Requirements / environment notes:
    - Gated HF model: request access to Unbabel/wmt22-cometkiwi-da and
      authenticate (huggingface_hub.login) before running.
    - On a fresh/recycled runtime, install `setuptools<81` first, otherwise
      the comet -> pytorch_lightning -> torchmetrics import chain fails with
      ModuleNotFoundError: pkg_resources.

Memory / reliability design:
    - The CometKiwi model is loaded ONCE (not per language pair). Reloading
      per pair accumulates RAM and gets the process OS-killed.
    - batch_size=16 keeps the memory footprint manageable on a T4.
    - Results are written INCREMENTALLY after each pair, and completed pairs
      are skipped on re-run, so an interruption never loses finished work.
"""

import argparse
import os
import pandas as pd
from pathlib import Path
import torch
from comet import download_model, load_from_checkpoint

ALL_LANGS = ['de', 'fr', 'zh', 'es', 'ja', 'hi', 'ar', 'bn', 'mr', 'pa', 'ta', 'te']
INDIC_LANGS = ['hi', 'bn', 'mr', 'pa', 'ta', 'te']

# LLM systems only: the Google baseline and NMT systems already have CometKiwi
# scores in the NMT repo (metrics/cometkiwi/cometkiwi_scores.csv), computed with
# the same model and settings, and are merged in by analysis.py.
ALL_SYSTEMS = [
    'qwen25_coder_7b',
    'qwen25_coder_7b_clean',
]
INDIC_ONLY = []

BATCH_SIZE = 16

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
RESULTS_DIR = BASE_DIR / 'metrics' / 'cometkiwi'
SCORES_CSV = RESULTS_DIR / 'cometkiwi_scores.csv'


def load_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return [line.rstrip('\n') for line in f.readlines()]


def load_sources():
    return load_lines(DATA_DIR / 'source' / 'en.txt')


def main():
    parser = argparse.ArgumentParser(description='Compute CometKiwi QE scores')
    parser.add_argument('--system', type=str, help='System name')
    parser.add_argument('--lang', type=str, default='all', help='Language or "all"')
    parser.add_argument('--all', action='store_true', help='All systems and languages')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sources = load_sources()

    systems = ALL_SYSTEMS if args.all else [args.system]
    langs = ALL_LANGS if (args.lang == 'all' or args.all) else [args.lang]

    # Resume support: load any already-computed (system, lang) rows.
    if SCORES_CSV.exists():
        existing = pd.read_csv(SCORES_CSV)
        done = {(r['system'], r['lang']) for _, r in existing.iterrows()}
        results = existing.to_dict('records')
        print(f"Resuming: {len(done)} pairs already computed.")
    else:
        done = set()
        results = []

    # Load the model ONCE (key fix: never reload inside the loop).
    n_gpu = 1 if torch.cuda.is_available() else 0
    print("Loading CometKiwi model (once)...")
    model = load_from_checkpoint(download_model("Unbabel/wmt22-cometkiwi-da"))

    for system in systems:
        display = system.replace('baseline_', '')
        for lang in langs:
            if system in INDIC_ONLY and lang not in INDIC_LANGS:
                continue
            if (display, lang) in done:
                print(f"[skip] {display}/{lang} already done")
                continue
            fp = DATA_DIR / system / f'{lang}.txt'
            if not fp.exists():
                print(f"[skip] {system}/{lang}: file not found")
                continue

            hyp = load_lines(fp)
            n = min(len(sources), len(hyp))
            data = [{"src": sources[i], "mt": hyp[i]} for i in range(n)]

            print(f"Computing CometKiwi: {display} / en->{lang} ({n} strings)...")
            output = model.predict(data, batch_size=args.batch_size, gpus=n_gpu)

            results.append({
                'system': display, 'lang': lang,
                'cometkiwi': output.system_score, 'n_strings': n,
            })
            # Incremental save after EVERY pair (crash-safe).
            pd.DataFrame(results).to_csv(SCORES_CSV, index=False)
            print(f"  CometKiwi = {output.system_score:.4f}  (saved)")

    if results:
        df = pd.DataFrame(results)
        pivot = df.pivot(index='system', columns='lang', values='cometkiwi')
        pivot.to_csv(RESULTS_DIR / 'cometkiwi_pivot.csv')
        print(f"\nSaved: {SCORES_CSV}")
        print("\nSystem rankings by CometKiwi (higher = better):")
        print(df.groupby('system')['cometkiwi'].mean().sort_values(ascending=False))


if __name__ == '__main__':
    main()
