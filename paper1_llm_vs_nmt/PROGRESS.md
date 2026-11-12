# Research Progress & Paper Handoff Log: LLMs vs. Classic NMT for Software UI Localization

## 1. Goal and Status

**Paper Title:** "LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?"
**Target:** 1 journal submission.
**Core Research Question:** In cloud-native localization pipelines, do LLMs preserve runtime invariants (placeholders, accelerators, script purity, encoding) better or worse than classic NMT, and how does their CometKiwi quality compare?
**GitHub:** https://github.com/Ranjit-choudhary/localization/tree/main/paper1_llm_vs_nmt

### Task checklist (all research work complete, 2026-11-12)
NMT data: `nmt-benchmarking-paper-main/data/` (Track 1, added 2026-11-12; 55 files pass `CHECKSUMS.txt`). The old `cloud-native-nmt-benchmark-main` folder (0-byte stubs) was replaced by it. **Never use `../dump/`.**

- [x] **Invariant audit** (`scripts/audit.py`): 10 LLM suites + 5 NMT systems, 1,779,672 strings. Accelerator check fixed (Decision 8).
- [x] **Audit validation:** LLM sample (`manual_check_sample.csv`, 91%) + NMT sample (`manual_check_sample_nmt.csv`, 94%) = 92% precision overall.
- [x] **Master table and figures:** all 15 suites in `results/master_table*.csv` and the 4 figures.
- [x] **Statistics:** 75 defect tests (72 robust), 55 CometKiwi tests (28 robust).
- [x] **Manuscript:** `paper/draft.md` v0.3, complete, no PENDING markers, 41 references.
- [ ] ✍️ Team: `[AUTHORS]`.
- [ ] Optional: human spot-check of `my_verdict` in both samples; re-run LLM repair with the corrected accelerator check (GPU).

---

## 2. Script Inventory (run from the `cs sop/` root)

| Script | Purpose | Outputs |
|---|---|---|
| `python paper1_llm_vs_nmt/scripts/audit.py` | 7-check invariant audit of every system with non-empty files (`--new-sample` redraws the graded sample; normally kept) | `results/defects_per_string.csv`, `defect_summary.csv`, `defect_summary_by_system.csv`, `manual_check_sample.csv` (only if missing) |
| `python paper1_llm_vs_nmt/scripts/build_master_table.py` | Merge defects + CometKiwi (both repos) | `results/master_table.csv`, `master_table_by_system.csv` |
| `python paper1_llm_vs_nmt/scripts/stats.py` | Paired significance tests (~80 s) | `results/stats_defects_pairwise.csv`, `stats_cometkiwi_pairwise.csv` |
| `python paper1_llm_vs_nmt/scripts/generate_figures.py` | 4 figures, 300 DPI | `figures/fig1..fig4*.png` |
| `python paper1_llm_vs_nmt/scripts/sample_nmt_check.py` | NMT validation sample (kept if exists; `--new-sample` redraws) | `results/manual_check_sample_nmt.csv` |

All scripts overwrite their own outputs, never modify source data, and print a summary.

---

## 3. Activity Log

### 2026-11-04
- Explored both repos; built and ran `audit.py` (this first run also read NMT outputs from `../dump/make it like/data/`; those results are now discarded).

### 2026-11-12
- Removed dump usage; built master table, figures, statistics, outline and draft v0.1; pushed to GitHub `main`.
- Graded the 150-row manual sample. The one miss revealed the accelerator bug; fixed it, re-ran everything, and rewrote the draft as v0.2 with real references.
- Found that the repo's "gpt4o" is actually **gpt-4o-mini** (`findings/experiment_runs.json`).
- Track 1 NMT files arrived (`nmt-benchmarking-paper-main`). Verified checksums and line counts, audited all 5 NMT systems, validated the audit on NMT (94%), redrew figures with NMT, ran LLM-vs-NMT stats, and completed draft v0.3.

---

## 4. Decisions (and Why)

1. **No dump data.** NMT string-level data must come from Track 1's own repo. *Why:* user instruction; `make it like` is only a template.
2. **Quality compared on CometKiwi only.** Both repos use `Unbabel/wmt22-cometkiwi-da`. *Why:* Track 1's BLEU/COMET use Google Translate as the reference, so they measure agreement with Google, not quality.
3. **CometKiwi tests are language-paired (n = 12).** *Why:* only per-language means exist; recomputing per-segment scores for 1.78M strings would take days on the RTX 3050.
4. **Defect bootstrap clusters by source string.** *Why:* the 12 translations of one string are correlated. `robust` = Holm-significant AND CI excludes 0.
5. **Fair LLM-vs-NMT comparison = baseline LLM vs NMT.** *Why:* only LLMs got the repair step.
6. **Encoding corruption and accelerators get their own colours in fig4.** *Why:* both are large for some models.
7. **MADLAD-400 stays** (CometKiwi exists; defects once files arrive). **Amazon Translate dropped**, since it existed only in dump.
8. **Accelerator regex fixed:** `&[^\s\d_;]` → `&\s?[^\s\d_;&]` (after removing XML entities). *Why:* OPUS KDE4 writes accelerators as `& File`; the old pattern matched 1 of 785 accelerator sources. Losses were verified by hand (dropped `&`, translated as "and", escaped to `&amp;`, moved to the end). The LLM repo's README numbers use the old pattern and are therefore lower; our numbers supersede them for the paper. User approved the fix 2026-11-12.
9. **Manual sample kept across re-runs.** *Why:* it holds the grades; `audit.py` only redraws it with `--new-sample`.

---

## 5. Key Numbers (sources: `results/*.csv`)

| System | Defect rate | CometKiwi | Accelerators lost |
|---|---:|---:|---:|
| GPT-4o-mini → + repair | 2.53% → 1.80% | 0.7877 | 20.6% |
| Qwen-2.5-7B → + repair | 5.98% → 2.44% | 0.7046 → 0.7069 | 11.7% |
| Llama-3.1-8B → + repair | 7.94% → 5.66% | 0.7483 → 0.7531 | 72.1% |
| Mistral-Nemo-12B → + repair | 14.10% → 5.56% | 0.6872 → 0.7136 | 69.2% |
| Gemma-2-9B → + repair | 21.92% → 5.03% | 0.7395 → 0.7653 | 53.9% |
| NLLB-200 | 4.18% | 0.7834 | 30.3% |
| Google Translate | 6.28% | 0.7939 | 65.2% |
| IndicTrans2 (6 langs) | 7.60% | 0.7979 | 53.6% |
| Microsoft Translator | 7.71% | 0.7894 | 57.1% |
| MADLAD-400 | 9.06% | 0.7703 | 69.3% |

- **RQ1:** no paradigm dominates. GPT-4o-mini is safer than every NMT system; Mistral and Gemma are worse than every NMT system; Qwen and Llama sit inside the NMT range.
- NMT never invents placeholders but breaks existing ones (`%1` → `1%`, `% 1`); IndicTrans2 breaks 99.5% of them. Open LLMs invent them (11,932).
- **RQ3:** every repaired LLM is safer than Google, Microsoft, MADLAD and IndicTrans2; only repaired GPT-4o-mini and Qwen beat NLLB-200.
- **RQ2:** GPT-4o-mini is tied with Google, Microsoft, NLLB and IndicTrans2 on CometKiwi; open LLMs are below Google and Microsoft.
- GPT-4o-mini + repair is the best trade-off (1.80% defects, NMT-level quality).

---

## 6. Known Issues Checked

1. **README −91.2% vs −77.2% (GPT-4o-mini):** both were correct under the old accelerator check; superseded by the new numbers.
2. **README repaired counts** (e.g. Mistral 305 vs 312): the repair validator had no `empty_output` check. Also superseded by the accelerator fix.
3. **Circularity:** repair accepts fixes that pass its own validator. Stated as threat #1 in the draft; CometKiwi gain is the independent evidence.
4. **Track 1 bibliography:** ref 28 (CometKiwi) lists "Yu N" as third author; the real third author is Guerreiro NM. Corrected in our draft only.
5. **Track 1 README** inconsistencies (citation, git URL, system count): not our files, not edited.
6. **`llm models/` local git repo** has uncommitted deletions and is now 1+ commits behind GitHub `main`. Not touched.

---

## 7. Next Steps

1. ✍️ Fill `[AUTHORS]` in `paper/draft.md`.
2. Optional: human spot-check of `my_verdict` in both validation samples.
3. Optional: re-run LLM repair with the corrected accelerator check (GPU), then re-run the 4 scripts.
4. Convert `paper/draft.md` to the target journal's LaTeX template.
