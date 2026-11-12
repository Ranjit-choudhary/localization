# LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?

> **DRAFT v0.3 (2026-11-12).** Complete draft: every number comes from a file in `paper1_llm_vs_nmt/results/`.
> - v0.3: NMT translation files from Track 1 (`nmt-benchmarking-paper-main/data/`) added; all NMT results filled in, and the audit was validated on NMT output as well.
> - v0.2: the accelerator check now recognises the corpus's `& File` notation.
> - Remaining for the team: **[AUTHORS]**, plus an optional human spot-check of the validation samples (`my_verdict` column).

**Authors:** [AUTHORS]

---

## Abstract

Cloud-native delivery pipelines increasingly push machine translations of user-interface (UI) strings straight into production builds. A translation that reads well can still break software: a dropped `%1` placeholder crashes a format call, a lost `&` removes a keyboard shortcut, and stray characters from another script or a `�` replacement character corrupt the screen. Standard translation metrics do not see these failures.

We compare five large language models (GPT-4o-mini, Llama-3.1-8B, Mistral-Nemo-12B, Gemma-2-9B, Qwen-2.5-7B) with five neural machine translation (NMT) systems (Google Translate, Microsoft Translator, NLLB-200, MADLAD-400, IndicTrans2) on 10,228 KDE software strings in twelve languages. We use a deterministic seven-check invariant audit (92% precision on 150 validated flags) together with reference-free CometKiwi quality estimation.

**Neither paradigm is uniformly safer.** NMT systems break 4.18–9.06% of strings, while zero-shot LLMs range from 2.53% (GPT-4o-mini, safer than every NMT system) to 21.92% (Gemma-2-9B, worse than every NMT system). The two families fail differently. NMT systems drop 30–69% of keyboard accelerators and mangle existing placeholders (`%1` → `1%`, `% 1`), but they never invent placeholders. Open LLMs invent placeholders the source never had (11,932 strings) and collapse into untranslated copies on low-resource languages. A compiler-guided self-repair loop cuts LLM defects by 29–77%, so that every repaired LLM is safer than Google Translate, Microsoft Translator, MADLAD-400 and IndicTrans2. The loop fixes only what its validator checks, however.

On quality, GPT-4o-mini is statistically indistinguishable from Google, Microsoft, NLLB-200 and IndicTrans2 and better than MADLAD-400, while the open 7–12B LLMs trail the commercial engines. GPT-4o-mini with repair is the only system that is both at NMT quality and below 2% defects. We release the audit, statistics and figures as re-runnable scripts.

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
1. A deterministic, re-runnable seven-check invariant audit for software UI translations, with an allowlist for legitimate non-translatable tokens (NTTs). It was validated on both LLM and NMT output (92% precision) and applied to 1,779,672 translations from 15 system suites.
2. A controlled comparison of 5 LLMs and 5 NMT systems on the same 10,228 source strings in 12 languages, using the same CometKiwi checkpoint for both, with paired statistics (cluster bootstrap, McNemar, Wilcoxon, Holm) for every claim.
3. A failure taxonomy showing that the two paradigms break software in different ways. NMT mistranslates or drops accelerators and splits placeholders. Open LLMs invent placeholders and copy the source on low-resource languages.
4. Evidence that validator-in-the-loop self-repair moves every LLM below most NMT systems in defect rate and never adds new flawed strings, but silently passes defect types its validator does not recognise.

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
We use a fixed set of **10,228 English UI strings** from the KDE desktop environment, taken from OPUS KDE4 [29]. The source file has SHA-256 `464d6582…fe281f` and is identical in the LLM and NMT repositories. All 55 NMT files pass the Track 1 checksum manifest. Targets are **12 languages**: five high-resource (de, fr, es, zh, ja) and seven low-resource (hi, ar, bn, mr, pa, ta, te). IndicTrans2 covers only the six Indic languages. Every system translates the same source lines, so every comparison is paired at the string level. Of the source strings, 785 contain a keyboard accelerator (written `& File` in this tokenized corpus) and 356 contain format placeholders.

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
| NMT (open) | IndicTrans2 | `ai4bharat/indictrans2-en-indic-1B`, greedy, IndicProcessor | 6 (Indic) |

Note: the LLM repository labels the API model `gpt4o`, but its run log (`findings/experiment_runs.json`) records `gpt-4o-mini`. We report it as GPT-4o-mini throughout.

All LLMs share one zero-shot system prompt (`prompts/system_zero_shot.txt`). It asks for a single-line translation and to "preserve all placeholders, format specifiers, and variables (e.g., {0}, {name}, %s, %d, …) exactly as written". It does not mention keyboard accelerators. Open-weights LLMs ran on an NVIDIA A100-SXM4-80GB. NMT configurations are those of the Track 1 study; the NMT engines received the raw source string with no pre- or post-processing beyond each toolkit's defaults.

### 3.3 Invariant audit
Every output line is checked against its source line for seven defect types (`scripts/audit.py`):

1. **Broken placeholder.** The multiset of `%N`, `%x` and `{…}` tokens differs between source and output (omitted, invented or altered, e.g. `%1` → `1%` or `% 1`).
2. **Broken accelerator.** The source has an `&` accelerator and the output has none. XML entities such as `&kexi;` and `&amp;` are removed before checking. An optional space after `&` is allowed, because KDE4 in OPUS is tokenized as `& File`.
3. **Script contamination.** The output contains characters from a Unicode block foreign to the target language (e.g. CJK or Cyrillic in Hindi).
4. **Encoding corruption.** The output contains U+FFFD.
5. **Conversational chatter.** The output starts with phrases such as "Here is the translation" or "Note:".
6. **Copy fallback.** The output equals the source (longer than 3 characters, containing letters) and the source is not a legitimate NTT.
7. **Empty output.** The output is empty while the source is not.

The **NTT allowlist** exempts strings that should stay untranslated: hardware and protocol acronyms (USB, SCSI, IPv6, …), spreadsheet formulas (`BIN2OCT(value)`), POSIX format descriptors, XML entities, X11 colour names, short upper-case identifiers, time-zone paths, and single-word Western-European cognates for de/es/fr. A string counts as *flawed* if it has at least one defect. Defect rate = flawed strings / audited strings.

**Audit validation.** We drew two stratified samples with seed 42 and graded each flag as a true or false defect:
- **LLM sample** (100 flagged + 50 unflagged; `results/manual_check_sample.csv`): 91% precision (91/100).
- **NMT sample** (50 flagged + 25 unflagged; `results/manual_check_sample_nmt.csv`): 94% precision (47/50).

**Overall precision is 92% (138/150).** It is 100% (70/70) for accelerator, placeholder, encoding and script flags and 85% (68/80) for copy fallback. All 12 false positives are copy-fallback flags on strings that may legitimately stay in English: person names (e.g. *Matthias Ettrich*), code identifiers (`massVariance`), the directory `lost+found`, technical names (*CCITT Modified Huffman RLE*, the MIDI instrument *Lead 3 – Calliope*) and cognates (French `(%1 occurrences)`, German `& Suffix:`). Among the 75 unflagged strings we found one miss: GPT-4o-mini translated the accelerator in `& Outline` as the Bengali word for "and". That miss exposed the accelerator bug described in §6, which was fixed before the results below were produced. The grades were model-assisted; a human spot-check of the same rows is recorded in the `my_verdict` column.

### 3.4 Compiler-guided self-repair (LLMs only)
For each baseline LLM, every string flagged by the LLM repository's validator goes back to **the same model** with a targeted system prompt (`scripts/run_agentic_repair.py`). The prompt contains only the rules matching the detected defects: the exact placeholder list (or, when the model invented placeholders, an instruction to add no variables), the accelerator rule, a script-purity rule naming the target script, or a "do not return the source unchanged" rule with a de-camel-cased meaning hint. Decoding is greedy (T = 0). The candidate is re-validated, and it **replaces the original only if it passes every check**. Otherwise the original line is kept. Unflagged strings are never touched.

That validator used the original accelerator pattern, `&[^\s\d_;]`, which matches only 1 of the 785 accelerator strings in this corpus. As a result, the repair loop almost never saw or fixed an accelerator defect. We keep the repaired outputs as they were produced and audit them with the corrected check.

### 3.5 Quality estimation
Both tracks scored every output with the same reference-free model, **CometKiwi `Unbabel/wmt22-cometkiwi-da`** [28]. This makes LLM and NMT scores directly comparable. Only per-(system, language) means are available, so quality comparisons are paired at the language level. Reference-based metrics from the Track 1 study (BLEU, COMET, etc.) use Google Translate output as the reference. They therefore measure agreement with Google rather than quality, and we do not use them here.

### 3.6 Statistical analysis
All tests are paired, with 10,000 bootstrap resamples and seed 42 (`scripts/stats.py`).

- **Defects (string level).** The unit is a (language, source line) pair; n = 122,736 per 12-language suite and 61,368 for IndicTrans2, which is compared on its six languages only. We report the risk difference in percentage points with a 95% **cluster-bootstrap** CI that resamples whole source strings, so the translations of one string stay together [38]. We also report a **McNemar** test [39] on discordant pairs (exact binomial when b + c < 25, otherwise χ² with continuity correction) and the paired odds ratio.
- **CometKiwi (language level).** The unit is a language; n = 12, or 6 for IndicTrans2. We report the mean difference with a 95% bootstrap CI over languages, an **exact Wilcoxon signed-rank** test [41], and Cohen's d_z.
- **Multiplicity.** **Holm–Bonferroni** correction [40] within each family (75 defect tests; 55 CometKiwi tests). We call a result *robust* when it is Holm-significant **and** its bootstrap CI excludes zero.

With 12 languages, the smallest attainable exact Wilcoxon p is 0.00049. With 6 languages it is 0.031, so no IndicTrans2 CometKiwi comparison can survive Holm correction. We flag this rather than hide it.

---

## 4. Results

### 4.1 RQ1: Which paradigm breaks fewer strings?

**Table 2. Invariant defects per system (10,228 strings × 12 languages; IndicTrans2 × 6).** Source: `results/master_table_by_system.csv`.

| System | Flawed | Defect rate | High-res. | Low-res. | Accelerator | Copy fallback | Placeholder | Script | Encoding |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| *NMT* | | | | | | | | | |
| NLLB-200 | 5,125 | 4.18% | 5.52% | 3.22% | 2,850 | 554 | 1,728 | 0 | 0 |
| Google Translate | 7,706 | 6.28% | 6.49% | 6.13% | 6,146 | 836 | 727 | 0 | 1 |
| IndicTrans2 (6 langs) | 4,661 | 7.60% | – | 7.60% | 2,524 | 38 | 2,125 | 1 | 0 |
| Microsoft Translator | 9,458 | 7.71% | 5.30% | 9.43% | 5,378 | 2,218 | 1,861 | 364 | 1 |
| MADLAD-400 | 11,119 | 9.06% | 8.21% | 9.67% | 6,525 | 1,999 | 2,546 | 4 | 0 |
| *LLM, zero-shot* | | | | | | | | | |
| GPT-4o-mini | 3,104 | 2.53% | 2.30% | 2.69% | 1,939 | 1,083 | 5 | 81 | 0 |
| Qwen-2.5-7B | 7,340 | 5.98% | 2.51% | 8.46% | 1,106 | 3,933 | 691 | 328 | 1,343 |
| Llama-3.1-8B | 9,749 | 7.94% | 6.82% | 8.75% | 6,791 | 1,299 | 1,692 | 0 | 10 |
| Mistral-Nemo-12B | 17,302 | 14.10% | 15.95% | 12.77% | 6,518 | 718 | 10,148 | 0 | 10 |
| Gemma-2-9B | 26,899 | 21.92% | 5.80% | 33.43% | 5,076 | 20,611 | 43 | 1,226 | 0 |
| *LLM + repair* | | | | | | | | | |
| GPT-4o-mini + repair | 2,206 | 1.80% | 1.45% | 2.04% | 1,940 | 232 | 4 | 31 | 0 |
| Qwen-2.5-7B + repair | 2,996 | 2.44% | 1.00% | 3.47% | 1,124 | 1,167 | 52 | 136 | 541 |
| Gemma-2-9B + repair | 6,178 | 5.03% | 4.41% | 5.48% | 5,181 | 885 | 1 | 109 | 0 |
| Mistral-Nemo-12B + repair | 6,823 | 5.56% | 6.28% | 5.04% | 6,524 | 161 | 141 | 0 | 1 |
| Llama-3.1-8B + repair | 6,945 | 5.66% | 4.75% | 6.30% | 6,812 | 89 | 52 | 0 | 1 |

Chatter and empty output are rare (≤ 7 per suite, except MADLAD-400 with 74 empty outputs and NLLB-200 with 17); full counts are in the CSV.

**Like-for-like (zero-shot LLM vs NMT, neither post-processed).** The paired tests (`results/stats_defects_pairwise.csv`, family `llm_vs_nmt`; 50 tests, 48 robust) show that **neither paradigm dominates.** The best LLM beats the best NMT system, the worst LLMs are worse than any NMT system, and the middle overlaps:

| Zero-shot LLM | vs Google | vs Microsoft | vs NLLB-200 | vs MADLAD-400 | vs IndicTrans2 (6 langs) |
|---|---|---|---|---|---|
| GPT-4o-mini | **−3.75** [−4.04, −3.47] | **−5.18** | **−1.65** [−1.88, −1.42] | **−6.53** | **−4.76** |
| Qwen-2.5-7B | −0.30 [−0.65, 0.05] (tie) | **−1.73** | +1.81 | **−3.08** | +0.97 |
| Llama-3.1-8B | +1.67 | +0.24 [−0.09, 0.55] (tie) | +3.77 | **−1.12** | +1.30 |
| Mistral-Nemo-12B | +7.82 | +6.39 | +9.92 | +5.04 | +4.37 |
| Gemma-2-9B | +15.64 | +14.21 | +17.74 | +12.86 | +29.69 |

The table shows the risk difference in percentage points, LLM minus NMT; **bold** means the LLM is significantly safer. All entries except the two marked ties are robust.

GPT-4o-mini is safer than every NMT system, by 1.65 pp against the safest one (NLLB-200). Qwen-2.5-7B and Llama-3.1-8B sit inside the NMT range. Mistral-Nemo and Gemma are less safe than every NMT system. Among NMT systems, the open NLLB-200 (600M) is the safest (4.18%), safer than both commercial engines.

Figure 3 shows where defects concentrate. Gemma breaks 79.7% of Punjabi and 76.7% of Telugu strings. Microsoft is worst on Marathi and Punjabi (11.7% and 12.6%), MADLAD-400 exceeds 10% in five languages (de, hi, mr, pa, te), and NLLB-200 is worst on Chinese (8.7%).

### 4.2 Failure taxonomy: the two paradigms break software differently
Figure 4 shows the defect mix per system.

- **Accelerators: the biggest NMT failure.** Accelerators account for 54–80% of NMT defect occurrences. Of the accelerator strings in each suite, MADLAD-400 drops the accelerator in 69.3%, Google in 65.2%, Microsoft in 57.1%, IndicTrans2 in 53.6% and NLLB-200 in 30.3%. Typical NMT failures:
  - translating `&` as the word "and" (`& Data Format` → "और डेटा प्रारूप", `& User Certificate:` → "et certificat utilisateur")
  - keeping the letter but losing the marker (`& Delete...` → "मिटाएँ... (D)")
  - substituting a full-width `＆`

  Among zero-shot LLMs, Llama (72.1%) and Mistral-Nemo (69.2%) are as bad as the worst NMT, Gemma loses 53.9%, and GPT-4o-mini (20.6%) and Qwen (11.7%) lose far fewer than any NMT system.
- **Placeholders: NMT breaks them, open LLMs invent them.** NMT systems never add a placeholder (0 invented for Google, Microsoft, NLLB and IndicTrans2; 4 for MADLAD-400). Instead they break the ones present, usually by reformatting `%1` as `1%`, `% 1` or `٪ 1`. The share of placeholder-bearing strings broken is 17% for Google, 40–44% for NLLB-200 and Microsoft, 60% for MADLAD-400 and 99.5% for IndicTrans2 (2,125 of 2,136, almost all split into `% 1`, consistent with its script-normalisation pre-processing). Open LLMs do the opposite: 97% of Mistral-Nemo's 10,148 placeholder errors and 90% of Llama's 1,692 are placeholders *added* to strings that had none (11,932 across the open models). The system prompt lists example specifiers (`{0}`, `%s`, `%d`), so we read this as **prompt-induced**. GPT-4o-mini breaks only 5 placeholders.
- **Copy collapse on low-resource languages (Gemma, Qwen).** 20,611 of Gemma's defects are untranslated copies, concentrated in pa/te/mr/ta. Its low-resource defect rate (33.43%) is 5.8× its high-resource rate (5.80%). NMT systems show no such collapse; NLLB-200 is in fact *safer* on low-resource languages (3.22% vs 5.52%).
- **Encoding and script errors.** Encoding corruption (U+FFFD) is specific to Qwen (1,343 strings). Script contamination appears in Gemma (1,226), Microsoft Translator (364, all in Punjabi, e.g. the Arabic percent sign ٪ in `٪ 1`) and Qwen (328).

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
Repair reduces defects for every LLM, and every reduction is robust (family `baseline_vs_repaired`):

| Model | Baseline → repaired | Relative change | Risk difference [95% CI] |
|---|---|---:|---|
| GPT-4o-mini | 2.53% → 1.80% | −28.9% | 0.73 pp [0.64, 0.83] |
| Llama-3.1-8B | 7.94% → 5.66% | −28.8% | 2.29 pp [2.11, 2.47] |
| Mistral-Nemo-12B | 14.10% → 5.56% | −60.6% | 8.54 pp [8.17, 8.92] |
| Gemma-2-9B | 21.92% → 5.03% | −77.0% | 16.88 pp [16.66, 17.10] |
| Qwen-2.5-7B | 5.98% → 2.44% | −59.2% | 3.54 pp [3.42, 3.67] |

**Repair moves every LLM below most NMT systems.** All five repaired suites are robustly safer than Google Translate (by 0.62–4.48 pp), Microsoft Translator (2.05–5.91 pp), MADLAD-400 (3.40–7.26 pp) and IndicTrans2 (1.16–5.43 pp on its six languages). Against NLLB-200, the safest NMT system, only repaired GPT-4o-mini (−2.38 pp) and repaired Qwen (−1.74 pp) are safer. Repaired Gemma, Mistral-Nemo and Llama remain 0.86–1.48 pp behind it, because of their accelerator losses.

**Repair fixes what its validator checks.** For the defect types the repair validator detected (placeholders, copy fallback, script, encoding, chatter), residual counts fall sharply. Invented placeholders drop from 11,932 to 130 (−98.9%), and Gemma's copy fallbacks drop from 20,611 to 885. No string that was clean before repair is flawed after it: the clean→flawed count is 0 in every model.

**Repair does not fix what its validator misses.** Accelerator losses are essentially unchanged: Llama 6,791 → 6,812, Mistral-Nemo 6,518 → 6,524, Gemma 5,076 → 5,181, GPT-4o-mini 1,939 → 1,940. After repair, accelerators account for 84–98% of all remaining defects in GPT-4o-mini, Llama, Mistral-Nemo and Gemma. The small increases (e.g. +105 for Gemma) come from strings that were re-translated to fix another defect and lost their `&` in the process. Those strings were already flawed, so they do not count as clean→flawed. Repaired Llama and Mistral-Nemo are tied (0.10 pp [−0.03, 0.24], not significant).

Repair also *raised* CometKiwi for every open model (Llama +0.0048, Mistral-Nemo +0.0264, Gemma +0.0259, Qwen +0.0023; all Holm p = 0.027, robust) and left GPT-4o-mini unchanged (0.0000, p = 0.97). The independent quality model therefore agrees that the repaired strings are better translations, not just strings that pass a regex.

Repair is cheap. The targeted re-prompts for the four open models took 89 s (Llama), 155 s (Mistral-Nemo), 151 s (Qwen) and 512 s (Gemma) of A100 wall-clock time for 3,008–21,888 flagged strings (`reports/repair_execution_telemetry.jsonl`).

### 4.5 The safety–quality trade-off
Figure 2 places all 15 suites by defect rate and CometKiwi. **GPT-4o-mini + repair dominates the field.** It has the lowest defect rate of any system (1.80%), and its CometKiwi (0.7877) is statistically tied with Google (0.7939), Microsoft (0.7894) and NLLB-200 (0.7834). Among NMT systems:
- NLLB-200 gives the best safety–quality balance (4.18%, 0.7834).
- Google and IndicTrans2 have the highest quality but break 6–8% of strings.
- MADLAD-400 is dominated on both axes by GPT-4o-mini, Google, Microsoft and NLLB-200.

The open LLMs, even repaired, sit below the NMT quality band. Repair moves them left toward NMT-level safety but not up to NMT-level quality.

---

## 5. Discussion

**There is no safe paradigm, only safe configurations.** A team choosing "NMT because it is predictable" ships 4–9% broken strings, mostly lost accelerators and split placeholders. A team choosing "LLMs because they follow instructions" ships anywhere from 2.5% to 22% depending on the model. The deciding factors are the specific engine and whether a validator sits behind it.

**The validator is the product.** The repair loop removed nearly every defect it could see and none it could not. One regex that did not match the corpus's `& File` notation left about 6,800 accelerator losses per open model in place after repair. For CI/CD use, validator coverage must be tested against the real string format of each project, for example with seeded test strings for every invariant type, before the loop is trusted. The same validator could gate NMT output too.

**Each family needs a different guard.**
- For NMT, the main risks are accelerators and placeholder formatting. Masking both with opaque tokens before translation and restoring them afterwards would remove most NMT defects; this is standard practice in professional CAT tools and not done by the raw APIs.
- For LLMs, the risks are prompt-induced placeholder invention and low-resource collapse. Per-string constraints that name exactly the placeholders and accelerators present (as the repair prompt does) address the first. Language-based routing or the validator gate addresses the second.

**Pre-processing can break invariants.** IndicTrans2's script normalisation split 99.5% of placeholders into `% 1`. Toolkit pre- and post-processing is part of the system under test and must be audited with it.

**Validator-in-the-loop as a pipeline stage.** The audit is deterministic and cheap, and repair touches only flagged strings, so the pattern fits a CI/CD gate: translate → validate → repair → re-validate → merge. This connects directly to the Track 3 CI/CD design (Paper 2) [7].

**Choosing an engine.**
- For the best combination of quality and safety: GPT-4o-mini behind a validator-repair gate.
- For an open-weights, self-hosted deployment: NLLB-200 is the safest NMT and close to commercial quality. Among open LLMs, repaired Gemma-2-9B is tied with MADLAD-400 on quality and safer, but it still needs accelerator handling.
- For Indic languages specifically: IndicTrans2 has the highest CometKiwi, but its placeholder handling must be fixed before deployment.

---

## 6. Threats to Validity

1. **Repair validator coverage and circularity.** The repair loop accepts a fix only if it passes its own validator. Defects of the types it checks are therefore low after repair partly by construction. The independent CometKiwi gain supports a real improvement. Conversely, the validator's accelerator pattern (`&[^\s\d_;]`) matched 1 of 785 accelerator strings, so accelerator defects were never repaired. Our audit uses a corrected pattern (`&\s?[^\s\d_;&]`). The defect counts in the LLM repository's README use the original pattern and are lower for that reason.
2. **Unequal treatment.** Only LLMs were repaired. The like-for-like comparison is zero-shot LLM vs NMT (§4.1). Applying a validator gate and placeholder/accelerator masking to NMT is a natural follow-up.
3. **Audit precision.** The audit is 92% precise on 150 validated flags and 100% precise for accelerator, placeholder, encoding and script flags. Its false positives are copy-fallback flags on names, identifiers and cognates, so copy-fallback counts are slight over-estimates for both families. Grades were model-assisted with a human spot-check.
4. **What counts as an accelerator.** We count an accelerator as lost when no `&` marker remains, even if the target keeps the letter, e.g. `(D)`. Without the marker the shortcut does not work in KDE/Qt, but a localization engineer could restore it cheaply. These NMT cases are therefore easier to fix than a translated "and".
5. **Quality granularity.** CometKiwi is available only as per-language means, so quality tests have n = 12 (n = 6 for IndicTrans2) and limited power. A single QE model is used, and CometKiwi is not designed to judge format invariants.
6. **Model versions.** The API model is GPT-4o-mini, not GPT-4o. Commercial engines (Google, Microsoft, OpenAI) change server-side; outputs are frozen at their generation dates (3 Sep, 6 Sep and 18 Oct 2026). Google output came from the Sheets function, not the Cloud API.
7. **Corpus.** KDE strings represent desktop UI, and the OPUS tokenization (`& File`, `& kexi;`) differs from raw `.po` files. Both families saw the same tokenized input, so the comparison is fair, but absolute accelerator rates on raw `&File` strings may differ. A few source lines are corpus artifacts (hundreds of strings merged into one line). Web, mobile and cloud-console strings may contain different invariant mixes (ICU plural syntax, HTML).

---

## 7. Conclusion

On 10,228 KDE strings in 12 languages, neither LLMs nor classic NMT systems are uniformly safer for software localization. NMT systems break 4–9% of strings, mostly by losing keyboard accelerators and reformatting placeholders. Zero-shot LLMs range from 2.5% (GPT-4o-mini, safer than every NMT system) to 22% (Gemma-2-9B), failing through invented placeholders, accelerator loss and low-resource copy collapse. A compiler-guided self-repair loop removes 29–77% of LLM defects without adding new flawed strings and makes every repaired LLM safer than four of the five NMT systems. It still cannot fix what its validator does not check.

On quality, GPT-4o-mini matches commercial NMT, while open 7–12B LLMs trail it, especially in low-resource languages. GPT-4o-mini with repair is the only configuration that is both at NMT quality and below 2% defects. For continuous localization, the engine choice matters less than putting a well-tested invariant validator between the engine and the build. Scripts, results and figures are released for re-running.

---

## Figures (in `paper1_llm_vs_nmt/figures/`)
- **Fig. 1** `fig1_defect_rate_by_system.png`: defect rate of all 15 suites, sorted, coloured by family.
- **Fig. 2** `fig2_quality_vs_defects.png`: CometKiwi vs defect rate; arrows show the effect of repair.
- **Fig. 3** `fig3_defect_heatmap_by_lang.png`: defect rate by system × language.
- **Fig. 4** `fig4_defect_taxonomy.png`: defect-type mix per system.

## Reproduction
```
python paper1_llm_vs_nmt/scripts/audit.py
python paper1_llm_vs_nmt/scripts/build_master_table.py
python paper1_llm_vs_nmt/scripts/stats.py
python paper1_llm_vs_nmt/scripts/generate_figures.py
python paper1_llm_vs_nmt/scripts/sample_nmt_check.py   # NMT validation sample (kept if already graded)
```

---

## References

[1]–[30] are taken from the Track 1 NMT paper (`nmt-benchmarking-paper-main/main.tex`; ref 28's author list corrected); [31]–[41] were added for this paper and checked against their publisher pages.

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
