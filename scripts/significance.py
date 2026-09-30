"""
Statistical validation of LLM vs NMT differences (Roadmap Phase 3, Track 1 & 2).

1. Paired bootstrap resampling (Koehn, 2004) per language, via SacreBLEU's
   PairedTest (1,000 resamples, seed 12345): the primary LLM is the baseline
   and every NMT system (and the cleaned LLM variant) is tested against it on
   BLEU and chrF++. p-values are Holm-corrected within each metric.
      -> metrics/significance/paired_bootstrap.csv, tables/tab_significance_chrf.tex
2. Segment-level Wilcoxon signed-rank test on sentence chrF++ (10,228 paired
   strings per language), with the matched-pairs rank-biserial correlation as
   effect size and win/tie/loss counts. With n = 10,228 almost any difference is
   "significant", so report the effect size, not just p.
      -> metrics/significance/wilcoxon_sentence_chrf.csv
3. Cross-language tests on corpus scores: Friedman test across the systems that
   cover all 12 languages (and across all systems on the 6 Indic languages),
   followed by pairwise Wilcoxon (LLM vs each system, n = languages), Holm-corrected.
      -> metrics/significance/friedman.csv, pairwise_across_languages.csv

Usage:
    python scripts/significance.py [--n-samples 1000]
"""
import argparse

import numpy as np
import pandas as pd
from sacrebleu.metrics import BLEU, CHRF
from sacrebleu.significance import PairedTest
from scipy.stats import friedmanchisquare, rankdata, wilcoxon

from common import (DISPLAY, INDIC, LANG_NAMES, LANGS, LLM_SYSTEMS, METRICS, NMT_SYSTEMS,
                    PRIMARY_LLM, TABLES, ensure_dirs, load_all_scores, load_lines, load_reference,
                    metric_cols, supports)

OUT = METRICS / "significance"
SENT = METRICS / "sentence_level" / "chrf_sentence.csv.gz"
BLEU_TOK = {"zh": "zh", "ja": "ja-mecab"}


def holm(p):
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


def rank_biserial(diff):
    d = diff[diff != 0]
    if len(d) == 0:
        return 0.0
    r = rankdata(np.abs(d))
    return (r[d > 0].sum() - r[d < 0].sum()) / r.sum()


def comparison_systems(lang):
    return [s for s in NMT_SYSTEMS + [x for x in LLM_SYSTEMS if x != PRIMARY_LLM] if supports(s, lang)]


def paired_bootstrap(n_samples):
    rows = []
    for lang in LANGS:
        refs = load_reference(lang)
        named = [(PRIMARY_LLM, load_lines(PRIMARY_LLM, lang))]
        named += [(s, load_lines(s, lang)) for s in comparison_systems(lang)]
        bleu = BLEU(tokenize=BLEU_TOK[lang]) if lang in BLEU_TOK else BLEU()
        test = PairedTest(named, {"BLEU": bleu, "chrF++": CHRF(word_order=2)}, [refs],
                          test_type="bs", n_samples=n_samples)
        _, scores = test()
        for key, results in scores.items():
            if key == "System":
                continue
            metric = "bleu" if key.startswith("BLEU") else "chrf"
            base = results[0]
            for name, res in zip(scores["System"], results):
                rows.append({"lang": lang, "metric": metric, "system": name, "score": res.score,
                             "bs_mean": res.mean, "ci95": res.ci, "llm_score": base.score,
                             "delta_vs_llm": res.score - base.score,
                             "p_value": res.p_value})
        print(f"[bootstrap] {lang} done")
    df = pd.DataFrame(rows)
    comp = df.system != PRIMARY_LLM
    df["p_holm"] = np.nan
    for m in df.metric.unique():
        idx = df.index[comp & (df.metric == m)]
        df.loc[idx, "p_holm"] = holm(df.loc[idx, "p_value"])
    df["significant_0.05"] = df.p_holm < 0.05
    df.to_csv(OUT / "paired_bootstrap.csv", index=False, float_format="%.5f")
    return df


def sentence_chrf():
    if SENT.exists():
        return pd.read_csv(SENT)
    chrf = CHRF(word_order=2)
    rows = []
    for lang in LANGS:
        refs = load_reference(lang)
        for s in [PRIMARY_LLM] + comparison_systems(lang):
            hyps = load_lines(s, lang)
            scores = [chrf.sentence_score(h, [r]).score for h, r in zip(hyps, refs)]
            rows.append(pd.DataFrame({"system": s, "lang": lang, "line": np.arange(1, len(hyps) + 1),
                                      "chrf": np.round(scores, 3)}))
        print(f"[sentence chrF++] {lang} done")
    df = pd.concat(rows, ignore_index=True)
    SENT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SENT, index=False)
    return df


def wilcoxon_sentence(sent):
    rows = []
    for lang in LANGS:
        base = sent[(sent.system == PRIMARY_LLM) & (sent.lang == lang)].chrf.values
        for s in comparison_systems(lang):
            other = sent[(sent.system == s) & (sent.lang == lang)].chrf.values
            diff = other - base
            p = wilcoxon(other, base, zero_method="wilcox").pvalue if np.any(diff) else 1.0
            rows.append({"lang": lang, "system": s, "n": len(diff),
                         "mean_llm": base.mean(), "mean_system": other.mean(),
                         "median_diff": np.median(diff), "mean_diff": diff.mean(),
                         "system_better": int((diff > 0).sum()), "tie": int((diff == 0).sum()),
                         "llm_better": int((diff < 0).sum()),
                         "rank_biserial": rank_biserial(diff), "p_value": p})
    df = pd.DataFrame(rows)
    df["p_holm"] = holm(df.p_value)
    df.to_csv(OUT / "wilcoxon_sentence_chrf.csv", index=False, float_format="%.5g")
    return df


def across_languages(scores):
    metrics = metric_cols(scores)
    fr_rows, pw_rows = [], []
    subsets = {"all12": (LANGS, [s for s in NMT_SYSTEMS if s != "indictrans2"] + [PRIMARY_LLM]),
               "indic6": (INDIC, NMT_SYSTEMS + [PRIMARY_LLM])}
    for subset, (langs, systems) in subsets.items():
        for m in metrics:
            p = scores[scores.system.isin(systems) & scores.lang.isin(langs)].pivot(
                index="lang", columns="system", values=m)
            if p[PRIMARY_LLM].isna().all():
                continue
            p = p.dropna()
            stat, pval = friedmanchisquare(*[p[s] for s in systems])
            fr_rows.append({"subset": subset, "metric": m, "n_langs": len(p), "k_systems": len(systems),
                            "chi2": stat, "p_value": pval})
            for s in systems:
                if s == PRIMARY_LLM:
                    continue
                d = p[s] - p[PRIMARY_LLM]
                pw_rows.append({"subset": subset, "metric": m, "system": s, "n_langs": len(p),
                                "mean_delta_vs_llm": d.mean(),
                                "langs_system_better": int((d > 0).sum()),
                                "p_value": wilcoxon(p[s], p[PRIMARY_LLM]).pvalue})
    fr = pd.DataFrame(fr_rows)
    pw = pd.DataFrame(pw_rows)
    if len(pw):
        pw["p_holm"] = np.nan
        for key, g in pw.groupby(["subset", "metric"]):
            pw.loc[g.index, "p_holm"] = holm(g.p_value)
    fr.to_csv(OUT / "friedman.csv", index=False, float_format="%.5g")
    pw.to_csv(OUT / "pairwise_across_languages.csv", index=False, float_format="%.5g")
    return fr, pw


def latex_bootstrap(bs):
    """Per-language chrF++ delta (system - LLM) with significance markers."""
    d = bs[(bs.metric == "chrf") & (bs.system != PRIMARY_LLM)]
    systems = [s for s in NMT_SYSTEMS + LLM_SYSTEMS if s in set(d.system)]
    llm = bs[(bs.metric == "chrf") & (bs.system == PRIMARY_LLM)].set_index("lang")
    lines = ["\\begin{table*}[t]", "\\centering",
             "\\caption{chrF++ of " + DISPLAY[PRIMARY_LLM] + " and difference of each system from it "
             "($\\Delta$ = system $-$ LLM), paired bootstrap resampling (1,000 samples), Holm-corrected: "
             "$^{*}p<0.05$, $^{**}p<0.01$. Positive $\\Delta$: system closer to the Google baseline."
             "\\label{tab:significance}}",
             "\\begin{tabular}{l r" + "r" * len(systems) + "}", "\\toprule",
             "Language & LLM & " + " & ".join(DISPLAY[s] for s in systems) + " \\\\", "\\midrule"]
    for lang in LANGS:
        cells = []
        for s in systems:
            r = d[(d.lang == lang) & (d.system == s)]
            if r.empty:
                cells.append("--")
                continue
            r = r.iloc[0]
            star = "$^{**}$" if r.p_holm < 0.01 else "$^{*}$" if r.p_holm < 0.05 else ""
            cells.append(f"{r.delta_vs_llm:+.2f}{star}")
        lines.append(f"{LANG_NAMES[lang]} & {llm.loc[lang, 'score']:.2f} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
    (TABLES / "tab_significance_chrf.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-samples", type=int, default=1000)
    args = ap.parse_args()
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    bs = paired_bootstrap(args.n_samples)
    latex_bootstrap(bs)
    sig = bs[bs.system != PRIMARY_LLM]
    print("\nPaired bootstrap (chrF++): delta = system - LLM")
    print(sig[sig.metric == "chrf"].pivot(index="lang", columns="system", values="delta_vs_llm")
          .round(2).to_string())

    ws = wilcoxon_sentence(sentence_chrf())
    print("\nSentence-level chrF++ Wilcoxon (effect size = rank-biserial, + means system better):")
    print(ws.pivot(index="lang", columns="system", values="rank_biserial").round(3).to_string())

    fr, pw = across_languages(load_all_scores())
    print("\nFriedman:\n" + fr.round(5).to_string(index=False))
    print("\nPairwise across languages:\n" + pw.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
