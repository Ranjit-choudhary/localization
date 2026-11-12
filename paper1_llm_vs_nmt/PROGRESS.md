# Research Progress & Paper Handoff Log: LLMs vs. Classic NMT for Software UI Localization

## 1. Goal and Status

**Paper Title:** "LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?"
**Target:** 1 journal submission.
**Core Research Question:** In cloud-native localization pipelines, do LLMs preserve runtime invariants (placeholders, accelerators, script purity, encoding) better or worse than classic NMT, and how does their CometKiwi quality compare?
**GitHub:** https://github.com/Ranjit-choudhary/localization/tree/main/paper1_llm_vs_nmt

### Task checklist
**Blocker:** Track 1 NMT translation files. `cloud-native-nmt-benchmark-main/data/*/*.txt` are all 0-byte stubs. Ranjit is requesting them from sir/Track 1. **Do NOT use `../dump/`** (project rule, 2026-11-12).

- [x] **Invariant audit** (`scripts/audit.py`): LLMs from the LLM repo, NMT **only** from `cloud-native-nmt-benchmark-main/data/` (0-byte files skipped). 10 LLM suites × 12 langs, 1,227,360 strings.
  - [x] Accelerator check fixed 2026-11-12 (see Decision 8).
  - [ ] ⏳ NMT systems (automatic once files exist).
- [x] **Audit validation:** `results/manual_check_sample.csv` graded (`model_verdict`, `model_note`). Precision 91%, miss rate 2%.
  - [ ] ✍️ Optional: Ranjit spot-checks about 20 rows in `my_verdict`.
- [x] **Master table and figures:** `results/master_table*.csv`, 4 figures at 300 DPI in `figures/`.
- [x] **Statistics** (`scripts/stats.py`): `results/stats_defects_pairwise.csv` (25 tests, 24 robust) and `results/stats_cometkiwi_pairwise.csv` (55 tests, 28 robust).
- [x] **Manuscript:** `paper/outline.md`, `paper/draft.md` v0.2 with 41 references (Track 1's 30 plus 11 checked additions).
  - [ ] ⏳ `[PENDING-NMT]` sections.
  - [ ] ✍️ `[AUTHORS]`.
- [ ] Optional follow-up: re-run the LLM repair loop with the corrected accelerator check (needs GPU and the LLM repo's `run_agentic_repair.py`).

---

## 2. Script Inventory (run from the `cs sop/` root)

| Script | Purpose | Outputs |
|---|---|---|
| `python paper1_llm_vs_nmt/scripts/audit.py` | 7-check invariant audit of every system with non-empty files (`--new-sample` redraws the graded sample; normally kept) | `results/defects_per_string.csv`, `defect_summary.csv`, `defect_summary_by_system.csv`, `manual_check_sample.csv` (only if missing) |
| `python paper1_llm_vs_nmt/scripts/build_master_table.py` | Merge defects + CometKiwi (both repos) | `results/master_table.csv`, `master_table_by_system.csv` |
| `python paper1_llm_vs_nmt/scripts/stats.py` | Paired significance tests (~80 s) | `results/stats_defects_pairwise.csv`, `stats_cometkiwi_pairwise.csv` |
| `python paper1_llm_vs_nmt/scripts/generate_figures.py` | 4 figures, 300 DPI | `figures/fig1..fig4*.png` |

All scripts overwrite their own outputs, never modify source data, and print a summary.

---

## 3. Activity Log

### 2026-11-04
- Explored both repos; built and ran `audit.py` (this first run also read NMT outputs from `../dump/make it like/data/`; those results are now discarded).

### 2026-11-12
- Removed dump usage; built master table, figures, statistics, outline and draft v0.1; pushed to GitHub `main`.
- Graded the 150-row manual sample. The one miss revealed the accelerator bug; fixed it, re-ran everything, and rewrote the draft as v0.2 with real references.
- Found that the repo's "gpt4o" is actually **gpt-4o-mini** (`findings/experiment_runs.json`).

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

| System | Defect rate (baseline → repaired) | CometKiwi (baseline → repaired) | Accelerators lost (of 9,420) |
|---|---:|---:|---:|
| GPT-4o-mini | 2.53% → 1.80% | 0.7877 → 0.7877 | 20.6% |
| Qwen-2.5-7B | 5.98% → 2.44% | 0.7046 → 0.7069 | 11.7% |
| Llama-3.1-8B | 7.94% → 5.66% | 0.7483 → 0.7531 | 72.1% |
| Mistral-Nemo-12B | 14.10% → 5.56% | 0.6872 → 0.7136 | 69.2% |
| Gemma-2-9B | 21.92% → 5.03% | 0.7395 → 0.7653 | 53.9% |
| Google / Microsoft / NLLB / MADLAD / IndicTrans2 | ⏳ | 0.7939 / 0.7894 / 0.7834 / 0.7703 / 0.7979 (6 langs) | ⏳ |

- Repair: −29% to −77% defects. It never turns a clean string into a flawed one, but it does not fix accelerators (its validator never saw them). Invented placeholders fell from 11,932 to 130.
- GPT-4o-mini is tied with Google, Microsoft, NLLB and IndicTrans2 on CometKiwi and beats MADLAD-400 (+0.0175, 12/12 langs).
- All open 7–12B LLMs are significantly below Google and Microsoft (−0.024 to −0.107).
- Audit precision is 91% (copy fallback 87.5%; all other types 100%); miss rate 2% (the accelerator bug, now fixed).

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

1. ⏳ **When Track 1 NMT files arrive:** copy them into `cloud-native-nmt-benchmark-main/data/<system>/<lang>.txt` (10,228 lines each, UTF-8), run the 4 scripts in order (Section 2), then fill `[PENDING-NMT]` in `paper/draft.md` (abstract, Table 2, §4.1, §4.2, §4.5, §5, §7).
2. ✍️ Fill `[AUTHORS]`.
3. Optional: spot-check `my_verdict`; re-run repair with the corrected accelerator check.
