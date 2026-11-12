"""
Week 3 - Statistical significance for Paper 1.

A) Invariant defects (string level; needs audit output for both systems)
   Unit = one (language, source line) pair; both systems translated the same 10,228
   source strings into the same languages, so comparisons are paired.
   * Risk difference (percentage points) with a 95% CI from a CLUSTER bootstrap over the
     10,228 source strings (10,000 resamples, seed 42). Resampling whole source strings
     keeps the 12 translations of one string together, so correlation across languages
     does not shrink the CI.
   * McNemar test on discordant pairs (exact binomial when b+c < 25, else chi-square with
     continuity correction) and the paired odds ratio b/c.
   * Holm-Bonferroni correction across the whole family of defect tests.
   * `robust` = Holm-significant AND bootstrap CI excludes 0 (McNemar treats the 12
     translations of a string as independent; the cluster CI does not).
   Comparisons: baseline vs repaired per model, all pairs of repaired LLMs, all pairs of
   baseline LLMs. LLM vs NMT is run automatically for any NMT system whose translation
   files exist (none yet: Track 1 files are 0-byte stubs).

B) CometKiwi (language level; only per-language means exist, no per-segment scores)
   Unit = one language. Paired over the languages both systems cover (12, or 6 for
   IndicTrans2).
   * Mean difference with a 95% bootstrap CI over languages (10,000 resamples, seed 42).
   * Exact two-sided Wilcoxon signed-rank test; effect size Cohen's dz.
   * Holm-Bonferroni across the CometKiwi family.
   Comparisons: every LLM suite vs every NMT system, plus baseline vs repaired per model.
   Note: with 12 languages the smallest possible exact Wilcoxon p is 0.00049; with 6
   languages (IndicTrans2) it is 0.031, which cannot survive Holm correction.

Outputs (overwritten):
  results/stats_defects_pairwise.csv
  results/stats_cometkiwi_pairwise.csv

Run:  python paper1_llm_vs_nmt/scripts/stats.py
"""
import sys
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "paper1_llm_vs_nmt" / "results"
N_LINES = 10228
LANGS = ["ar", "bn", "de", "es", "fr", "hi", "ja", "mr", "pa", "ta", "te", "zh"]
N_BOOT = 10_000
SEED = 42
MODELS = ["gpt4o", "llama_8b", "mistral_nemo", "gemma_9b", "qwen_7b"]
NMT_ALIASES = {"baseline_google_translate": "google_translate"}


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


# ---------------------------------------------------------------- A) defects
def load_flags(audited_pairs):
    """Return {system: bool array [n_langs_covered, N_LINES]} and the langs covered."""
    dps = pd.read_csv(RESULTS / "defects_per_string.csv")
    dps["system"] = dps["system"].replace(NMT_ALIASES)
    flags, langs_of = {}, {}
    for sysname, g in audited_pairs.groupby("system"):
        langs = [l for l in LANGS if l in set(g["lang"])]
        arr = np.zeros((len(langs), N_LINES), dtype=bool)
        sub = dps[dps["system"] == sysname]
        li = {l: i for i, l in enumerate(langs)}
        for lang, ids in sub.groupby("lang")["line_id"]:
            arr[li[lang], ids.values - 1] = True
        flags[sysname] = arr
        langs_of[sysname] = langs
    return flags, langs_of


def cluster_bootstrap_rd(d_per_line, n_units, rng):
    """d_per_line: per source line, sum over languages of (flag_a - flag_b).
    Returns 2.5/97.5 percentiles of the risk difference in percentage points."""
    n = len(d_per_line)
    out = np.empty(N_BOOT)
    chunk = 1000
    for start in range(0, N_BOOT, chunk):
        idx = rng.integers(0, n, size=(min(chunk, N_BOOT - start), n))
        out[start:start + idx.shape[0]] = d_per_line[idx].sum(axis=1) / n_units * 100
    return np.percentile(out, [2.5, 97.5])


def compare_defects(a, b, flags, langs_of, family, rng):
    shared = [l for l in langs_of[a] if l in langs_of[b]]
    fa = flags[a][[langs_of[a].index(l) for l in shared]]
    fb = flags[b][[langs_of[b].index(l) for l in shared]]
    n_units = fa.size
    b_cnt = int((fa & ~fb).sum())   # a flawed, b clean
    c_cnt = int((~fa & fb).sum())   # a clean, b flawed
    rate_a = fa.mean() * 100
    rate_b = fb.mean() * 100
    rd = rate_a - rate_b
    d_line = (fa.astype(np.int16) - fb.astype(np.int16)).sum(axis=0)
    lo, hi = cluster_bootstrap_rd(d_line, n_units, rng)
    disc = b_cnt + c_cnt
    if disc == 0:
        p, test = 1.0, "none (no discordant pairs)"
    elif disc < 25:
        p, test = stats.binomtest(b_cnt, disc, 0.5).pvalue, "exact binomial"
    else:
        chi2 = (abs(b_cnt - c_cnt) - 1) ** 2 / disc
        p, test = stats.chi2.sf(chi2, 1), "chi-square (cc)"
    odds = (b_cnt + 0.5) / (c_cnt + 0.5) if (b_cnt == 0 or c_cnt == 0) else b_cnt / c_cnt
    return {
        "family": family, "system_a": a, "system_b": b, "n_languages": len(shared),
        "n_pairs": n_units, "defect_rate_a_pct": round(rate_a, 3), "defect_rate_b_pct": round(rate_b, 3),
        "risk_diff_pp": round(rd, 3), "rd_ci95_low": round(lo, 3), "rd_ci95_high": round(hi, 3),
        "relative_change_pct": round((rate_b - rate_a) / rate_a * 100, 1) if rate_a > 0 else np.nan,
        "discordant_a_only": b_cnt, "discordant_b_only": c_cnt,
        "paired_odds_ratio": round(odds, 3), "mcnemar_test": test, "p_value": p,
    }


def run_defects():
    summ = pd.read_csv(RESULTS / "defect_summary.csv")
    summ["system"] = summ["system"].replace(NMT_ALIASES)
    flags, langs_of = load_flags(summ[["system", "lang"]])
    rng = np.random.default_rng(SEED)
    rows = []
    for m in MODELS:
        rows.append(compare_defects(f"baseline_{m}", f"repaired_{m}", flags, langs_of, "baseline_vs_repaired", rng))
    for tier in ("repaired", "baseline"):
        for x, y in combinations(MODELS, 2):
            rows.append(compare_defects(f"{tier}_{x}", f"{tier}_{y}", flags, langs_of, f"{tier}_pairwise", rng))
    nmt = [s for s in flags if not s.startswith(("baseline_", "repaired_"))]
    for n in nmt:
        for t in ("baseline", "repaired"):
            for m in MODELS:
                rows.append(compare_defects(f"{t}_{m}", n, flags, langs_of, "llm_vs_nmt", rng))
    df = pd.DataFrame(rows)
    df["p_holm"] = holm(df["p_value"])
    df["significant_holm_05"] = df["p_holm"] < 0.05
    # robust = Holm-significant AND the cluster-bootstrap CI excludes zero
    df["robust"] = df["significant_holm_05"] & ((df["rd_ci95_low"] > 0) | (df["rd_ci95_high"] < 0))
    df.to_csv(RESULTS / "stats_defects_pairwise.csv", index=False, encoding="utf-8")
    return df, nmt


# --------------------------------------------------------------- B) CometKiwi
def run_cometkiwi():
    mt = pd.read_csv(RESULTS / "master_table.csv")
    piv = mt.pivot(index="system", columns="lang", values="cometkiwi")
    fam = mt.drop_duplicates("system").set_index("system")["family"]
    llm = [s for s in piv.index if fam[s] == "LLM"]
    nmt = [s for s in piv.index if fam[s] == "NMT"]
    rng = np.random.default_rng(SEED)
    pairs = [(f"baseline_{m}", f"repaired_{m}", "baseline_vs_repaired") for m in MODELS]
    pairs += [(l, n, "llm_vs_nmt") for l in llm for n in nmt]
    rows = []
    for a, b, family in pairs:
        both = piv.loc[[a, b]].dropna(axis=1)
        d = (both.loc[a] - both.loc[b]).values
        n = len(d)
        boot = rng.choice(d, size=(N_BOOT, n), replace=True).mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        if np.allclose(d, 0):
            p = 1.0
        else:
            p = stats.wilcoxon(d, alternative="two-sided", method="exact").pvalue
        sd = d.std(ddof=1)
        rows.append({
            "family": family, "system_a": a, "system_b": b, "n_languages": n,
            "cometkiwi_a": round(both.loc[a].mean(), 4), "cometkiwi_b": round(both.loc[b].mean(), 4),
            "mean_diff": round(d.mean(), 4), "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
            "langs_a_higher": int((d > 0).sum()), "langs_b_higher": int((d < 0).sum()),
            "cohens_dz": round(d.mean() / sd, 3) if sd > 0 else np.nan,
            "wilcoxon_p": p,
        })
    df = pd.DataFrame(rows)
    df["p_holm"] = holm(df["wilcoxon_p"])
    df["significant_holm_05"] = df["p_holm"] < 0.05
    df["robust"] = df["significant_holm_05"] & ((df["ci95_low"] > 0) | (df["ci95_high"] < 0))
    df.to_csv(RESULTS / "stats_cometkiwi_pairwise.csv", index=False, encoding="utf-8")
    return df


def main():
    print("A) Defect tests (cluster bootstrap over source strings + McNemar)...")
    dd, nmt_audited = run_defects()
    print(f"   {len(dd)} comparisons, {dd.significant_holm_05.sum()} significant after Holm, {dd.robust.sum()} robust. "
          f"NMT systems with string data: {nmt_audited or 'none (Track 1 files missing)'}")
    show = dd[dd.family == "baseline_vs_repaired"][["system_a", "defect_rate_a_pct", "defect_rate_b_pct",
                                                    "risk_diff_pp", "rd_ci95_low", "rd_ci95_high", "p_holm"]]
    print(show.to_string(index=False))
    print("\nB) CometKiwi tests (paired over languages, Wilcoxon exact)...")
    ck = run_cometkiwi()
    print(f"   {len(ck)} comparisons, {ck.significant_holm_05.sum()} significant after Holm, {ck.robust.sum()} robust.")
    print(ck[ck.family == "baseline_vs_repaired"][["system_a", "mean_diff", "ci95_low", "ci95_high",
                                                   "wilcoxon_p", "p_holm"]].to_string(index=False))
    print("\nWrote results/stats_defects_pairwise.csv and results/stats_cometkiwi_pairwise.csv")


if __name__ == "__main__":
    main()
