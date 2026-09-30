# Benchmarking LLMs against NMT for Software UI Localization

Track 2 (LLM benchmarking) of the localization research roadmap. Local LLMs translate the same
10,228 KDE4 software UI strings into the same 12 languages as the NMT study
(`../make it like`, "Benchmarking neural machine translation for multilingual assistive
technology interfaces"). They are scored with the **identical metric code and Google Translate
reference**, so LLM and NMT results can be compared directly for the NMT-vs-LLM comparative
paper (Paper 1).

## Systems

| System | Type | Role |
| --- | --- | --- |
| Google Translate | Commercial NMT | Baseline / reference (from NMT repo) |
| Amazon Translate, Microsoft Translator | Commercial NMT | Compared (scores and outputs read from NMT repo) |
| NLLB-200, IndicTrans2 (6 Indic pairs) | Open NMT | Compared (scores and outputs read from NMT repo) |
| **Qwen2.5-Coder-7B** (`qwen25_coder_7b`) | Open LLM, local (Ollama, Q4_K_M) | Evaluated |
| Qwen2.5-Coder-7B (clean) (`qwen25_coder_7b_clean`) | Same run, post-processed | Ablation: first non-empty line, quotes stripped |

Further LLMs (Llama 3.2, TranslateGemma 4B) plug in without code changes beyond the system lists; see
"Adding another LLM" below.

Target languages: high-resource de, fr, zh, es, ja; low-resource hi, ar, bn, mr, pa, ta, te.

## Repository Structure

```
llm models/
├── test_run.py                    # original Ollama translation driver
├── Dataset-Translated.xlsx        # source strings as used by test_run.py
├── Qwen2.5/                       # raw run output: translations_<language>.csv (+ latency)
├── data/
│   ├── source/en.txt              # 10,228 source strings (MD5-verified copy of NMT repo)
│   ├── baseline_google_translate/ # reference translations (copy of NMT repo)
│   ├── qwen25_coder_7b/           # aligned outputs <lang>.txt + latency.csv, MISSING.csv, FILLED.csv
│   └── qwen25_coder_7b_clean/     # post-processing ablation
├── scripts/
│   ├── prepare_llm_outputs.py     # raw CSV -> aligned 10,228-line files (verified alignment)
│   ├── fill_missing_llm.py        # translate strings the original run skipped / returned empty
│   ├── compute_metrics.py         # 7 reference-based metrics (NMT repo code, unchanged metrics)
│   ├── compute_cometkiwi.py       # reference-free QE (GPU)
│   ├── merge_metric_results.py, make_pivots.py
│   ├── common.py                  # shared config; NMT repo path (NMT_REPO env var)
│   ├── analysis.py                # combined NMT+LLM tables, Kendall tau, figures
│   ├── significance.py            # paired bootstrap, Wilcoxon, Friedman (Holm-corrected)
│   └── error_analysis.py          # artifact preservation, failure modes, string types, latency
├── metrics/
│   ├── results/                   # corpus-level scores (+ pivots/)
│   ├── sentence_level/            # sentence chrF++ for every system x language
│   ├── significance/              # statistical test outputs
│   └── analysis/                  # error analysis, latency, metric agreement
├── tables/                        # CSV + LaTeX (booktabs) tables for the paper
├── figures/                       # PNG (300 dpi) + PDF figures
└── Notebooks/llm_benchmarking_pipeline.ipynb   # GPU step (COMET, BERTScore, CometKiwi)
```

## Pipeline

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-lexical-lock.txt

# 1. Align raw LLM output with en.txt (aborts on any misalignment)
python scripts/prepare_llm_outputs.py --raw-dir Qwen2.5 --system qwen25_coder_7b --clean-variant
# 2. Fill strings the run skipped/returned empty (same prompt + decoding; logged in FILLED.csv)
python scripts/fill_missing_llm.py --system qwen25_coder_7b --model qwen2.5-coder:7b
# 3. Metrics: lexical on CPU; neural + CometKiwi on GPU (see notebook)
python scripts/compute_metrics.py --all --metrics lexical
python scripts/compute_metrics.py --all --metrics neural      # GPU
python scripts/compute_cometkiwi.py --all                     # GPU, gated model
python scripts/merge_metric_results.py && python scripts/make_pivots.py
# 4. Analysis (run from scripts/)
cd scripts && python significance.py && python analysis.py && python error_analysis.py
```

## Adding another LLM

1. Run `test_run.py` with the model and put its `translations_<language>.csv` files in a folder (e.g. `Llama3.2/`).
2. `python scripts/prepare_llm_outputs.py --raw-dir Llama3.2 --system llama32_3b --clean-variant`
3. `python scripts/fill_missing_llm.py --system llama32_3b --model llama3.2` if `MISSING.csv` lists lines.
4. Add `llama32_3b` (and `_clean`) to `LLM_SYSTEMS`, `DISPLAY` and `COLORS` in `scripts/common.py`, and to `SYSTEMS` in `compute_metrics.py` / `compute_cometkiwi.py`.
5. Re-run steps 3-4 of the pipeline.

Before running further models, fix two issues in `test_run.py`: read the spreadsheet so `#ERROR!` cells are
not dropped (`keep_default_na=False`), and correct the Marathi key `"mr:"` → `"mr"`.

## Caveats (same as the NMT study)

- Reference-based metrics measure agreement with Google Translate, not certified correctness.
- Word-level lexical metrics are unreliable for zh, ja and the Indic languages; weight chrF++,
  neural and reference-free metrics more heavily.
- IndicTrans2 is compared only on its six Indic languages (the `indic6` tables).
