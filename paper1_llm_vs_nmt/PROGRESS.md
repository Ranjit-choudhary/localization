# Research Progress & Paper Handoff Log: LLMs vs. Classic NMT for Software UI Localization

## 1. Goal and 4-Week Plan

**Paper Title:** "LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?"
**Target:** 1 journal submission.
**Core Research Question:** In cloud-native localization pipelines, do LLMs preserve runtime invariants (placeholders, accelerators, script purity, encoding) better or worse than classic NMT, and how does their CometKiwi quality compare?

### Status: everything that does not need NMT translation text is DONE (2026-11-12)
**Blocker:** Track 1 NMT translation files. `cloud-native-nmt-benchmark-main/data/*/*.txt` are all 0-byte stubs. Ranjit is requesting them from sir/Track 1. **Do NOT use `../dump/`** (project rule, 2026-11-12).

- [x] **Week 1: Invariant audit**
  - [x] `scripts/audit.py`. Reads LLMs from the LLM repo and NMT **only** from `cloud-native-nmt-benchmark-main/data/`; 0-byte files are skipped.
  - [x] Re-run 2026-11-12 without dump data: 10 LLM suites × 12 langs = 120 pairs, 1,227,360 strings.
  - [x] `results/manual_check_sample.csv` regenerated (150 rows, LLM only, seed 42).
  - [ ] ✍️ Ranjit: fill `my_verdict` (TP/FP) in `manual_check_sample.csv`.
  - [ ] ⏳ Audit NMT systems (automatic once files exist).
- [x] **Week 2: Master table and figures**
  - [x] `results/master_table.csv` (174 rows: system × lang, defects + CometKiwi) and `results/master_table_by_system.csv`.
  - [x] 4 figures at 300 DPI in `figures/` (fig1–fig4). NMT appears only as CometKiwi reference lines in fig2.
  - [ ] ⏳ NMT defect columns and NMT points in figures.
- [x] **Week 3: Statistics**
  - [x] `scripts/stats.py`: defects use cluster bootstrap over source strings + McNemar + Holm; CometKiwi uses language-paired bootstrap + exact Wilcoxon + Holm; adds a `robust` flag.
  - [x] `results/stats_defects_pairwise.csv` (25 tests, 24 robust) and `results/stats_cometkiwi_pairwise.csv` (55 tests, 28 robust).
  - [ ] ⏳ LLM-vs-NMT defect tests (code already in place, family `llm_vs_nmt`; runs automatically).
- [x] **Weeks 3–4: Manuscript**
  - [x] `paper/outline.md`
  - [x] `paper/draft.md` v0.1: full draft; gaps marked `[PENDING-NMT]`, `[PENDING-MANUAL]`, `[CITE]`.
  - [ ] ✍️ Team: references, related work, authors.

---

## 2. Script Inventory (run from the `cs sop/` root)

| Script | Purpose | Outputs |
|---|---|---|
| `python paper1_llm_vs_nmt/scripts/audit.py` | 7-check invariant audit of every system with non-empty files | `results/defects_per_string.csv`, `defect_summary.csv`, `defect_summary_by_system.csv`, `manual_check_sample.csv` |
| `python paper1_llm_vs_nmt/scripts/build_master_table.py` | Merge defects + CometKiwi (both repos) | `results/master_table.csv`, `master_table_by_system.csv` |
| `python paper1_llm_vs_nmt/scripts/stats.py` | Paired significance tests (~80 s) | `results/stats_defects_pairwise.csv`, `stats_cometkiwi_pairwise.csv` |
| `python paper1_llm_vs_nmt/scripts/generate_figures.py` | 4 figures, 300 DPI | `figures/fig1..fig4*.png` |

All scripts overwrite their own outputs, never modify source data, and print a summary.

---

## 3. Activity Log

### 2026-11-04
- Explored both repos; built and ran `audit.py` (this first run also read NMT outputs from `../dump/make it like/data/`; those results are now discarded).

### 2026-11-12
- **Removed dump usage** from `audit.py` and re-ran it. LLM numbers are unchanged; NMT is now skipped (0-byte files).
- Built `build_master_table.py`, `generate_figures.py`, `stats.py`; wrote `paper/outline.md` and `paper/draft.md`.
- Found that the repo's "gpt4o" is actually **gpt-4o-mini** (`findings/experiment_runs.json`).

---

## 4. Decisions (and Why)

1. **No dump data.** NMT string-level data must come from Track 1's own repo. *Why:* user instruction; `make it like` is only a template.
2. **Quality compared on CometKiwi only.** Both repos use `Unbabel/wmt22-cometkiwi-da`. *Why:* Track 1's BLEU/COMET use Google Translate as the reference, so they measure agreement with Google, not quality, and cannot be applied to LLMs fairly.
3. **CometKiwi tests are language-paired (n = 12).** *Why:* only per-language means exist; recomputing per-segment scores for 1.78M strings would take days on the RTX 3050.
4. **Defect bootstrap clusters by source string.** *Why:* the 12 translations of one string are correlated; plain McNemar treats them as independent. `robust` = Holm-significant AND CI excludes 0.
5. **Fair LLM-vs-NMT comparison = baseline LLM vs NMT.** *Why:* only LLMs got the repair step.
6. **Encoding corruption shown as its own category in fig4.** *Why:* 1,343 Qwen strings; hiding it in "Other" would misread the figure.
7. **MADLAD-400 and Amazon Translate.** MADLAD-400 stays in the quality comparison (CometKiwi exists) and gets defects once files arrive. Amazon Translate is dropped, since it existed only in dump.

---

## 5. Key Numbers (sources: `results/*.csv`)

| System | Defect rate | CometKiwi |
|---|---:|---:|
| GPT-4o-mini → + repair | 0.95% → 0.22% | 0.7877 → 0.7877 |
| Llama-3.1-8B → + repair | 2.45% → 0.12% | 0.7483 → 0.7531 |
| Mistral-Nemo-12B → + repair | 8.87% → 0.25% | 0.6872 → 0.7136 |
| Gemma-2-9B → + repair | 17.83% → 0.82% | 0.7395 → 0.7653 |
| Qwen-2.5-7B → + repair | 5.11% → 1.54% | 0.7046 → 0.7069 |
| Google / Microsoft / NLLB / MADLAD / IndicTrans2 | ⏳ | 0.7939 / 0.7894 / 0.7834 / 0.7703 / 0.7979 (6 langs) |

- Repair never introduced a new defect: 0 clean→flawed strings in every model. Invented placeholders fell from 11,932 to 130.
- GPT-4o-mini is statistically tied with Google, Microsoft, NLLB and IndicTrans2 on CometKiwi and beats MADLAD-400 (+0.0175, 12/12 langs).
- All open 7–12B LLMs (baseline and repaired) are significantly below Google and Microsoft (−0.024 to −0.107).
- The only non-robust defect test: repaired GPT-4o-mini vs repaired Mistral (Holm p = 0.034, CI includes 0).

---

## 6. Known Issues Checked

1. **README −91.2% vs −77.2% (GPT-4o-mini):** both correct; −91.2% covers the 9 non-Latin languages and −77.2% all 12. Report both.
2. **README repaired counts differ slightly from our audit** (Mistral 305 vs 312, Gemma 996 vs 1001, Qwen 1887 vs 1888). *Cause:* the repair validator has no `empty_output` check and our audit does; the differences are 7, 5 and 1 empty outputs. Use our audit numbers.
3. **Circularity:** repair accepts a fix only if it passes the same checks as the audit. Stated as threat #1 in the draft; CometKiwi gain is the independent evidence.
4. **Track 1 README** has citation, git-URL and system-count wording inconsistencies (see 2026-11-04 notes); not our files, so not edited.
5. **`llm models/` git repo** (remote `Ranjit-choudhary/localization`) has uncommitted local deletions, including `data/baseline_google_translate/*`. Not touched.

---

## 7. Next Steps

1. ⏳ **When Track 1 NMT files arrive:** copy them into `cloud-native-nmt-benchmark-main/data/<system>/<lang>.txt` (10,228 lines each, UTF-8), then run the 4 scripts in order (Section 2). Then fill `[PENDING-NMT]` in `paper/draft.md` (Table 2 rows, §4.1, §4.2, §4.5, abstract, conclusion).
2. ✍️ **Manual check:** fill `my_verdict` in `results/manual_check_sample.csv`, then compute precision and FP rate and fill `[PENDING-MANUAL]` (§3.3, §4.2, §6).
3. ✍️ **Team:** references (`[CITE]`), related work, author list.
