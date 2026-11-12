# LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?

> **DRAFT v0.2 (2026-11-12).** Every number in this draft comes from a file in `paper1_llm_vs_nmt/results/`.
> v0.2 change: the accelerator check now recognises the corpus's `& File` notation (785 source strings). v0.1 checked only 1 of them, so every defect number changed.
> Markers:
> - **[PENDING-NMT]**: needs the Track 1 NMT translation files (`cloud-native-nmt-benchmark-main/data/*.txt` are currently 0-byte). Re-run `audit.py → build_master_table.py → stats.py → generate_figures.py` and fill in.
> - **[AUTHORS]**: author list and affiliations, to be confirmed by the team.
> - Manual-check grades are model-assisted (`model_verdict`). A human spot-check goes in the `my_verdict` column.

**Authors:** [AUTHORS]

---

## Abstract

Cloud-native delivery pipelines increasingly push machine translations of user-interface (UI) strings straight into production builds. A translation that reads well can still break software: a dropped `%1` placeholder crashes a format call, a lost `&` removes a keyboard shortcut, and stray characters from another script or a `�` replacement character corrupt the screen. Standard translation metrics do not see these failures. We compare five large language models (GPT-4o-mini, Llama-3.1-8B, Mistral-Nemo-12B, Gemma-2-9B, Qwen-2.5-7B) with five neural machine translation (NMT) systems (Google Translate, Microsoft Translator, NLLB-200, MADLAD-400, IndicTrans2) on 10,228 KDE software strings in twelve languages. We use a deterministic seven-check invariant audit (91% precision on a validation sample) together with reference-free CometKiwi quality estimation. Zero-shot LLMs break between 2.53% (GPT-4o-mini) and 21.92% (Gemma-2-9B) of strings. Each model fails in its own way: Llama and Mistral-Nemo drop about 70% of keyboard accelerators, Mistral-Nemo invents placeholders in 8% of all strings, and Gemma collapses into untranslated copies on Punjabi and Telugu. A compiler-guided self-repair loop removes 29–77% of defects and never turns a clean string into a flawed one. However, it fixes only what its validator checks, and because the validator did not recognise the corpus's accelerator notation, accelerator losses survive repair almost untouched. On quality, GPT-4o-mini is statistically indistinguishable from Google Translate, Microsoft Translator, NLLB-200 and IndicTrans2, and significantly better than MADLAD-400. The four open 7–12B models remain significantly below the commercial NMT engines even after repair. [PENDING-NMT: one sentence comparing NMT defect rates.] We release the audit, statistics and figures as re-runnable scripts.

**Keywords:** software localization, large language models, neural machine translation, quality estimation, CometKiwi, continuous localization, cloud-native CI/CD

---

## 1. Introduction

Software localization has moved from batch hand-offs to continuous localization. New UI strings are machine-translated and merged within the same CI/CD cycle that ships the code [5, 6, 7, 15]. In this setting there is often no human reviewer between the translation engine and the build, so a translation must be correct as software, not only as language.

Software strings carry *runtime invariants* that ordinary text does not. These include format placeholders (`%1`, `%d`, `{name}`) that the program fills at run time, keyboard accelerators (`&File`), the target script, valid UTF-8, and the requirement that a string actually be translated rather than echoed. Breaking any of these causes a visible bug or a crash, even when a quality metric scores the sentence highly. Koneru et al. [9] identify such software-specific problems for NMT. Reference-based metrics (BLEU [20], COMET [25]) and quality-estimation models (CometKiwi [28]) are built to judge meaning and fluency. They are not built to check whether `%1` survived.

Two kinds of engine now compete for this job. Classic encoder-decoder NMT systems (commercial APIs and open models such as NLLB-200 [17], MADLAD-400 [31] and IndicTrans2 [30]) are fast and predictable. Instruction-tuned LLMs translate competitively in high-resource languages [32, 33, 34], follow format rules written in a prompt, and can be asked to correct themselves [36, 37]. But they also hallucinate and degrade on low-resource languages [35]. Deployment teams need evidence on both safety and quality to choose between them.

We ask:

- **RQ1 (safety).** Which paradigm breaks fewer software strings, and which invariants does each break?
- **RQ2 (quality).** How does reference-free translation quality (CometKiwi) compare between LLMs and NMT?
- **RQ3 (repair).** Does compiler-guided self-repair change the safety–quality trade-off for LLMs?

**Contributions.**
1. A deterministic, re-runnable seven-check invariant audit for software UI translations, with an allowlist for legitimate non-translatable tokens (NTTs) and a measured precision of 91%, applied to 1,227,360 LLM translations [PENDING-NMT: + NMT count].
2. A controlled comparison of 5 LLMs and 5 NMT systems on the same 10,228 source strings in 12 languages, using the same CometKiwi checkpoint for both.
3. A failure taxonomy showing that LLM defects are model-specific: accelerator loss, prompt-induced placeholder invention (11,932 strings), low-resource copy collapse and byte-level encoding corruption.
4. Evidence that validator-in-the-loop self-repair removes the defects its validator checks (and never adds new flawed strings), but silently passes the ones it does not check. This makes the validator's coverage, not the LLM, the limiting factor.

---

## 2. Related Work

**Software and continuous localization.** Localization has evolved from Waterfall processes [11, 12], through Agile approaches that place localization inside sprint cycles [13, 14], to continuous localization integrated with CI/CD pipelines [5, 6]. More recently it has been extended to cloud-native and serverless delivery [7, 15]. As release cycles shrink from weeks to hours [15, 16], automated checks become the only quality gate many strings pass through.

**MT for software content.** Transformer NMT [8] and massively multilingual models such as NLLB-200 [17], MADLAD-400 [31] and IndicTrans2 [30] cover hundreds of languages. For software specifically, Wang et al. [18] trained domain-specific models, Muntés-Mulero et al. [10] showed that code context improves software translation, and Koneru et al. [9] catalogued NMT failure modes for software localization: terminology, fragmentation and missing context. Our audit targets a complementary class of failures, the runtime invariants, that these studies do not measure.

**LLMs as translators.** Zhang et al. [32] showed that prompt design strongly affects LLM translation and reported copying and hallucination errors. Hendy et al. [33] found GPT models competitive for high-resource languages but weaker for low-resource ones. WMT23 [34] confirmed that LLMs are strong but not yet dominant. Robinson et al. [35] found traditional MT ahead on 84% of 203 languages, with resource level as the strongest predictor of LLM quality. Our results reproduce this resource gap on software strings and show it as invariant failures, not only as lower scores.

**Quality estimation.** CometKiwi [28] predicts quality from source and hypothesis alone, which makes it suitable when references are absent or are themselves machine output. It ranked first at the WMT22 QE task [27, 28]. Its training objective rewards adequacy and fluency, not format invariants, which motivates our separate audit.

**Self-correction with external feedback.** Self-Refine [36] lets an LLM critique and revise its own output. CRITIC [37] shows that correction is reliable mainly when the critique comes from an external tool, and that pure self-correction can even hurt. Our repair loop follows the CRITIC pattern: a deterministic validator is the critic and the acceptance gate. We show the flip side: the loop is only as complete as its validator.

---

## 3. Experimental Setup

### 3.1 Corpus and languages
We use a fixed set of **10,228 English UI strings** from the KDE desktop environment, taken from OPUS KDE4 [29]. The source file has SHA-256 `464d6582…fe281f` and is identical in both team repositories. Targets are **12 languages**: five high-resource (de, fr, es, zh, ja) and seven low-resource (hi, ar, bn, mr, pa, ta, te), following the Track 1 study. Every system translates the same source lines, so every comparison is paired at the string level. Of the source strings, 785 contain a keyboard accelerator (written `& File` in this tokenized corpus), and 356 contain format placeholders.

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

Note: the LLM repository labels the API model `gpt4o`, but its run log (`findings/experiment_runs.json`) records `gpt-4o-mini`. We report it as GPT-4o-mini throughout.

All LLMs share one zero-shot system prompt (`prompts/system_zero_shot.txt`). It asks for a single-line translation and to "preserve all placeholders, format specifiers, and variables (e.g., {0}, {name}, %s, %d, …) exactly as written". It does not mention keyboard accelerators. Open-weights models ran on an NVIDIA A100-SXM4-80GB. NMT configurations are those of the Track 1 study.

### 3.3 Invariant audit
Every output line is checked against its source line for seven defect types (`scripts/audit.py`):

1. **Broken placeholder.** The multiset of `%N`, `%x` and `{…}` tokens differs between source and output (omitted, invented or altered).
2. **Broken accelerator.** The source has an `&` accelerator and the output has none. XML entities such as `&kexi;` and `&amp;` are removed before checking. An optional space after `&` is allowed, because KDE4 in OPUS is tokenized as `& File`.
3. **Script contamination.** The output contains characters from a Unicode block foreign to the target language (e.g. CJK or Cyrillic in Hindi).
4. **Encoding corruption.** The output contains U+FFFD.
5. **Conversational chatter.** The output starts with phrases such as "Here is the translation" or "Note:".
6. **Copy fallback.** The output equals the source (longer than 3 characters, containing letters) and the source is not a legitimate NTT.
7. **Empty output.** The output is empty while the source is not.

The **NTT allowlist** exempts strings that should stay untranslated: hardware and protocol acronyms (USB, SCSI, IPv6, …), spreadsheet formulas (`BIN2OCT(value)`), POSIX format descriptors, XML entities, X11 colour names, short upper-case identifiers, time-zone paths, and single-word Western-European cognates for de/es/fr. A string counts as *flawed* if it has at least one defect. Defect rate = flawed strings / audited strings.

**Audit validation.** We drew a stratified sample of 100 flagged and 50 unflagged strings (seed 42; `results/manual_check_sample.csv`) and graded each one as a true or false defect. **Precision was 91% (91/100).** It was 100% (28/28) for placeholder, encoding and script flags and 87.5% (63/72) for copy fallback. All nine false positives were copy-fallback flags on strings that may legitimately stay in English: five person names (e.g. *Matthias Ettrich*), two code identifiers (`massVariance`, `ImagePlugin_ChannelMixer`), the directory name `lost+found`, and one French cognate (`(%1 occurrences)`). Among the 50 unflagged strings we found **one miss (2%)**: GPT-4o-mini translated the accelerator in `& Outline` as the Bengali word for "and". That miss exposed the accelerator bug described in §6, and the audit was fixed before the results below were produced. The grades were model-assisted. A human spot-check of the same rows is recorded in the `my_verdict` column.

### 3.4 Compiler-guided self-repair (LLMs only)
For each baseline LLM, every string flagged by the LLM repository's validator goes back to **the same model** with a targeted system prompt (`scripts/run_agentic_repair.py`). The prompt contains only the rules matching the detected defects: the exact placeholder list (or, when the model invented placeholders, an instruction to add no variables), the accelerator rule, a script-purity rule naming the target script, or a "do not return the source unchanged" rule with a de-camel-cased meaning hint. Decoding is greedy (T = 0). The candidate is re-validated, and it **replaces the original only if it passes every check**. Otherwise the original line is kept. Unflagged strings are never touched.

That validator used the original accelerator pattern, `&[^\s\d_;]`, which matches only 1 of the 785 accelerator strings in this corpus. As a result, the repair loop almost never saw or fixed an accelerator defect. We keep the repaired outputs as they were produced and audit them with the corrected check.

### 3.5 Quality estimation
Both tracks scored every output with the same reference-free model, **CometKiwi `Unbabel/wmt22-cometkiwi-da`** [28]. This makes LLM and NMT scores directly comparable. Only per-(system, language) means are available, so quality comparisons are paired at the language level. Reference-based metrics from the Track 1 study (BLEU, COMET, etc.) use Google Translate output as the reference. They therefore measure agreement with Google rather than quality, and we do not use them here.

### 3.6 Statistical analysis
All tests are paired, with 10,000 bootstrap resamples and seed 42 (`scripts/stats.py`).

- **Defects (string level).** The unit is a (language, source line) pair; n = 122,736 per LLM. We report the risk difference in percentage points with a 95% **cluster-bootstrap** CI that resamples whole source strings, so the 12 translations of one string stay together [38]. We also report a **McNemar** test [39] on discordant pairs (exact binomial when b + c < 25, otherwise χ² with continuity correction) and the paired odds ratio.
- **CometKiwi (language level).** The unit is a language; n = 12, or 6 for IndicTrans2. We report the mean difference with a 95% bootstrap CI over languages, an **exact Wilcoxon signed-rank** test [41], and Cohen's d_z.
- **Multiplicity.** **Holm–Bonferroni** correction [40] within each family (25 defect tests; 55 CometKiwi tests). We call a result *robust* when it is Holm-significant **and** its bootstrap CI excludes zero.

With 12 languages, the smallest attainable exact Wilcoxon p is 0.00049. With 6 languages it is 0.031, so no IndicTrans2 comparison can survive Holm correction. We flag this rather than hide it.

---

## 4. Results

### 4.1 RQ1: How often does each system break strings?

**Table 2. Invariant defects per system (12 languages × 10,228 strings).** Source: `results/master_table_by_system.csv`.

| System | Flawed | Defect rate | High-res. | Low-res. | Accelerator | Copy fallback | Placeholder | Script | Encoding |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-4o-mini | 3,104 | 2.53% | 2.30% | 2.69% | 1,939 | 1,083 | 5 | 81 | 0 |
| Qwen-2.5-7B | 7,340 | 5.98% | 2.51% | 8.46% | 1,106 | 3,933 | 691 | 328 | 1,343 |
| Llama-3.1-8B | 9,749 | 7.94% | 6.82% | 8.75% | 6,791 | 1,299 | 1,692 | 0 | 10 |
| Mistral-Nemo-12B | 17,302 | 14.10% | 15.95% | 12.77% | 6,518 | 718 | 10,148 | 0 | 10 |
| Gemma-2-9B | 26,899 | 21.92% | 5.80% | 33.43% | 5,076 | 20,611 | 43 | 1,226 | 0 |
| GPT-4o-mini + repair | 2,206 | 1.80% | 1.45% | 2.04% | 1,940 | 232 | 4 | 31 | 0 |
| Qwen-2.5-7B + repair | 2,996 | 2.44% | 1.00% | 3.47% | 1,124 | 1,167 | 52 | 136 | 541 |
| Gemma-2-9B + repair | 6,178 | 5.03% | 4.41% | 5.48% | 5,181 | 885 | 1 | 109 | 0 |
| Mistral-Nemo-12B + repair | 6,823 | 5.56% | 6.28% | 5.04% | 6,524 | 161 | 141 | 0 | 1 |
| Llama-3.1-8B + repair | 6,945 | 5.66% | 4.75% | 6.30% | 6,812 | 89 | 52 | 0 | 1 |
| Google Translate | [PENDING-NMT] | | | | | | | | |
| Microsoft Translator | [PENDING-NMT] | | | | | | | | |
| NLLB-200 | [PENDING-NMT] | | | | | | | | |
| MADLAD-400 | [PENDING-NMT] | | | | | | | | |
| IndicTrans2 (6 langs) | [PENDING-NMT] | | | | | | | | |

Chatter and empty-output defects are rare (≤ 7 per suite) and are omitted from the table; full counts are in the CSV.

Among zero-shot LLMs the safety ranking is GPT-4o-mini (2.53%) < Qwen (5.98%) < Llama (7.94%) < Mistral-Nemo (14.10%) < Gemma (21.92%). Every pairwise difference between baseline LLMs is robust (`results/stats_defects_pairwise.csv`, family `baseline_pairwise`). For example, GPT-4o-mini vs Qwen is −3.45 pp [−3.65, −3.25] and Llama vs Mistral-Nemo is −6.15 pp [−6.55, −5.76]. Figure 3 shows where the defects concentrate. Gemma breaks 77.9% of Punjabi and 75.7% of Telugu strings. Mistral-Nemo is poor everywhere (5.7–12.4% in every language, before counting accelerators).

[PENDING-NMT: NMT defect rates, the LLM-vs-NMT comparison (family `llm_vs_nmt`, generated automatically once the files exist), and the answer to RQ1. The fair comparison is **baseline LLM vs NMT**, since neither had any post-processing.]

### 4.2 Failure taxonomy
Figure 4 shows that each model fails in its own way:

- **Accelerator loss (all models, worst for Llama and Mistral-Nemo).** Of the 9,420 accelerator strings (785 × 12 languages), Llama drops the accelerator in 72.1%, Mistral-Nemo in 69.2%, Gemma in 53.9%, GPT-4o-mini in 20.6% and Qwen in 11.7%. Typical failures are dropping `&` silently, translating it as the word "and" (*Start & time* → 開始と時間), escaping it to `&amp;`, or moving it to the end of the string where it marks no letter (背景颜色:&). GPT-4o-mini's losses concentrate in Bengali (658 of 785 strings). The zero-shot prompt never mentions accelerators, so these losses show what models do with `&` when they are not told.
- **Invented placeholders (Mistral-Nemo, Llama).** 97% of Mistral-Nemo's placeholder errors and 90% of Llama's are placeholders *added* to strings that had none: 9,820 of 10,148 and 1,529 of 1,692 (`reports/placeholder_error_decomposition.csv`). Across the open models, 11,932 strings received an invented placeholder. Because the system prompt lists example specifiers (`{0}`, `%s`, `%d`), we read this as **prompt-induced**: a rule meant to protect placeholders leads smaller models to insert them.
- **Copy collapse on low-resource languages (Gemma, Qwen).** 20,611 of Gemma's defects are untranslated copies, concentrated in pa/te/mr/ta. Its low-resource defect rate (33.43%) is 5.8× its high-resource rate (5.80%). Qwen shows the same pattern more mildly (8.46% vs 2.51%).
- **Encoding corruption (Qwen only).** 1,343 Qwen strings contain U+FFFD, often next to stray CJK or Cyrillic fragments (ਦੋ�cuメント). This is a byte-level tokenization failure that no other model shows at scale.

[PENDING-NMT: NMT taxonomy, e.g. whether NMT systems also drop or mistranslate `&`, and whether they omit rather than invent placeholders.]

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
- **The gap is largest on low-resource languages.** NMT systems score *higher* on low-resource than on high-resource languages (Google 0.7966 vs 0.7902), whereas every open LLM scores lower (e.g. Qwen 0.6588 vs 0.7688). This matches the resource effect reported by Robinson et al. [35].

### 4.4 RQ3: Effect of compiler-guided repair
Repair reduces defects for every model, and every reduction is robust (`stats_defects_pairwise.csv`, family `baseline_vs_repaired`):

| Model | Baseline → repaired | Relative change | Risk difference [95% CI] |
|---|---|---:|---|
| GPT-4o-mini | 2.53% → 1.80% | −28.9% | 0.73 pp [0.64, 0.83] |
| Llama-3.1-8B | 7.94% → 5.66% | −28.8% | 2.29 pp [2.11, 2.47] |
| Mistral-Nemo-12B | 14.10% → 5.56% | −60.6% | 8.54 pp [8.17, 8.92] |
| Gemma-2-9B | 21.92% → 5.03% | −77.0% | 16.88 pp [16.66, 17.10] |
| Qwen-2.5-7B | 5.98% → 2.44% | −59.2% | 3.54 pp [3.42, 3.67] |

**Repair fixes what its validator checks.** For the defect types the repair validator detected (placeholders, copy fallback, script, encoding, chatter), residual counts fall sharply. Invented placeholders drop from 11,932 to 130 (−98.9%), and Gemma's copy fallbacks drop from 20,611 to 885. No string that was clean before repair is flawed after it: the clean→flawed count is 0 in every model.

**Repair does not fix what its validator misses.** Accelerator losses are essentially unchanged: Llama 6,791 → 6,812, Mistral-Nemo 6,518 → 6,524, Gemma 5,076 → 5,181, GPT-4o-mini 1,939 → 1,940. After repair, accelerators account for 84–98% of all remaining defects in GPT-4o-mini, Llama, Mistral-Nemo and Gemma (Figure 4). The small *increases* (e.g. +105 for Gemma) come from strings that were re-translated to fix another defect and lost their `&` in the process. Those strings were already flawed, so they do not count as clean→flawed. As a result, the repaired ranking differs from the baseline ranking. GPT-4o-mini (1.80%) and Qwen (2.44%), which drop few accelerators, become the safest. Llama (5.66%) and Mistral-Nemo (5.56%) are tied (difference 0.10 pp [−0.03, 0.24], not significant).

Repair also *raised* CometKiwi for every open model (Llama +0.0048, Mistral-Nemo +0.0264, Gemma +0.0259, Qwen +0.0023; all Holm p = 0.027, robust) and left GPT-4o-mini unchanged (0.0000, p = 0.97). The independent quality model therefore agrees that the repaired strings are better translations, not just strings that pass a regex.

Repair is cheap. The targeted re-prompts for the four open models took 89 s (Llama), 155 s (Mistral-Nemo), 151 s (Qwen) and 512 s (Gemma) of A100 wall-clock time for 3,008–21,888 flagged strings (`reports/repair_execution_telemetry.jsonl`). Re-running the loop with the corrected accelerator check is the obvious next step (§6).

### 4.5 The safety–quality trade-off
Figure 2 places each suite by defect rate and CometKiwi. Repair moves every model left (safer) and, for the open models, up (better quality). GPT-4o-mini + repair is the only LLM inside the NMT quality band (0.770–0.798), and it is also the safest LLM suite (1.80%). [PENDING-NMT: add NMT points to Figure 2 and state whether any NMT system dominates.]

---

## 5. Discussion

**The validator is the product.** The repair loop removed nearly every defect it could see and none it could not. One regex that did not match the corpus's `& File` notation left 6,800 accelerator losses per open model in place after repair. For CI/CD use, validator coverage must be tested against the real string format of each project, for example with seeded test strings for every invariant type, before the loop is trusted.

**The prompt can cause the failure, and silence can too.** Placeholders were invented because the prompt mentions placeholders; accelerators were dropped because it does not mention them. A static rule list should be replaced by per-string constraints that name exactly the placeholders and accelerators present, which is what the repair prompt does for the defects it detects.

**Low-resource languages need a safety net.** Gemma and Qwen are competitive on de/fr/es/zh/ja but fall into untranslated copies on Punjabi and Telugu. A pipeline that routes by language, or that always runs the validator, avoids shipping that collapse.

**Validator-in-the-loop as a pipeline stage.** The audit is deterministic and cheap, and repair touches only flagged strings, so the pattern fits a CI/CD gate: translate → validate → repair → re-validate → merge. This connects directly to the Track 3 CI/CD design (Paper 2) [7].

**Choosing an engine.** On current evidence, GPT-4o-mini offers commercial-NMT quality with the lowest LLM defect rate. Among open models, repaired Gemma-2-9B approaches MADLAD-400 quality but needs accelerator handling. [PENDING-NMT: final recommendation once NMT defect rates are known.]

---

## 6. Threats to Validity

1. **Repair validator coverage and circularity.** The repair loop accepts a fix only if it passes its own validator. Defects of the types it checks are therefore low after repair partly by construction. The independent CometKiwi gain supports a real improvement. Conversely, the validator's accelerator pattern (`&[^\s\d_;]`) matched 1 of 785 accelerator strings, so accelerator defects were never repaired. Our audit uses a corrected pattern (`&\s?[^\s\d_;&]`); the defect counts in the LLM repository's README use the original one and are lower for that reason.
2. **Unequal treatment.** Only LLMs were repaired. Applying the same validator and an LLM post-editor to NMT output is a natural follow-up. The like-for-like comparison is baseline LLM vs NMT.
3. **Audit precision.** The audit is 91% precise on a 100-string sample. Its false positives are copy-fallback flags on names, identifiers and cognates, so copy-fallback counts are slight over-estimates. Grades were model-assisted with a human spot-check.
4. **Quality granularity.** CometKiwi is available only as per-language means, so quality tests have n = 12 (n = 6 for IndicTrans2) and limited power. A single QE model is used, and CometKiwi is not designed to judge format invariants.
5. **Model versions.** The API model is GPT-4o-mini, not GPT-4o. Commercial engines (Google, Microsoft, OpenAI) change server-side; outputs are frozen at their generation dates (3 Sep, 6 Sep and 18 Oct 2026).
6. **Corpus.** KDE strings represent desktop UI, and the OPUS tokenization (`& File`, `& kexi;`) differs from raw `.po` files. A few source lines are corpus artifacts (hundreds of strings merged into one line). Web, mobile and cloud-console strings may contain different invariant mixes (ICU plural syntax, HTML).

---

## 7. Conclusion

On 10,228 KDE strings in 12 languages, zero-shot LLMs break between 2.53% and 21.92% of software strings, through model-specific failure modes: accelerator loss, invented placeholders, low-resource copy collapse and encoding corruption. A compiler-guided self-repair loop removes 29–77% of those defects, adds no new flawed strings and improves CometKiwi for every open model. But it leaves untouched every defect type its validator does not recognise. GPT-4o-mini matches commercial NMT quality, while open 7–12B LLMs still trail commercial NMT on quality, especially in low-resource languages. [PENDING-NMT: the head-to-head safety verdict.] Scripts, results and figures are released for re-running.

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

---

## References

[1]–[30] are taken from the Track 1 NMT paper (`cloud-native-nmt-benchmark-main/main.tex`); [31]–[41] were added for this paper and checked against their publisher pages.

1. Marcus A, Gould EW. Globalization, localization, and cross-cultural user-interface design. In: Jacko JA (ed.) *The Human-Computer Interaction Handbook*, 3rd edn. CRC Press, 2012, pp. 341–366.
2. Chroust G. Software like a courteous butler: localization under cultural diversity. In: *ISSS 2007*.
3. Banes D, Draffan EA. A guide to localising assistive technologies. In: *ATIA 2013*. Orlando, FL, 2013.
4. Aqle A, Al-Masri A, Nasser Y. Exploring current accessibility challenges in the multilingual web for visually-impaired users. In: *WWW 2015 Companion*. ACM, 2015, pp. 871–872.
5. Shahin M, Babar MA, Zhu L. Continuous integration, delivery, and deployment: a systematic review. *IEEE Access* 2017; 5: 3909–3943.
6. Stahl D, Martensson T, Bosch J. Continuous practices and DevOps. In: *SEAA 2017*. IEEE, 2017, pp. 440–448.
7. Sharma NK, Mate PD, Pandit SK, Kar P, Panda S, Neti LBM. Cloud-Native Scalable Localization: A Serverless CI/CD Framework for Multilingual Software Delivery. In: *IEEE COMPSAC 2026*. Madrid, Spain, 2026, pp. 462–467.
8. Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. *NeurIPS* 2017; 30: 5998–6008.
9. Koneru S, Huck M, Exel M, et al. Analyzing challenges in NMT for software localization. In: *EACL 2023*, pp. 2442–2454.
10. Muntés Mulero V, Paladini Adell P, España Bonet C, et al. Context-aware MT for software localization. In: *EAMT 2012*, pp. 77–80.
11. Hau E, Aparicio M. Software internationalization and localization in web-based ERP. In: *SIGDOC 2008*. ACM, 2008, pp. 175–180.
12. Giammarresi S. Strategic views on localization project management. In: Dunne KJ, Dunne ES (eds) *Translation and Localization Project Management*. John Benjamins, 2011, pp. 17–50.
13. Kabát M. Possible translation problems in agile localization of software. *Int J Interact Mob Technol* 2023; 17(1).
14. Lee S, Yong HS. Distributed agile: project management in a global environment. *Empir Softw Eng* 2010; 15: 204–217.
15. Bolaños García-Escribano A. Cloud technologies in media localisation. In: *New Advances in Translation Technology*. Springer, 2024, pp. 55–78.
16. Gonçalves L. *Process Improvement for Software Localization* [Master's thesis]. Helsinki Metropolia University of Applied Sciences, 2011.
17. Costa-jussà MR, Cross J, Çelebi O, et al. No language left behind: scaling human-centered machine translation. *Nature* 2024; 630: 841–846.
18. Wang X, Chen C, Xing Z. Domain-specific machine translation with recurrent neural network for software localization. *Empir Softw Eng* 2019; 24(6): 3514–3545.
19. Smirnov AV, Teslya N, Shilov N, et al. Comparative analysis of neural translation models based on Transformers. In: *ICEIS (1)*, 2022, pp. 586–593.
20. Papineni K, Roukos S, Ward T, et al. BLEU: a method for automatic evaluation of machine translation. In: *ACL 2002*, pp. 311–318.
21. Banerjee S, Lavie A. METEOR: an automatic metric for MT evaluation with improved correlation with human judgments. In: *ACL Workshop on Intrinsic and Extrinsic Evaluation Measures*, 2005, pp. 65–72.
22. Popović M. chrF: character n-gram F-score for automatic MT evaluation. In: *WMT 2015*, pp. 392–395.
23. Lin CY. ROUGE: a package for automatic evaluation of summaries. In: *Text Summarization Branches Out*, 2004, pp. 74–81.
24. Snover M, Dorr B, Schwartz R, et al. A study of translation edit rate with targeted human annotation. In: *AMTA 2006*, pp. 223–231.
25. Rei R, Stewart C, Farinha AC, et al. COMET: a neural framework for MT evaluation. In: *EMNLP 2020*, pp. 2685–2702.
26. Zhang T, Kishore V, Wu F, et al. BERTScore: evaluating text generation with BERT. In: *ICLR 2020*.
27. Freitag M, Rei R, Mathur N, et al. Results of the WMT22 metrics shared task. In: *WMT 2022*, pp. 46–68.
28. Rei R, Treviso M, Guerreiro NM, et al. CometKiwi: IST-Unbabel 2022 submission for the quality estimation shared task. In: *WMT 2022*, pp. 634–645.
29. Tiedemann J. Parallel data, tools and interfaces in OPUS. In: *LREC 2012*. Istanbul, 2012, pp. 2214–2218.
30. Gala J, Chitale PA, Raghavan AK, et al. IndicTrans2: towards high-quality and accessible machine translation models for all 22 scheduled Indian languages. *Transactions on Machine Learning Research* 2023.
31. Kudugunta S, Caswell I, Zhang B, et al. MADLAD-400: a multilingual and document-level large audited dataset. In: *NeurIPS 2023 Datasets and Benchmarks Track*, 2023.
32. Zhang B, Haddow B, Birch A. Prompting large language model for machine translation: a case study. In: *ICML 2023*.
33. Hendy A, Abdelrehim M, Sharaf A, et al. How good are GPT models at machine translation? A comprehensive evaluation. *arXiv:2302.09210*, 2023.
34. Kocmi T, Avramidis E, Bawden R, et al. Findings of the 2023 Conference on Machine Translation (WMT23): LLMs are here but not quite there yet. In: *WMT 2023*, pp. 1–42.
35. Robinson NR, Ogayo P, Mortensen DR, Neubig G. ChatGPT MT: competitive for high- (but not low-) resource languages. In: *WMT 2023*, pp. 392–418.
36. Madaan A, Tandon N, Gupta P, et al. Self-Refine: iterative refinement with self-feedback. In: *NeurIPS 2023*.
37. Gou Z, Shao Z, Gong Y, et al. CRITIC: large language models can self-correct with tool-interactive critiquing. In: *ICLR 2024*.
38. Koehn P. Statistical significance tests for machine translation evaluation. In: *EMNLP 2004*, pp. 388–395.
39. McNemar Q. Note on the sampling error of the difference between correlated proportions or percentages. *Psychometrika* 1947; 12(2): 153–157.
40. Holm S. A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics* 1979; 6(2): 65–70.
41. Wilcoxon F. Individual comparisons by ranking methods. *Biometrics Bulletin* 1945; 1(6): 80–83.
