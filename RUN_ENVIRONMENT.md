# Run Environment

## Qwen2.5-Coder-7B Translation Run

- Date of run: 9–13 September 2026 (from output file timestamps; the Hindi file completed first, 10 Sep 00:26)
- Platform: local Windows 11 laptop
- GPU: NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB VRAM (driver 581.83); the 4.7 GB model does not fit in VRAM, so Ollama offloads part of it to the CPU
- System RAM: 16 GB
- Runtime: Ollama (server version recorded at analysis time: 0.34.4), Python `ollama` client
- Model: `qwen2.5-coder:7b` (Ollama tag), digest `dae161e27b0e`, architecture qwen2, 7.6B parameters, quantization Q4_K_M, context length 32,768
- Driver script: `test_run.py` (one request per string, no batching)
- Decoding: temperature 0.0, top_p 0.9, num_predict 100
- Prompt: fixed system prompt ("expert software localization engine", preserve placeholders/tags/accelerators, return only the translation) + user turn `Target Language: <name>\nSource Text: "<string>"\nTranslation:`
- Post-processing at run time: surrounding whitespace and `"`/`'` stripped
- Source strings: 10,225 of 10,228 (see "Gaps and follow-up run" below)
- Target languages (12): hi, ar, bn, de, es, fr, ja, mr, pa, ta, te, zh

### Gaps and follow-up run

- `test_run.py` read `Dataset-Translated.xlsx` with pandas defaults; three cells containing the literal text `#ERROR!` were parsed as NaN and dropped, so those three strings (en.txt lines 4791, 7204, 8148) were never sent.
- Ten outputs came back empty (ar ×2, ta ×7, te ×1).
- All 46 gaps (3 strings × 12 languages + 10 empty outputs) were translated on 30 September 2026 by `scripts/fill_missing_llm.py` with the identical prompt, model and decoding options. Every filled line is logged in `data/qwen25_coder_7b/FILLED.csv`, and the original gaps in `MISSING.csv`. On retry, the previously empty Tamil/Telugu outputs began with U+FFFD (a broken UTF-8 byte), which suggests why they were stored as empty in the original run.
- Ollama with temperature 0 on a GPU/CPU split is close to deterministic but not guaranteed bit-reproducible across Ollama versions or hardware.

### Reproducibility notes

- Local open-weights model: no API cost; latency depends on hardware (see `metrics/analysis/latency_summary.csv`).
- `latency_sec` is the wall-clock time of each `ollama.chat` call, including prompt processing; it is comparable across languages within this run, but not with the NMT systems, which were run in batches on different hardware.

## Metric Computation (lexical)

- Date of run: 30 September 2026
- Platform: the same Windows laptop, CPU only
- Python: 3.14.6 in a dedicated virtual environment (`.venv`)
- Key library versions: sacrebleu 2.6.0 (with mecab-python3 1.0.12 and ipadic 1.0.0 for Japanese BLEU tokenization), nltk 3.10.3 (METEOR; WordNet), rouge_score 0.1.2. These match the NMT metric environment (`requirements-metrics.txt`); the full lock file is `requirements-lexical-lock.txt`.
- Metric code: `scripts/compute_metrics.py`, copied from the NMT repo with the metric functions unchanged; only the system list and a lazy torch import differ.
- Reference: Google Translate baseline (`data/baseline_google_translate`, byte-identical to the NMT repo; `en.txt` verified against the NMT repo's published MD5).

## Metric Computation (neural): PENDING

COMET (Unbabel/wmt22-comet-da), BERTScore and CometKiwi (Unbabel/wmt22-cometkiwi-da) need a GPU environment pinned to `requirements-metrics.txt` (torch 2.8.0, unbabel-comet 2.2.7, bert-score 0.3.13, setuptools<81), plus Hugging Face access to the two gated Unbabel models. The NMT team ran these on Lightning AI; running the LLM outputs in the same environment keeps the scores comparable.
