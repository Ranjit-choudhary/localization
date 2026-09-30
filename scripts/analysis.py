"""
Corpus-level NMT vs LLM comparison: results tables, metric agreement, figures.

Mirrors the analyses in the NMT paper (Sections 5.2-5.4, 6.3) with the LLM
systems added, reading the NMT scores from the NMT repo unchanged:
    tables/tab_high_resource.{csv,tex}   mean over de, fr, zh, es, ja
    tables/tab_low_resource.{csv,tex}    mean over the 7 low-resource pairs
    tables/tab_indic6.{csv,tex}          mean over the 6 Indic pairs (all systems comparable)
    tables/tab_<metric>_by_language.{csv,tex}
    tables/tab_resource_gap.csv          high - low mean per system
    metrics/analysis/kendall_tau.csv     metric agreement across system-language pairs
    figures/*.png|pdf

Reference-based metrics measure agreement with the Google Translate baseline,
not certified correctness (same caveat as the NMT paper).

Usage:
    python scripts/analysis.py
"""
import itertools

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from common import (COLORS, DISPLAY, FIGURES, HIGH, INDIC, LANGS, LANG_NAMES, LLM_SYSTEMS,
                    LOW, LOWER_IS_BETTER, METRIC_LABELS, METRICS, NMT_SYSTEMS, TABLES,
                    ensure_dirs, load_all_scores, metric_cols)

SYSTEM_ORDER = NMT_SYSTEMS + LLM_SYSTEMS

plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#8a8a85",
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#e4e3dc", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False, "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(FIGURES / f"{name}.png")
    fig.savefig(FIGURES / f"{name}.pdf")
    plt.close(fig)
    print(f"[fig] {name}")


def to_latex(df, path, caption, label, fmt="{:.2f}", bold_best=True):
    """Minimal booktabs table; bolds the best system per column (TER: lowest)."""
    cols = list(df.columns)
    lines = ["\\begin{table*}[t]", "\\centering", f"\\caption{{{caption}\\label{{{label}}}}}",
             "\\begin{tabular}{l" + "r" * len(cols) + "}", "\\toprule",
             "System & " + " & ".join(METRIC_LABELS.get(c, LANG_NAMES.get(c, c)) for c in cols) + " \\\\",
             "\\midrule"]
    best = {}
    for c in cols:
        s = df[c].dropna()
        if bold_best and len(s):
            best[c] = s.idxmin() if c in LOWER_IS_BETTER else s.idxmax()
    for idx, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if pd.isna(v):
                cells.append("--")
            else:
                t = fmt.format(v)
                cells.append(f"\\textbf{{{t}}}" if best.get(c) == idx else t)
        lines.append(f"{DISPLAY.get(idx, idx)} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def group_means(df, langs, metrics):
    sub = df[df.lang.isin(langs) & df.system.isin(SYSTEM_ORDER)]
    g = sub.groupby("system")[metrics].mean()
    n = sub.groupby("system").lang.nunique().rename("n_langs")
    return g.join(n).reindex([s for s in SYSTEM_ORDER if s in g.index])


def tables(df, metrics):
    specs = [("high_resource", HIGH, "High-resource results, mean over EN-DE, EN-FR, EN-ZH, EN-ES, EN-JA."),
             ("low_resource", LOW, "Low-resource results, mean over EN-HI, EN-AR, EN-BN, EN-MR, EN-PA, "
                                   "EN-TA, EN-TE (IndicTrans2 over its six supported pairs)."),
             ("indic6", INDIC, "Mean over the six Indic pairs, the subset supported by every system.")]
    out = {}
    for name, langs, cap in specs:
        t = group_means(df, langs, metrics)
        t.to_csv(TABLES / f"tab_{name}.csv", float_format="%.4f")
        lex = [m for m in metrics if m in ("bleu", "meteor", "chrf", "rouge_l", "ter")]
        neu = [m for m in metrics if m not in lex]
        t2 = t[lex].copy()
        for m in neu:  # neural metrics on 0-1 scale -> show x100 so one format fits all
            t2[m] = t[m] * 100
        to_latex(t2, TABLES / f"tab_{name}.tex",
                 cap + " Reference-based metrics measure agreement with the Google Translate baseline"
                       " (TER: lower is closer). Neural metrics shown $\\times$100.", f"tab:{name}")
        out[name] = t
        print(f"\n== {name} ==\n{t.round(3).to_string()}")

    for m in metrics:
        p = df[df.system.isin(SYSTEM_ORDER)].pivot(index="system", columns="lang", values=m)
        p = p.reindex(index=[s for s in SYSTEM_ORDER if s in p.index], columns=LANGS)
        p.to_csv(TABLES / f"tab_{m}_by_language.csv", float_format="%.4f")
        scale = 100 if df[m].max() <= 1.0 else 1
        to_latex(p * scale, TABLES / f"tab_{m}_by_language.tex",
                 f"{METRIC_LABELS[m]} by language" + (" ($\\times$100)" if scale == 100 else "") +
                 ". Dashes: pair not supported.", f"tab:{m}_lang")

    gap = pd.DataFrame({m: out["high_resource"][m] - out["low_resource"][m] for m in metrics})
    gap.to_csv(TABLES / "tab_resource_gap.csv", float_format="%.4f")
    return out


def kendall(df, metrics):
    """Pairwise Kendall tau across all system-language pairs (TER sign-inverted), as in NMT paper 6.3."""
    ref_metrics = [m for m in metrics if m != "cometkiwi"]
    d = df[df.system.isin(SYSTEM_ORDER)].dropna(subset=ref_metrics).copy()
    if "ter" in d:
        d["ter"] = -d["ter"]
    tau = pd.DataFrame(index=ref_metrics, columns=ref_metrics, dtype=float)
    for a, b in itertools.product(ref_metrics, ref_metrics):
        tau.loc[a, b] = kendalltau(d[a], d[b]).statistic
    tau.to_csv(METRICS / "analysis" / "kendall_tau.csv", float_format="%.3f")

    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    im = ax.imshow(tau.values.astype(float), cmap="RdBu_r", vmin=-1, vmax=1)
    labels = [METRIC_LABELS[m] for m in ref_metrics]
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.grid(False)
    for i, j in itertools.product(range(len(labels)), range(len(labels))):
        v = tau.values[i, j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                color="white" if abs(v) > 0.6 else "#1a1a19")
    fig.colorbar(im, ax=ax, shrink=0.8, label="Kendall's $\\tau$")
    ax.set_title(f"Metric agreement ({len(d)} system-language pairs)")
    save(fig, "fig_metric_correlation")
    return tau


def fig_by_language(df, metric):
    systems = [s for s in SYSTEM_ORDER if s in set(df.system)]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    width = 0.8 / len(systems)
    x = np.arange(len(LANGS))
    for i, s in enumerate(systems):
        vals = [df[(df.system == s) & (df.lang == l)][metric].mean() for l in LANGS]
        ax.bar(x + (i - (len(systems) - 1) / 2) * width, vals, width * 0.9, color=COLORS[s],
               label=DISPLAY[s], edgecolor="white", linewidth=0.4)
    ax.axvline(len(HIGH) - 0.5, color="#8a8a85", linewidth=0.8, linestyle=":")
    ax.text(len(HIGH) / 2 - 0.5, ax.get_ylim()[1], "high-resource", ha="center", va="bottom", fontsize=8,
            color="#5f5e5a")
    ax.text(len(HIGH) + len(LOW) / 2 - 0.5, ax.get_ylim()[1], "low-resource", ha="center", va="bottom",
            fontsize=8, color="#5f5e5a")
    ax.set_xticks(x, [LANG_NAMES[l] for l in LANGS], rotation=30, ha="right")
    ax.set_ylabel(METRIC_LABELS[metric] + (" (lower = closer)" if metric in LOWER_IS_BETTER else ""))
    ax.legend(ncol=3, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.3))
    save(fig, f"fig_{metric}_by_language")


def fig_resource_gap(tabs, metric):
    hi, lo = tabs["high_resource"][metric], tabs["low_resource"][metric]
    systems = [s for s in SYSTEM_ORDER if s in hi.index and pd.notna(hi.get(s))]
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    y = np.arange(len(systems))[::-1]
    for yi, s in zip(y, systems):
        ax.plot([lo[s], hi[s]], [yi, yi], color="#c3c2b7", linewidth=2, zorder=1)
        ax.scatter([hi[s]], [yi], s=40, color=COLORS[s], zorder=2, marker="o")
        ax.scatter([lo[s]], [yi], s=40, color="white", edgecolor=COLORS[s], linewidth=1.5, zorder=2)
    ax.set_yticks(y, [DISPLAY[s] for s in systems])
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"Mean {METRIC_LABELS[metric]}  (filled = high-resource, open = low-resource)")
    save(fig, f"fig_resource_gap_{metric}")


def fig_heatmap(df, metric):
    p = df[df.system.isin(SYSTEM_ORDER)].pivot(index="system", columns="lang", values=metric)
    p = p.reindex(index=[s for s in SYSTEM_ORDER if s in p.index], columns=LANGS)
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    cmap = plt.get_cmap("Blues_r" if metric in LOWER_IS_BETTER else "Blues").copy()
    cmap.set_bad("#f0efe9")
    im = ax.imshow(np.ma.masked_invalid(p.values.astype(float)), cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(LANGS)), [LANG_NAMES[l] for l in LANGS], rotation=30, ha="right")
    ax.set_yticks(range(len(p.index)), [DISPLAY[s] for s in p.index])
    ax.grid(False)
    lo, hi = np.nanmin(p.values), np.nanmax(p.values)
    for i, j in itertools.product(range(p.shape[0]), range(p.shape[1])):
        v = p.values[i, j]
        if pd.notna(v):
            dark = (v - lo) / (hi - lo + 1e-9) > 0.6
            if metric in LOWER_IS_BETTER:
                dark = not dark
            ax.text(j, i, f"{v:.3f}" if hi <= 1 else f"{v:.1f}", ha="center", va="center", fontsize=6.5,
                    color="white" if dark else "#1a1a19")
    fig.colorbar(im, ax=ax, shrink=0.9, label=METRIC_LABELS[metric])
    save(fig, f"fig_heatmap_{metric}")


def main():
    ensure_dirs()
    df = load_all_scores()
    metrics = metric_cols(df)
    llm_metrics = [m for m in metrics if df[df.system.isin(LLM_SYSTEMS)][m].notna().any()]
    print(f"Metrics available for LLM systems: {llm_metrics}")
    if len(llm_metrics) < len(metrics):
        print(f"  (pending for LLMs: {sorted(set(metrics) - set(llm_metrics))} -- run on GPU, then re-run)")
    df.to_csv(METRICS / "analysis" / "all_scores_long.csv", index=False, float_format="%.6f")

    tabs = tables(df, metrics)
    kendall(df, llm_metrics)
    for m in llm_metrics:
        fig_by_language(df, m)
    for m in ("chrf", "comet", "cometkiwi"):
        if m in llm_metrics:
            fig_heatmap(df, m)
            fig_resource_gap(tabs, m)
    print(f"\nTables -> {TABLES}\nFigures -> {FIGURES}")


if __name__ == "__main__":
    main()
