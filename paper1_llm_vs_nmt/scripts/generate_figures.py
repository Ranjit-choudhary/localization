"""
Week 2 - Publication figures (300 DPI PNG) for Paper 1.

Reads results/master_table.csv and results/master_table_by_system.csv
(build_master_table.py output) and writes to paper1_llm_vs_nmt/figures/:

  fig1_defect_rate_by_system.png   (a) defect rate per system, baseline vs repaired
  fig2_quality_vs_defects.png      (b) CometKiwi vs defect rate (Pareto view);
                                       NMT systems drawn as CometKiwi reference lines
                                       until their string-level defect data exists
  fig3_defect_heatmap_by_lang.png  (c) defect rate, system x language
  fig4_defect_taxonomy.png         (d) defect-type mix per system

Systems without defect data (currently all NMT) are left out of the defect
axes and named in the caption note on each figure.

Run:  python paper1_llm_vs_nmt/scripts/generate_figures.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "paper1_llm_vs_nmt" / "results"
FIGS = ROOT / "paper1_llm_vs_nmt" / "figures"

# Reference palette (dataviz skill, light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
C_BASE = "#eb6834"   # slot 2 orange  -> baseline LLM
C_REP = "#2a78d6"    # slot 1 blue    -> repaired LLM
C_NMT = "#1baf7a"    # slot 3 aqua    -> NMT
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
TYPE_COLORS = {"Copy fallback": "#2a78d6", "Broken placeholder": "#eb6834",
               "Script contamination": "#1baf7a", "Encoding corruption": "#eda100",
               "Broken accelerator": "#e87ba4",
               "Other": "#898781"}

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 9, "axes.titlesize": 11, "axes.labelsize": 9,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "xtick.color": MUTED, "ytick.color": INK2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "grid.color": GRID, "grid.linewidth": 0.6,
})

MODELS = [("gpt4o", "GPT-4o-mini"), ("llama_8b", "Llama-3.1-8B"),
          ("mistral_nemo", "Mistral-Nemo-12B"), ("gemma_9b", "Gemma-2-9B"),
          ("qwen_7b", "Qwen-2.5-7B")]


def note(fig, missing):
    if missing:
        fig.text(0.01, -0.035, "Not shown (string-level NMT outputs not yet available): " + ", ".join(missing),
                 fontsize=7, color=MUTED, ha="left", va="bottom")


def save(fig, name):
    fig.savefig(FIGS / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote figures/{name}")


def fig1(bs, missing):
    llm = bs[bs.family == "LLM"].set_index("system")
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    y = np.arange(len(MODELS))
    h = 0.36
    for i, (key, label) in enumerate(MODELS):
        b = llm.loc[f"baseline_{key}", "defect_rate_pct"]
        r = llm.loc[f"repaired_{key}", "defect_rate_pct"]
        ax.barh(i - h / 2 - 0.01, b, height=h, color=C_BASE, edgecolor=SURFACE, linewidth=1)
        ax.barh(i + h / 2 + 0.01, r, height=h, color=C_REP, edgecolor=SURFACE, linewidth=1)
        ax.text(b + 0.25, i - h / 2, f"{b:.2f}%", va="center", fontsize=7.5, color=INK2)
        ax.text(r + 0.25, i + h / 2, f"{r:.2f}%", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [m[1] for m in MODELS])
    ax.invert_yaxis()
    ax.set_xlabel("Strings with at least one invariant defect (%)")
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    ax.set_xlim(0, max(llm.defect_rate_pct) * 1.15)
    ax.set_title("Defect rate by system (12 languages, 10,228 strings each)", loc="left", color=INK)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=C_BASE, label="Baseline (zero-shot)"),
                       Patch(color=C_REP, label="After compiler-guided repair")],
              frameon=False, loc="lower right", fontsize=8)
    note(fig, missing)
    save(fig, "fig1_defect_rate_by_system.png")


def fig2(bs, missing):
    llm = bs[bs.family == "LLM"]
    nmt = bs[bs.family == "NMT"].sort_values("cometkiwi_mean", ascending=False)
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    for _, r in nmt.iterrows():
        ax.axhline(r.cometkiwi_mean, color=C_NMT, lw=1, ls=(0, (4, 3)), alpha=0.9, zorder=1)
    # NMT line labels, nudged apart so they do not overlap
    ys = list(nmt.cometkiwi_mean); placed = []
    for v in ys:
        p = v
        while any(abs(p - q) < 0.0034 for q in placed):
            p -= 0.0034
        placed.append(p)
    for (_, r), p in zip(nmt.iterrows(), placed):
        lab = r.label + (" (6 Indic langs)" if r.n_languages < 12 else "")
        ax.text(1.01, p, f"{lab}  {r.cometkiwi_mean:.3f}", transform=ax.get_yaxis_transform(),
                fontsize=7, color=INK2, va="center")
    for key, label in MODELS:
        b = llm[llm.system == f"baseline_{key}"].iloc[0]
        r = llm[llm.system == f"repaired_{key}"].iloc[0]
        ax.annotate("", xy=(r.defect_rate_pct, r.cometkiwi_mean), xytext=(b.defect_rate_pct, b.cometkiwi_mean),
                    arrowprops=dict(arrowstyle="-|>", color=AXIS, lw=1, shrinkA=5, shrinkB=5), zorder=2)
        ax.scatter(b.defect_rate_pct, b.cometkiwi_mean, s=46, color=C_BASE, edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.scatter(r.defect_rate_pct, r.cometkiwi_mean, s=46, color=C_REP, edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.text(b.defect_rate_pct * 1.12, b.cometkiwi_mean - 0.0035, label, fontsize=7.5, color=INK2)
    ax.set_xscale("log")
    from matplotlib.ticker import NullFormatter, NullLocator
    lo, hi = llm.defect_rate_pct.min(), llm.defect_rate_pct.max()
    ticks = [t for t in (0.1, 0.2, 0.5, 1, 2, 3, 5, 10, 20, 30, 50) if lo * 0.8 <= t <= hi * 1.25]
    ax.set_xlim(lo * 0.8, hi * 1.25)
    ax.xaxis.set_minor_locator(NullLocator()); ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.set_xlabel("Defect rate (% of strings, log scale)  -  lower is safer")
    ax.set_ylabel("Mean CometKiwi (wmt22-cometkiwi-da)  -  higher is better")
    ax.set_title("Quality vs. string safety", loc="left", color=INK)
    ax.scatter([], [], s=46, color=C_BASE, label="LLM baseline")
    ax.scatter([], [], s=46, color=C_REP, label="LLM + repair")
    ax.plot([], [], color=C_NMT, ls=(0, (4, 3)), label="NMT CometKiwi (defect rate pending)")
    ax.legend(frameon=False, loc="lower left", fontsize=7.5)
    note(fig, missing)
    save(fig, "fig2_quality_vs_defects.png")


def fig3(mt, missing):
    d = mt[mt.defect_data_available]
    order = [f"{t}_{k}" for t in ("baseline", "repaired") for k, _ in MODELS]
    labels = dict(zip(d.system, d.label))
    piv = d.pivot(index="system", columns="lang", values="defect_rate_pct").loc[order]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    cmap = LinearSegmentedColormap.from_list("seq_blue", SEQ)
    vals = piv.values.clip(min=0.01)
    im = ax.imshow(vals, cmap=cmap, norm=LogNorm(vmin=0.01, vmax=100), aspect="auto")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = piv.values[i, j]
            ax.text(j, i, f"{v:.1f}" if v >= 1 else f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                    color="#ffffff" if v >= 3 else INK)
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), [labels[s] for s in piv.index])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.axhline(4.5, color=SURFACE, lw=3)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("Defect rate (%, log scale)", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("Defect rate by language (%)", loc="left", color=INK)
    note(fig, missing)
    save(fig, "fig3_defect_heatmap_by_lang.png")


def fig4(bs, missing):
    llm = bs[bs.family == "LLM"].copy()
    order = [f"{t}_{k}" for t in ("baseline", "repaired") for k, _ in MODELS]
    llm = llm.set_index("system").loc[order]
    groups = pd.DataFrame({
        "Copy fallback": llm.copy_fallback,
        "Broken placeholder": llm.broken_placeholder,
        "Broken accelerator": llm.broken_accelerator,
        "Script contamination": llm.script_contamination,
        "Encoding corruption": llm.encoding_corruption,
        "Other": llm.conversational_chatter + llm.empty_output,
    })
    share = groups.div(groups.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    left = np.zeros(len(share))
    y = np.arange(len(share))
    for col in share.columns:
        ax.barh(y, share[col], left=left, color=TYPE_COLORS[col], edgecolor=SURFACE, linewidth=1.5,
                height=0.66, label=col)
        left += share[col].values
    for i, s in enumerate(share.index):
        ax.text(101.5, i, f"n = {int(groups.loc[s].sum()):,}", va="center", fontsize=7, color=INK2)
    ax.set_yticks(y, llm.label)
    ax.invert_yaxis()
    ax.axhline(4.5, color=AXIS, lw=0.8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of defect occurrences (%)  -  a string can carry more than one type")
    ax.set_title("Defect taxonomy by system", loc="left", color=INK, pad=34)
    ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=7.5)
    note(fig, missing)
    save(fig, "fig4_defect_taxonomy.png")


def main():
    FIGS.mkdir(parents=True, exist_ok=True)
    mt = pd.read_csv(RESULTS / "master_table.csv")
    bs = pd.read_csv(RESULTS / "master_table_by_system.csv")
    missing = bs.loc[~bs.defect_data_available, "label"].tolist()
    print("Generating figures (300 DPI)...")
    fig1(bs, missing); fig2(bs, missing); fig3(mt, missing); fig4(bs, missing)
    print(f"Done. Systems without defect data: {missing if missing else 'none'}")


if __name__ == "__main__":
    main()
