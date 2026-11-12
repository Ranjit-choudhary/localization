# LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?

> **DRAFT v0.1 (2026-11-12).** Every number in this draft comes from a file in `paper1_llm_vs_nmt/results/` (the source is noted beside each table).
> Markers:
> - **[PENDING-NMT]**: needs the Track 1 NMT translation files (`cloud-native-nmt-benchmark-main/data/*.txt` are currently 0-byte). Re-run `audit.py → build_master_table.py → stats.py → generate_figures.py` and fill in.
> - **[PENDING-MANUAL]**: needs the human verdicts in `results/manual_check_sample.csv`.
> - **[CITE]**: reference to be added or checked by the team.
> - Authors and affiliations: to be confirmed by the team.

---

## Abstract

Cloud-native delivery pipelines increasingly push machine translations of user-interface (UI) strings straight into production builds. A translation that reads well can still break software: a dropped `%1` placeholder crashes a format call, a lost `&` removes a keyboard shortcut, and stray characters from another script or a `�` replacement character corrupt the screen. Standard translation metrics do not see these failures. We compare five large language models (GPT-4o-mini, Llama-3.1-8B, Mistral-Nemo-12B, Gemma-2-9B, Qwen-2.5-7B) with five neural machine translation (NMT) systems (Google Translate, Microsoft Translator, NLLB-200, MADLAD-400, IndicTrans2) on 10,228 KDE software strings in twelve languages. We use a deterministic seven-check invariant audit together with reference-free CometKiwi quality estimation. Zero-shot LLMs break between 0.95% (GPT-4o-mini) and 17.83% (Gemma-2-9B) of strings. The failures follow distinct, model-specific patterns: Mistral-Nemo and Llama mostly invent placeholders the source never had, while Gemma and Qwen collapse into untranslated copies on low-resource Indic languages (Gemma: 77.9% of Punjabi and 75.7% of Telugu strings). A compiler-guided self-repair loop, where each model fixes only its own flagged strings under targeted constraints, cuts defects by 69.9–97.1% without introducing a single new defect, and it raises CometKiwi for every open-weights model. On quality, GPT-4o-mini is statistically indistinguishable from Google Translate, Microsoft Translator, NLLB-200 and IndicTrans2, and significantly better than MADLAD-400. The four open 7–12B models remain significantly below the commercial NMT engines even after repair. [PENDING-NMT: one sentence comparing NMT defect rates.] We release the audit, statistics and figures as re-runnable scripts.

**Keywords:** software localization, large language models, neural machine translation, quality estimation, CometKiwi, continuous localization, cloud-native CI/CD

---

## 1. Introduction

Software localization has moved from batch hand-offs to continuous localization. New UI strings are machine-translated and merged within the same CI/CD cycle that ships the code [CITE: continuous localization; Track 1 paper refs 5–7, 15–16]. In this setting there is often no human reviewer between the translation engine and the build, so a translation must be correct as software, not only as language.

Software strings carry *runtime invariants* that ordinary text does not. These include format placeholders (`%1`, `%d`, `{name}`) that the program fills at run time, keyboard accelerators (`&File`), the target script, valid UTF-8, and the requirement that a string actually be translated rather than echoed. Breaking any of these causes a visible bug or a crash, even when a quality metric scores the sentence highly. Reference-based metrics (BLEU, COMET) and quality-estimation models (CometKiwi) are built to judge meaning and fluency. They are not built to check whether `%1` survived.

Two kinds of engine now compete for this job. Classic encoder-decoder NMT systems (commercial APIs and open models such as NLLB-200, MADLAD-400 and IndicTrans2) are fast and predictable. Instruction-tuned LLMs follow format rules written in a prompt and can be asked to correct themselves, but they also hallucinate, add chatter, and degrade on low-resource languages. Deployment teams need evidence on both safety and quality to choose between them.

We ask:

- **RQ1 (safety).** Which paradigm breaks fewer software strings, and which invariants does each break?
- **RQ2 (quality).** How does reference-free translation quality (CometKiwi) compare between LLMs and NMT?
- **RQ3 (repair).** Does compiler-guided self-repair change the safety–quality trade-off for LLMs?

**Contributions.**
1. A deterministic, re-runnable seven-check invariant audit for software UI translations, with an allowlist for legitimate non-translatable tokens (NTTs), applied to 1,227,360 LLM translations [PENDING-NMT: + NMT count].
2. A controlled comparison of 5 LLMs and 5 NMT systems on the same 10,228 source strings in 12 languages, using the same CometKiwi checkpoint for both.
3. A failure taxonomy showing that LLM defects are model-specific and largely prompt-induced (11,932 invented placeholders) or resource-induced (copy collapse on Indic languages).
4. Evidence that a validator-in-the-loop self-repair step removes 69.9–97.1% of LLM defects with no new defects introduced, together with paired statistics (cluster bootstrap, McNemar, Wilcoxon, Holm) for every claim.

---

## 2. Related Work

**Software and continuous localization.** [CITE: Waterfall → Agile → Continuous Localization; reuse Track 1 paper §2.1.]

**NMT for software content.** Multilingual NMT models such as NLLB-200 [CITE: NLLB Team 2022], MADLAD-400 [CITE: Kudugunta et al. 2023] and IndicTrans2 [CITE: Gala et al. 2023] cover hundreds of languages. Prior work identifies terminology consistency, UI fragmentation and missing context as the main problems for software strings [CITE: Track 1 refs 9, 10, 18].

**LLMs as translators.** [CITE: recent LLM-MT evaluations, e.g. WMT general task LLM submissions; zero-shot prompting studies.]

**Quality estimation.** CometKiwi [CITE: Rei et al. 2022] predicts quality from source and hypothesis alone, which makes it suitable when references are absent or are themselves machine output. Its training objective rewards adequacy and fluency, not format invariants. This gap motivates our separate audit.

**Self-correction with external feedback.** [CITE: self-refine / tool-feedback / compiler-feedback correction literature.] Our repair loop differs in using a deterministic validator as the acceptance gate, so a correction is kept only if it is provably compliant.

---

## 3. Experimental Setup

### 3.1 Corpus and languages
We use a fixed set of **10,228 English UI strings** from the KDE desktop environment (OPUS KDE4) [CITE]. The source file has SHA-256 `464d6582…fe281f` and is identical in both team repositories. Targets are **12 languages**: five high-resource (de, fr, es, zh, ja) and seven low-resource (hi, ar, bn, mr, pa, ta, te), following the Track 1 study. Every system translates the same source lines, so every comparison is paired at the string level.

### 3.2 Systems

**Table 1. Systems evaluated.**

| Family | System | Checkpoint / access | Languages |
|---|---|---|---|
| LLM (API) | GPT-4o-mini | `gpt-4o-mini`, OpenAI API, T = 0 | 12 |
| LLM (open) | Llama-3.1-8B | `meta-llama/Llama-3.1-8B-Instruct`, vLLM | 12 |
| LLM (open) | Mistral-Nemo-12B | `mistralai/Mistral-Nemo-Instruct-2407`, vLLM | 12 |
| LLM (open) | Gemma-2-9B | `google/gemma-2-9b-it`, vLLM | 12 |
| LLM (open) | Qwen-2.5-7B | `Qwen/Qwen2.5-7B-Instruct`, vLLM | 12 |
| NMT (commercial) | Google Translate | GOOGLETRANSLATE() in Google Sheets, 3 Sep 2026 | 12 |
| NMT (commercial) | Microsoft Translator | Azure AI Translator v3.0, 6 Sep 2026 | 12 |
| NMT (open) | NLLB-200 | `facebook/nllb-200-distilled-600M`, greedy | 12 |
| NMT (open) | MADLAD-400 | `google/madlad400-3b-mt`, fp16, greedy | 12 |
| NMT (open) | IndicTrans2 | `ai4bharat/indictrans2-en-indic-1B`, greedy | 6 (Indic) |

Note: the LLM repository labels the API model `gpt4o`, but the run log (`findings/experiment_runs.json`) records `gpt-4o-mini`. We report it as GPT-4o-mini throughout.

All LLMs share one zero-shot system prompt (`prompts/system_zero_shot.txt`). It asks for a single-line translation and to "preserve all placeholders, format specifiers, and variables (e.g., {0}, {name}, %s, %d, …) exactly as written". Open-weights models ran on an NVIDIA A100-SXM4-80GB. NMT configurations are those of the Track 1 study [CITE: Track 1 paper §3.5].

### 3.3 Invariant audit
Every output line is checked against its source line for seven defect types (`scripts/audit.py`):

1. **Broken placeholder.** The multiset of `%N`, `%x` and `{…}` tokens differs between source and output (omitted, invented or altered).
2. **Broken accelerator.** The source has an `&` accelerator (XML entities excluded) and the output has none.
3. **Script contamination.** The output contains characters from a Unicode block foreign to the target language (e.g. CJK or Cyrillic in Hindi).
4. **Encoding corruption.** The output contains U+FFFD.
5. **Conversational chatter.** The output starts with phrases such as "Here is the translation" or "Note:".
6. **Copy fallback.** The output equals the source (longer than 3 characters, containing letters) and the source is not a legitimate NTT.
7. **Empty output.** The output is empty while the source is not.

The **NTT allowlist** exempts strings that should stay untranslated: hardware and protocol acronyms (USB, SCSI, IPv6, …), spreadsheet formulas (`BIN2OCT(value)`), POSIX format descriptors, XML entities, X11 colour names, short upper-case identifiers, time-zone paths, and single-word Western-European cognates for de/es/fr. A string counts as *flawed* if it has at least one defect. Defect rate = flawed strings / audited strings.

**Audit precision.** We drew a stratified validation sample (100 flagged + 50 unflagged strings, seed 42; `results/manual_check_sample.csv`). [PENDING-MANUAL: report precision, false-positive rate and the false-negative rate on the unflagged stratum.]

### 3.4 Compiler-guided self-repair (LLMs only)
For each baseline LLM, every flagged string goes back to **the same model** with a targeted system prompt (`scripts/run_agentic_repair.py`). The prompt contains only the rules matching the detected defects: the exact placeholder list (or, when the model invented placeholders, an instruction to add no variables), the accelerator rule, a script-purity rule naming the target script, or a "do not return the source unchanged" rule with a de-camel-cased meaning hint. Decoding is greedy (T = 0). The candidate is re-validated, and it **replaces the original only if it passes every check**. Otherwise the original line is kept. Unflagged strings are never touched.

### 3.5 Quality estimation
Both tracks scored every output with the same reference-free model, **CometKiwi `Unbabel/wmt22-cometkiwi-da`** [CITE: Rei et al. 2022]. This makes LLM and NMT scores directly comparable. Only per-(system, language) means are available, so quality comparisons are paired at the language level. Reference-based metrics from the Track 1 study (BLEU, COMET, etc.) use Google Translate output as the reference. They therefore measure agreement with Google rather than quality, and we do not use them here.

### 3.6 Statistical analysis
All tests are paired, with 10,000 bootstrap resamples and seed 42 (`scripts/stats.py`).

- **Defects (string level).** The unit is a (language, source line) pair; n = 122,736 per LLM. We report the risk difference in percentage points with a 95% **cluster-bootstrap** CI that resamples whole source strings, so the 12 translations of one string stay together. We also report a **McNemar** test on discordant pairs (exact binomial when b + c < 25, otherwise χ² with continuity correction) and the paired odds ratio.
- **CometKiwi (language level).** The unit is a language; n = 12, or 6 for IndicTrans2. We report the mean difference with a 95% bootstrap CI over languages, an **exact Wilcoxon signed-rank** test, and Cohen's d_z.
- **Multiplicity.** **Holm–Bonferroni** correction within each family (25 defect tests; 55 CometKiwi tests). We call a result *robust* when it is Holm-significant **and** its bootstrap CI excludes zero.

With 12 languages, the smallest attainable exact Wilcoxon p is 0.00049. With 6 languages it is 0.031, so no IndicTrans2 comparison can survive Holm correction. We flag this rather than hide it.

---

## 4. Results

### 4.1 RQ1: How often does each system break strings?

**Table 2. Invariant defects per system (12 languages × 10,228 strings).** Source: `results/master_table_by_system.csv`.

| System | Flawed | Defect rate | High-res. | Low-res. | Copy fallback | Placeholder | Script | Encoding |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-4o-mini | 1,169 | 0.95% | 1.28% | 0.72% | 1,083 | 5 | 81 | 0 |
| Llama-3.1-8B | 3,008 | 2.45% | 2.32% | 2.54% | 1,299 | 1,692 | 0 | 10 |
| Qwen-2.5-7B | 6,267 | 5.11% | 1.84% | 7.44% | 3,933 | 691 | 328 | 1,343 |
| Mistral-Nemo-12B | 10,883 | 8.87% | 10.01% | 8.05% | 718 | 10,148 | 0 | 10 |
| Gemma-2-9B | 21,888 | 17.83% | 1.76% | 29.31% | 20,611 | 43 | 1,226 | 0 |
| GPT-4o-mini + repair | 267 | 0.22% | 0.43% | 0.07% | 232 | 4 | 31 | 0 |
| Llama-3.1-8B + repair | 149 | 0.12% | 0.20% | 0.07% | 89 | 52 | 0 | 1 |
| Mistral-Nemo-12B + repair | 312 | 0.25% | 0.27% | 0.24% | 161 | 141 | 0 | 1 |
| Gemma-2-9B + repair | 1,001 | 0.82% | 0.35% | 1.15% | 885 | 1 | 109 | 0 |
| Qwen-2.5-7B + repair | 1,888 | 1.54% | 0.33% | 2.40% | 1,167 | 52 | 136 | 541 |
| Google Translate | [PENDING-NMT] | | | | | | | |
| Microsoft Translator | [PENDING-NMT] | | | | | | | |
| NLLB-200 | [PENDING-NMT] | | | | | | | |
| MADLAD-400 | [PENDING-NMT] | | | | | | | |
| IndicTrans2 (6 langs) | [PENDING-NMT] | | | | | | | |

Accelerator, chatter and empty-output defects are rare (≤ 10 per suite) and are omitted from the table; full counts are in the CSV.

Among zero-shot LLMs, GPT-4o-mini is the safest (0.95%) and Gemma-2-9B the least safe (17.83%). Every pairwise difference between baseline LLMs is robust (`results/stats_defects_pairwise.csv`, family `baseline_pairwise`). For example, GPT-4o-mini vs Llama-3.1-8B is −1.50 pp [−1.70, −1.29] and Mistral-Nemo vs Qwen is +3.76 pp [3.36, 4.16]. Figure 3 shows that the variation is concentrated in a few language–model cells. Gemma breaks 77.9% of Punjabi and 75.7% of Telugu strings, and 19.2% of Marathi and of Tamil. Qwen breaks 14.8% of Punjabi strings. Mistral-Nemo is uniformly poor (5.7–12.4% in every language).

[PENDING-NMT: NMT defect rates, the LLM-vs-NMT comparison (family `llm_vs_nmt`, generated automatically once the files exist), and the answer to RQ1. The fair comparison is **baseline LLM vs NMT**, since neither had any post-processing.]

### 4.2 Failure taxonomy
Figure 4 shows that each model fails in its own way:

- **Invented placeholders (Mistral-Nemo, Llama).** 97% of Mistral-Nemo's placeholder errors and 90% of Llama's are placeholders *added* to strings that had none: 9,820 of 10,148 and 1,529 of 1,692 (`reports/placeholder_error_decomposition.csv`). Across the open models, 11,932 strings received an invented placeholder. Because the system prompt lists example specifiers (`{0}`, `%s`, `%d`), we read this as **prompt-induced**: a rule meant to protect placeholders leads smaller models to insert them.
- **Copy collapse on low-resource languages (Gemma, Qwen).** 94% of Gemma's defects are untranslated copies, concentrated in pa/te/mr/ta. Its low-resource defect rate (29.31%) is 17× its high-resource rate (1.76%). Qwen shows the same pattern more mildly (7.44% vs 1.84%).
- **Encoding corruption (Qwen only).** 1,343 Qwen strings contain U+FFFD, a byte-level tokenization failure that no other model shows at scale.
- **Residual copy fallback (GPT-4o-mini).** 93% of its few defects are copies, mostly of CamelCase code identifiers (e.g. `KDevStructureTree`) that sit on the boundary of the NTT definition. Some of these may be acceptable [PENDING-MANUAL].

[PENDING-NMT: NMT taxonomy. Track 1 should be expected to show a different profile, e.g. omitted rather than invented placeholders.]

### 4.3 RQ2: Translation quality (CometKiwi)

**Table 3. Mean CometKiwi (wmt22-cometkiwi-da).** Source: `results/master_table_by_system.csv`.

| System | All langs | High-res. | Low-res. |
|---|---:|---:|---:|
| IndicTrans2 (6 Indic) | 0.7979 | – | 0.7979 |
| Google Translate | 0.7939 | 0.7902 | 0.7966 |
| Microsoft Translator | 0.7894 | 0.7844 | 0.7931 |
| GPT-4o-mini | 0.7877 | 0.7875 | 0.7879 |
| GPT-4o-mini + repair | 0.7877 | 0.7872 | 0.7880 |
| NLLB-200 | 0.7834 | 0.7736 | 0.7903 |
| MADLAD-400 | 0.7703 | 0.7726 | 0.7686 |
| Gemma-2-9B + repair | 0.7653 | 0.7801 | 0.7548 |
| Llama-3.1-8B + repair | 0.7531 | 0.7674 | 0.7429 |
| Llama-3.1-8B | 0.7483 | 0.7640 | 0.7371 |
| Gemma-2-9B | 0.7395 | 0.7774 | 0.7124 |
| Mistral-Nemo-12B + repair | 0.7136 | 0.7415 | 0.6937 |
| Qwen-2.5-7B + repair | 0.7069 | 0.7701 | 0.6617 |
| Qwen-2.5-7B | 0.7046 | 0.7688 | 0.6588 |
| Mistral-Nemo-12B | 0.6872 | 0.7098 | 0.6710 |

Paired over languages (`results/stats_cometkiwi_pairwise.csv`, 55 tests, 28 robust):

- **GPT-4o-mini matches the NMT engines.** Against Google it is −0.0062 [−0.0109, −0.0023], Holm p = 0.066, not significant. Against Microsoft it is −0.0017, against NLLB-200 +0.0044 and against IndicTrans2 −0.0047, none significant. It is **significantly better than MADLAD-400** (+0.0175 [0.0124, 0.0233], higher in 12 of 12 languages). This holds both before and after repair.
- **Open 7–12B LLMs fall short.** Every baseline and repaired Llama, Mistral-Nemo, Gemma and Qwen suite is significantly below Google and Microsoft, by 0.024 to 0.107 depending on the model. Against MADLAD-400 and NLLB-200 the picture is mixed. Repaired Gemma-2-9B is statistically tied with MADLAD-400 (−0.0049 [−0.0178, 0.0052]), while Mistral-Nemo is significantly below every 12-language NMT system.
- **The gap is largest on low-resource languages.** NMT systems score *higher* on low-resource than on high-resource languages (Google 0.7966 vs 0.7902), whereas every open LLM scores lower (e.g. Qwen 0.6588 vs 0.7688).

### 4.4 RQ3: Effect of compiler-guided repair
Repair reduces defects for every model, and every reduction is robust (`stats_defects_pairwise.csv`, family `baseline_vs_repaired`):

| Model | Baseline → repaired | Relative change | Risk difference [95% CI] |
|---|---|---:|---|
| GPT-4o-mini | 0.95% → 0.22% | −77.2% | 0.74 pp [0.64, 0.83] |
| Llama-3.1-8B | 2.45% → 0.12% | −95.0% | 2.33 pp [2.16, 2.51] |
| Mistral-Nemo-12B | 8.87% → 0.25% | −97.1% | 8.61 pp [8.25, 8.99] |
| Gemma-2-9B | 17.83% → 0.82% | −95.4% | 17.02 pp [16.80, 17.24] |
| Qwen-2.5-7B | 5.11% → 1.54% | −69.9% | 3.57 pp [3.45, 3.69] |

In every model, the number of strings that were clean before repair and flawed after is **zero**: repair never introduced a defect. Invented placeholders fell from 11,932 to 130 (−98.9%). For GPT-4o-mini the reduction is −77.2% over all 12 languages and −91.2% over the nine non-Latin-script languages; both figures describe the same data.

Repair also *raised* CometKiwi for every open model (Llama +0.0048, Mistral-Nemo +0.0264, Gemma +0.0259, Qwen +0.0023; all Holm p = 0.027, robust) and left GPT-4o-mini unchanged (0.0000, p = 0.97). The independent quality model therefore agrees that the repaired strings are better translations, not just strings that pass a regex.

Among repaired suites, Llama-3.1-8B (0.12%) is the safest. Its lead over Mistral-Nemo (−0.13 pp [−0.17, −0.10]) and GPT-4o-mini (−0.10 pp) is robust. Repaired GPT-4o-mini vs Mistral-Nemo is the single non-robust defect comparison: Holm p = 0.034, but the CI [−0.08, 0.01] includes zero. We treat the two as tied.

Repair is cheap. The targeted re-prompts for the four open models took 89 s (Llama), 155 s (Mistral-Nemo), 151 s (Qwen) and 512 s (Gemma) of A100 wall-clock time for 3,008–21,888 flagged strings (`reports/repair_execution_telemetry.jsonl`).

### 4.5 The safety–quality trade-off
Figure 2 places each suite by defect rate and CometKiwi. Repair moves every model left (safer) and, for the open models, up (better quality). GPT-4o-mini + repair is the only LLM in the NMT quality band (0.770–0.798) with a sub-0.3% defect rate. [PENDING-NMT: add NMT points to Figure 2 and state whether any NMT system dominates.]

---

## 5. Discussion

**The prompt can cause the failure.** Most open-model defects are not translation errors. They are placeholders invented because the prompt mentions placeholders. A static "preserve `%s`, `{0}`" rule should be replaced by a per-string list of the placeholders actually present, which is what the repair prompt does.

**Low-resource languages need a safety net.** Gemma and Qwen are competitive on de/fr/es/zh/ja but fall into untranslated copies on Punjabi and Telugu. A pipeline that routes by language, or that always runs the validator, avoids shipping that collapse.

**Validator-in-the-loop as a pipeline stage.** The audit is deterministic and cheap, and repair touches only flagged strings, so the pattern fits a CI/CD gate: translate → validate → repair → re-validate → merge. This connects directly to the Track 3 CI/CD design (Paper 2).

**Choosing an engine.** On current evidence: for quality, GPT-4o-mini is on par with commercial NMT. For open-weights deployment, repaired Gemma-2-9B approaches MADLAD-400 quality, and repaired Llama-3.1-8B gives the lowest defect rate. [PENDING-NMT: final recommendation once NMT defect rates are known.]

---

## 6. Threats to Validity

1. **Circularity of repair.** The repair loop accepts a fix only if it passes the same checks the audit uses, so repaired defect rates are low partly by construction. We mitigate this by (a) reporting the independent CometKiwi change, which rose for every open model, and (b) the manual precision check [PENDING-MANUAL]. Readers should treat the repaired defect rates as "residual defects the loop could not fix", not as an independent measurement.
2. **Unequal treatment.** Only LLMs were repaired. Applying the same validator and an LLM post-editor to NMT output is a natural follow-up. The like-for-like comparison is baseline LLM vs NMT.
3. **Audit precision.** The checks are regex-based. Copy fallback on CamelCase identifiers and script contamination from legitimate Latin product names may be false positives [PENDING-MANUAL].
4. **Quality granularity.** CometKiwi is available only as per-language means, so quality tests have n = 12 (n = 6 for IndicTrans2) and limited power. A single QE model is used, and CometKiwi is not designed to judge format invariants.
5. **Model versions.** The API model is GPT-4o-mini, not GPT-4o. Commercial engines (Google, Microsoft, OpenAI) change server-side; outputs are frozen at their generation dates (3 Sep, 6 Sep and 18 Oct 2026).
6. **Corpus.** KDE strings represent desktop UI. Web, mobile and cloud-console strings may contain different invariant mixes (ICU plural syntax, HTML).

---

## 7. Conclusion

On 10,228 KDE strings in 12 languages, zero-shot LLMs break between 0.95% and 17.83% of software strings, through model-specific failure modes: invented placeholders, low-resource copy collapse and encoding corruption. A compiler-guided self-repair loop removes 69.9–97.1% of those defects without adding new ones and improves CometKiwi for every open model. GPT-4o-mini matches commercial NMT quality, while open 7–12B LLMs still trail commercial NMT on quality, especially in low-resource languages. [PENDING-NMT: the head-to-head safety verdict.] Scripts, results and figures are released for re-running.

---

## Figures (in `paper1_llm_vs_nmt/figures/`)
- **Fig. 1** `fig1_defect_rate_by_system.png`: defect rate per LLM, baseline vs repaired.
- **Fig. 2** `fig2_quality_vs_defects.png`: CometKiwi vs defect rate; NMT shown as CometKiwi reference lines until defect data exist.
- **Fig. 3** `fig3_defect_heatmap_by_lang.png`: defect rate by system × language.
- **Fig. 4** `fig4_defect_taxonomy.png`: defect-type mix per system.

## Reproduction
```
python paper1_llm_vs_nmt/scripts/audit.py
python paper1_llm_vs_nmt/scripts/build_master_table.py
python paper1_llm_vs_nmt/scripts/stats.py
python paper1_llm_vs_nmt/scripts/generate_figures.py
```

## References
[CITE] To be compiled. Known items: Rei et al. 2022 (CometKiwi); NLLB Team 2022; Kudugunta et al. 2023 (MADLAD-400); Gala et al. 2023 (IndicTrans2); McNemar 1947; Holm 1979; Koehn 2004 (bootstrap for MT); Tiedemann 2012 (OPUS); Track 1 NMT paper (Sharma, Panda, Neti).
