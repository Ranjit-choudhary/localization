"""
Publication figures (300 DPI PNG) for Paper 1.

Reads results/master_table.csv and results/master_table_by_system.csv
(build_master_table.py output) and writes to paper1_llm_vs_nmt/figures/:

  fig1_defect_rate_by_system.png   defect rate of all 15 suites, sorted, grouped by family
  fig2_quality_vs_defects.png      CometKiwi vs defect rate (LLM baseline -> repair arrows + NMT)
  fig3_defect_heatmap_by_lang.png  defect rate, system x language
  fig4_defect_taxonomy.png         defect-type mix per system

Systems without string-level defect data are left out of the defect axes and named
in a footnote.

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
from matplotlib.patches import Patch
from matplotlib.ticker import NullFormatter, NullLocator

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
EMPTY = "#f0efec"
C_BASE = "#eb6834"   # slot 2 orange -> baseline LLM
C_REP = "#2a78d6"    # slot 1 blue   -> repaired LLM
C_NMT = "#1baf7a"    # slot 3 aqua   -> NMT
FAMILY_COLOR = {"baseline": C_BASE, "repaired": C_REP, "commercial": C_NMT, "open": C_NMT}
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
TYPE_COLORS = {"Broken accelerator": "#e87ba4", "Copy fallback": "#2a78d6",
               "Broken placeholder": "#eb6834", "Script contamination": "#1baf7a",
               "Encoding corruption": "#eda100", "Other": "#898781"}

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
NMT_ORDER = ["google_translate", "microsoft_translator", "nllb200", "madlad400", "indictrans2"]
GROUP_ROWS = ([f"baseline_{k}" for k, _ in MODELS] + [f"repaired_{k}" for k, _ in MODELS] + NMT_ORDER)


def short(row):
    lab = row.label
    return lab + " (6 langs)" if row.n_languages < 12 else lab


def note(fig, missing):
    if missing:
        fig.text(0.01, -0.035, "Not shown (no string-level outputs): " + ", ".join(missing),
                 fontsize=7, color=MUTED, ha="left", va="bottom")


def save(fig, name):
    fig.savefig(FIGS / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote figures/{name}")


def family_legend(ax, loc="lower right"):
    ax.legend(handles=[Patch(color=C_BASE, label="LLM, zero-shot"),
                       Patch(color=C_REP, label="LLM + compiler-guided repair"),
                       Patch(color=C_NMT, label="NMT")],
              frameon=False, loc=loc, fontsize=7.5)


def fig1(bs, missing):
    d = bs[bs.defect_data_available].sort_values("defect_rate_pct").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    y = np.arange(len(d))
    ax.barh(y, d.defect_rate_pct, height=0.68, color=[FAMILY_COLOR[t] for t in d.tier],
            edgecolor=SURFACE, linewidth=1)
    for i, r in d.iterrows():
        ax.text(r.defect_rate_pct + 0.25, i, f"{r.defect_rate_pct:.2f}%", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [short(r) for _, r in d.iterrows()])
    ax.invert_yaxis()
    ax.set_xlabel("Strings with at least one invariant defect (%)")
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    ax.set_xlim(0, d.defect_rate_pct.max() * 1.15)
    ax.set_title("Defect rate by system (10,228 strings x 12 languages)", loc="left", color=INK)
    family_legend(ax, loc="upper right")
    note(fig, missing)
    save(fig, "fig1_defect_rate_by_system.png")


# label offsets (points) for fig2, tuned to avoid collisions
NMT_OFF = {"google_translate": (-8, 3), "microsoft_translator": (6, -10), "nllb200": (6, -11),
           "madlad400": (7, -3), "indictrans2": (8, 1)}
LLM_OFF = {"gpt4o": (-4, 7)}


def fig2(bs, missing):
    llm = bs[bs.family == "LLM"]
    nmt = bs[(bs.family == "NMT") & bs.defect_data_available]
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    for key, label in MODELS:
        b = llm[llm.system == f"baseline_{key}"].iloc[0]
        r = llm[llm.system == f"repaired_{key}"].iloc[0]
        ax.annotate("", xy=(r.defect_rate_pct, r.cometkiwi_mean), xytext=(b.defect_rate_pct, b.cometkiwi_mean),
                    arrowprops=dict(arrowstyle="-|>", color=AXIS, lw=1, shrinkA=5, shrinkB=5), zorder=2)
        ax.scatter(b.defect_rate_pct, b.cometkiwi_mean, s=46, color=C_BASE, edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.scatter(r.defect_rate_pct, r.cometkiwi_mean, s=46, color=C_REP, edgecolor=SURFACE, lw=1.5, zorder=3)
        dx, dy = LLM_OFF.get(key, (6, -10))
        ax.annotate(label, (b.defect_rate_pct, b.cometkiwi_mean), xytext=(dx, dy), textcoords="offset points",
                    fontsize=7.5, color=INK2, ha="right" if dx < 0 else "left")
    for _, r in nmt.iterrows():
        ax.scatter(r.defect_rate_pct, r.cometkiwi_mean, s=52, marker="D", color=C_NMT, edgecolor=SURFACE,
                   lw=1.5, zorder=4)
        dx, dy = NMT_OFF.get(r.system, (6, 3))
        ax.annotate(short(r), (r.defect_rate_pct, r.cometkiwi_mean), xytext=(dx, dy), textcoords="offset points",
                    fontsize=7.5, color=INK2, ha="right" if dx < 0 else "left")
    allx = bs.loc[bs.defect_data_available, "defect_rate_pct"]
    lo, hi = allx.min(), allx.max()
    ax.set_xscale("log")
    ax.set_xlim(lo * 0.8, hi * 1.35)
    ticks = [t for t in (0.1, 0.2, 0.5, 1, 2, 3, 5, 10, 20, 30, 50) if lo * 0.8 <= t <= hi * 1.35]
    ax.xaxis.set_minor_locator(NullLocator()); ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.set_xlabel("Defect rate (% of strings, log scale)  -  lower is safer")
    ax.set_ylabel("Mean CometKiwi (wmt22-cometkiwi-da)  -  higher is better")
    ax.set_title("Quality vs. string safety", loc="left", color=INK)
    ax.scatter([], [], s=46, color=C_BASE, label="LLM, zero-shot")
    ax.scatter([], [], s=46, color=C_REP, label="LLM + repair")
    ax.scatter([], [], s=52, marker="D", color=C_NMT, label="NMT")
    ax.legend(frameon=False, loc="lower left", fontsize=7.5)
    note(fig, missing)
    save(fig, "fig2_quality_vs_defects.png")


def fig3(mt, bs, missing):
    d = mt[mt.defect_data_available]
    rows = [s for s in GROUP_ROWS if s in set(d.system)]
    lab = {r.system: short(r) for _, r in bs.iterrows()}
    piv = d.pivot(index="system", columns="lang", values="defect_rate_pct").reindex(rows)
    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    cmap = LinearSegmentedColormap.from_list("seq_blue", SEQ)
    cmap.set_bad(EMPTY)
    vals = np.ma.masked_invalid(piv.values.astype(float).clip(min=0.1))
    im = ax.imshow(vals, cmap=cmap, norm=LogNorm(vmin=0.1, vmax=100), aspect="auto")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if np.isnan(v):
                ax.text(j, i, "–", ha="center", va="center", fontsize=6.5, color=MUTED)
                continue
            ax.text(j, i, f"{v:.1f}" if v >= 1 else f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                    color="#ffffff" if v >= 3 else INK)
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), [lab[s] for s in piv.index])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for cut in (4.5, 9.5):
        ax.axhline(cut, color=SURFACE, lw=3)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("Defect rate (%, log scale)", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("Defect rate by language (%)", loc="left", color=INK)
    note(fig, missing)
    save(fig, "fig3_defect_heatmap_by_lang.png")


def fig4(bs, missing):
    d = bs[bs.defect_data_available].set_index("system")
    rows = [s for s in GROUP_ROWS if s in d.index]
    d = d.loc[rows]
    groups = pd.DataFrame({
        "Broken accelerator": d.broken_accelerator,
        "Copy fallback": d.copy_fallback,
        "Broken placeholder": d.broken_placeholder,
        "Script contamination": d.script_contamination,
        "Encoding corruption": d.encoding_corruption,
        "Other": d.conversational_chatter + d.empty_output,
    })
    share = groups.div(groups.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(7.0, 5.4))
    left = np.zeros(len(share))
    y = np.arange(len(share))
    for col in share.columns:
        ax.barh(y, share[col], left=left, color=TYPE_COLORS[col], edgecolor=SURFACE, linewidth=1.5,
                height=0.66, label=col)
        left += share[col].values
    for i, s in enumerate(share.index):
        ax.text(101.5, i, f"n = {int(groups.loc[s].sum()):,}", va="center", fontsize=7, color=INK2)
    ax.set_yticks(y, [short(r) for _, r in d.reset_index().iterrows()])
    ax.invert_yaxis()
    for cut in (4.5, 9.5):
        ax.axhline(cut, color=AXIS, lw=0.8)
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
    fig1(bs, missing); fig2(bs, missing); fig3(mt, bs, missing); fig4(bs, missing)
    print(f"Done. Systems without defect data: {missing if missing else 'none'}")


if __name__ == "__main__":
    main()
