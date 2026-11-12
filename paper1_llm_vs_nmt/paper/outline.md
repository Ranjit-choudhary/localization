# Paper 1 — Outline

**Working title:** LLMs vs. Classic NMT Systems for Software UI Localization: Which One Breaks Software Strings Less, and How Does Quality Compare?

**Status legend:** ✅ numbers available · ⏳ waiting on Track 1 NMT translation files · ✍️ needs team input

## 1. Introduction
- Continuous localization in cloud-native CI/CD: translations ship without a human in the loop.
- A translation can be fluent and still break the build or the UI (lost `%1`, lost `&` accelerator, wrong script, `�`, untranslated leakage).
- Metrics like BLEU/COMET do not see these failures → need a deterministic invariant audit.
- RQ1: Which paradigm breaks fewer strings? (⏳ for NMT side)
- RQ2: How does CometKiwi quality compare? ✅
- RQ3: Does compiler-guided self-repair change the trade-off? ✅
- Contributions (4 bullets).

## 2. Related work
- Software localization & continuous localization (reuse Track 1 paper §2) ✍️
- NMT for software strings; LLMs as translators
- Quality estimation (CometKiwi) and its blind spots for format invariants
- LLM self-correction / validator-in-the-loop

## 3. Experimental setup
- 3.1 Corpus: 10,228 KDE4 strings, SHA-256, 12 languages (5 high / 7 low resource) ✅
- 3.2 Systems: 5 LLMs × {baseline, repaired}; 5 NMT systems (configs from Track 1) ✅
- 3.3 Invariant audit: 7 defect types, NTT allowlist ✅; audit precision from manual check ✍️
- 3.4 Compiler-guided self-repair (same model, targeted prompt, accept-only-if-valid) ✅
- 3.5 Quality: CometKiwi wmt22-cometkiwi-da, same checkpoint both tracks ✅
- 3.6 Statistics: cluster bootstrap, McNemar, Wilcoxon, Holm ✅

## 4. Results
- 4.1 RQ1 Defect rates — LLM ✅ / NMT ⏳ (Table 2, Fig 1, Fig 3)
- 4.2 Defect taxonomy — LLM ✅ / NMT ⏳ (Fig 4)
- 4.3 RQ2 CometKiwi LLM vs NMT ✅ (Table 3)
- 4.4 RQ3 Effect of repair ✅ (Fig 2)
- 4.5 Quality–safety trade-off (Fig 2) — LLM ✅ / NMT points ⏳

## 5. Discussion
- Placeholder hallucination is prompt-induced
- Low-resource collapse (Gemma pa/te, Qwen ta/te)
- Deployment guidance: when to pick which
- Validator-in-the-loop as a pipeline pattern (bridge to Paper 2 / Track 3)

## 6. Threats to validity
- Circularity: repair uses the audit's own checker
- Unequal treatment: NMT not repaired
- CometKiwi only at language level; one QE model
- Regex audit precision (manual check pending)
- GPT-4o-mini (not GPT-4o); commercial engines change over time

## 7. Conclusion
