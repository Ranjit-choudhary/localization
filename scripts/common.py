"""Shared configuration and loaders for the LLM-vs-NMT analysis scripts."""
import os
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
METRICS = BASE / "metrics"
FIGURES = BASE / "figures"
TABLES = BASE / "tables"

# The NMT benchmark repository (Track 1). Its outputs and metric scores are
# read, never modified. Override with the NMT_REPO environment variable.
NMT_REPO = Path(os.environ.get("NMT_REPO", BASE.parent / "make it like"))

HIGH = ["de", "fr", "zh", "es", "ja"]
LOW = ["hi", "ar", "bn", "mr", "pa", "ta", "te"]
LANGS = HIGH + LOW
INDIC = ["hi", "bn", "mr", "pa", "ta", "te"]
LANG_NAMES = {"de": "German", "fr": "French", "zh": "Chinese", "es": "Spanish", "ja": "Japanese",
              "hi": "Hindi", "ar": "Arabic", "bn": "Bengali", "mr": "Marathi", "pa": "Punjabi",
              "ta": "Tamil", "te": "Telugu"}

NMT_SYSTEMS = ["amazon_translate", "microsoft_translator", "nllb200", "indictrans2"]
LLM_SYSTEMS = ["qwen25_coder_7b", "qwen25_coder_7b_clean"]  # add further LLMs here
PRIMARY_LLM = "qwen25_coder_7b"
BASELINE = "baseline_google_translate"
INDIC_ONLY = {"indictrans2"}

DISPLAY = {
    "baseline_google_translate": "Google Translate",
    "google_translate": "Google Translate",
    "amazon_translate": "Amazon Translate",
    "microsoft_translator": "Microsoft Translator",
    "nllb200": "NLLB-200",
    "indictrans2": "IndicTrans2",
    "qwen25_coder_7b": "Qwen2.5-Coder-7B",
    "qwen25_coder_7b_clean": "Qwen2.5-Coder-7B (clean)",
}
FAMILY = {s: "NMT" for s in NMT_SYSTEMS} | {s: "LLM" for s in LLM_SYSTEMS}

# Fixed categorical order (colour follows the entity, never its rank).
COLORS = {
    "amazon_translate": "#2a78d6",
    "microsoft_translator": "#eb6834",
    "nllb200": "#1baf7a",
    "indictrans2": "#eda100",
    "qwen25_coder_7b": "#e87ba4",
    "qwen25_coder_7b_clean": "#4a3aa7",
    "baseline_google_translate": "#008300",
}

LOWER_IS_BETTER = {"ter"}
METRIC_LABELS = {"bleu": "BLEU", "meteor": "METEOR", "chrf": "chrF++", "rouge_l": "ROUGE-L",
                 "ter": "TER", "comet": "COMET", "bertscore": "BERTScore", "cometkiwi": "CometKiwi"}


def supports(system, lang):
    return system not in INDIC_ONLY or lang in INDIC


def system_dir(system):
    """LLM outputs live in this repo; NMT outputs and the baseline in the NMT repo."""
    if system in LLM_SYSTEMS or system == BASELINE:
        return DATA / system
    return NMT_REPO / "data" / system


def load_lines(system, lang):
    with open(system_dir(system) / f"{lang}.txt", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]


def load_source():
    with open(DATA / "source" / "en.txt", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]


def load_reference(lang):
    return load_lines(BASELINE, lang)


def load_all_scores():
    """NMT + LLM corpus-level scores in one long frame (system, lang, metrics...)."""
    frames = [pd.read_csv(NMT_REPO / "metrics" / "results" / "metric_scores.csv")]
    llm = METRICS / "results" / "metric_scores.csv"
    if llm.exists():
        frames.append(pd.read_csv(llm))
    df = pd.concat(frames, ignore_index=True)

    kiwi = [NMT_REPO / "metrics" / "cometkiwi" / "cometkiwi_scores.csv",
            METRICS / "cometkiwi" / "cometkiwi_scores.csv"]
    kiwi = [pd.read_csv(p) for p in kiwi if p.exists()]
    if kiwi:
        k = pd.concat(kiwi, ignore_index=True)[["system", "lang", "cometkiwi"]]
        df = df.merge(k, on=["system", "lang"], how="outer")
    df["family"] = df.system.map(FAMILY).fillna("Baseline")
    return df


def metric_cols(df):
    return [m for m in METRIC_LABELS if m in df.columns and df[m].notna().any()]


def ensure_dirs():
    for d in (FIGURES, TABLES, METRICS / "analysis"):
        d.mkdir(parents=True, exist_ok=True)
