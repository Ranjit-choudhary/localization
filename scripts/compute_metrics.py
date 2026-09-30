"""
Compute all 7 reference-based evaluation metrics for LLM benchmarking.

Adapted verbatim from the NMT benchmark repo (scripts/compute_metrics.py) so
LLM scores are directly comparable with the NMT systems: the metric functions,
tokenisation, scaling and Google Translate reference are unchanged. Only the
SYSTEMS list differs.

Metrics: BLEU, METEOR, chrF++, ROUGE-L, TER, COMET, BERTScore
Reference: Google Translate baseline output (data/baseline_google_translate)

Usage:
    python scripts/compute_metrics.py --system qwen25_coder_7b --lang de
    python scripts/compute_metrics.py --all --metrics lexical
"""

import argparse
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path

# Metric imports
import sacrebleu
from sacrebleu.metrics import BLEU, CHRF, TER
import nltk
from rouge_score import rouge_scorer
# NOTE: torch, comet and bert_score are imported lazily inside their functions
# so a lexical-only run does not require the GPU/neural dependencies.

# Configuration
LANGUAGES = {
    'high_resource': ['de', 'fr', 'zh', 'es', 'ja'],
    'low_resource': ['hi', 'ar', 'bn', 'mr', 'pa', 'ta', 'te'],
}
ALL_LANGS = LANGUAGES['high_resource'] + LANGUAGES['low_resource']

# LLM systems (data/<system>/<lang>.txt). *_clean = first-line/quote-stripped
# post-processing ablation of the same run (see prepare_llm_outputs.py).
# Add further LLMs (e.g. llama32_3b, translategemma_4b) here.
SYSTEMS = ['qwen25_coder_7b', 'qwen25_coder_7b_clean']
INDIC_ONLY_SYSTEMS = []
INDIC_LANGS = ['hi', 'bn', 'mr', 'pa', 'ta', 'te']

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
RESULTS_DIR = BASE_DIR / 'metrics' / 'results'


def load_translations(system: str, lang: str) -> list:
    """Load translated strings for a system-language pair."""
    filepath = DATA_DIR / system / f'{lang}.txt'
    if not filepath.exists():
        raise FileNotFoundError(f"Translation file not found: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines()]


def load_references(lang: str) -> list:
    """Load Google Translate baseline translations (references)."""
    filepath = DATA_DIR / 'baseline_google_translate' / f'{lang}.txt'
    if not filepath.exists():
        raise FileNotFoundError(f"Reference file not found: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines()]


def load_sources() -> list:
    """Load English source strings."""
    filepath = DATA_DIR / 'source' / 'en.txt'
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines()]


def compute_bleu(hypotheses: list, references: list, lang: str = None) -> float:
    """Compute BLEU score using SacreBLEU with language-aware tokenization.

    Chinese and Japanese are not space-segmented, so the default '13a'
    tokenizer under-counts n-gram overlap. Use SacreBLEU's dedicated
    tokenizers for those languages for comparable scores.
    """
    tok = {'zh': 'zh', 'ja': 'ja-mecab'}.get(lang)
    bleu = BLEU(tokenize=tok) if tok else BLEU()
    result = bleu.corpus_score(hypotheses, [references])
    return result.score


def compute_chrf(hypotheses: list, references: list) -> float:
    """Compute chrF++ score using SacreBLEU."""
    chrf = CHRF(word_order=2)  # chrF++ includes word n-grams
    result = chrf.corpus_score(hypotheses, [references])
    return result.score


def compute_ter(hypotheses: list, references: list) -> float:
    """Compute TER score using SacreBLEU."""
    ter = TER()
    result = ter.corpus_score(hypotheses, [references])
    return result.score


def compute_meteor(hypotheses: list, references: list) -> float:
    """Compute METEOR score using NLTK."""
    nltk.download('wordnet', quiet=True)
    nltk.download('punkt', quiet=True)
    scores = []
    for hyp, ref in zip(hypotheses, references):
        score = nltk.translate.meteor_score.single_meteor_score(
            ref.split(), hyp.split()
        )
        scores.append(score)
    return np.mean(scores) * 100  # Scale to 0-100


def compute_rouge_l(hypotheses: list, references: list) -> float:
    """Compute ROUGE-L F1 score."""
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    scores = []
    for hyp, ref in zip(hypotheses, references):
        result = scorer.score(ref, hyp)
        scores.append(result['rougeL'].fmeasure)
    return np.mean(scores) * 100  # Scale to 0-100


def compute_comet(sources: list, hypotheses: list, references: list) -> float:
    """Compute COMET score (reference-based)."""
    import torch
    from comet import download_model, load_from_checkpoint
    model_path = download_model("Unbabel/wmt22-comet-da")
    model = load_from_checkpoint(model_path)
    data = [
        {"src": src, "mt": hyp, "ref": ref}
        for src, hyp, ref in zip(sources, hypotheses, references)
    ]
    n_gpu = 1 if torch.cuda.is_available() else 0
    output = model.predict(data, batch_size=32, gpus=n_gpu)
    return output.system_score


def compute_bertscore(hypotheses: list, references: list, lang: str) -> float:
    """Compute BERTScore F1."""
    from bert_score import score as bert_score
    P, R, F1 = bert_score(hypotheses, references, lang=lang, verbose=False)
    return F1.mean().item()


def compute_all_metrics(system: str, lang: str, mode: str = "all"):
    """Compute reference-based metrics for a system-language pair.

    mode: "lexical" (BLEU, METEOR, chrF++, ROUGE-L, TER; CPU-friendly),
          "neural"  (COMET, BERTScore; GPU-recommended),
          "all"     (both).
    """
    print(f"\n{'='*60}")
    print(f"Computing metrics: {system} / en->{lang}")
    print(f"{'='*60}")

    # Check if this system supports this language
    if system in INDIC_ONLY_SYSTEMS and lang not in INDIC_LANGS:
        print(f"  Skipping: {system} does not support {lang}")
        return None

    sources = load_sources()
    hypotheses = load_translations(system, lang)
    references = load_references(lang)

    # Ensure equal lengths
    min_len = min(len(sources), len(hypotheses), len(references))
    sources = sources[:min_len]
    hypotheses = hypotheses[:min_len]
    references = references[:min_len]

    print(f"  Strings: {min_len}")

    results = {'system': system, 'lang': lang, 'n_strings': min_len}

    if mode in ("lexical", "all"):
        print("  Computing BLEU...")
        results['bleu'] = compute_bleu(hypotheses, references, lang)
        print("  Computing METEOR...")
        results['meteor'] = compute_meteor(hypotheses, references)
        print("  Computing chrF++...")
        results['chrf'] = compute_chrf(hypotheses, references)
        print("  Computing ROUGE-L...")
        results['rouge_l'] = compute_rouge_l(hypotheses, references)
        print("  Computing TER...")
        results['ter'] = compute_ter(hypotheses, references)

    if mode in ("neural", "all"):
        print("  Computing COMET...")
        results['comet'] = compute_comet(sources, hypotheses, references)
        print("  Computing BERTScore...")
        results['bertscore'] = compute_bertscore(hypotheses, references, lang)

    print(f"\n  Done: {system}/{lang} (mode={mode})")
    return results


def main():
    parser = argparse.ArgumentParser(description='Compute NMT evaluation metrics')
    parser.add_argument('--system', type=str, help='NMT system name')
    parser.add_argument('--lang', type=str, default='all', help='Target language code or "all"')
    parser.add_argument('--all', action='store_true', help='Run all systems and languages')
    parser.add_argument('--metrics', choices=['lexical','neural','all'], default='all',
                        help='Which metric group to compute (lexical=CPU, neural=GPU)')
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []

    if args.all:
        for system in SYSTEMS:
            for lang in ALL_LANGS:
                try:
                    result = compute_all_metrics(system, lang, args.metrics)
                    if result:
                        all_results.append(result)
                except FileNotFoundError as e:
                    print(f"  Skipping {system}/{lang}: {e}")
    else:
        langs = ALL_LANGS if args.lang == 'all' else [args.lang]
        for lang in langs:
            try:
                result = compute_all_metrics(args.system, lang, args.metrics)
                if result:
                    all_results.append(result)
            except FileNotFoundError as e:
                print(f"  Skipping {args.system}/{lang}: {e}")

    # Save results
    if all_results:
        df = pd.DataFrame(all_results)
        suffix = '' if args.metrics == 'all' else f'_{args.metrics}'
        output_path = RESULTS_DIR / f'metric_scores{suffix}.csv'
        df.to_csv(output_path, index=False)
        print(f"\n{'='*60}")
        print(f"Results saved to: {output_path}")
        print(f"Total evaluations: {len(all_results)}")
        print(df.to_string(index=False))


if __name__ == '__main__':
    main()
