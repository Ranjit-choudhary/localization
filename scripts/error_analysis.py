"""
String-type, failure-mode and latency analysis for all systems (NMT, LLM and the
Google baseline). Quantifies the NMT paper's qualitative string-type section and
adds the failure modes specific to generative LLMs.

A. Artifact preservation (% of source strings of a type whose artifact survives):
     placeholder  %1, %s, {name} ...  every token present in output (multiset)
     accelerator  '&' (excluding '& entity;')  output still contains '&'
     identifier   camelCase / snake_case token  copied verbatim
     colon        trailing ':'  output ends with ':' or full-width '：'
     ellipsis     trailing '...'  output ends with '...', '…' or '。。。'
B. Quality by string type / length: mean sentence chrF++ per category
   (needs metrics/sentence_level/chrf_sentence.csv.gz from significance.py; LLM + NMT only).
C. Failure modes (% of strings):
     empty            no output
     untranslated     output == source although the Google baseline translated it
     wrong_script     <50% of letters in the target script although the Google
                      output is in the target script (non-Latin targets only)
     script_intrusion letters from a script that is neither Latin nor the target's
     overgeneration   output > 3x the baseline length and > 15 chars longer
     meta_commentary  'translation'/'note:'-style commentary absent from the source
     corrupt_char     U+FFFD replacement character (broken byte sequence)
D. Latency (LLM runs; per-string wall time recorded by test_run.py).

Outputs: metrics/analysis/*.csv, tables/tab_artifacts.tex, tab_failures.tex,
tab_latency.tex, figures/fig_artifact_preservation, fig_failure_modes,
fig_latency_by_language, fig_chrf_by_string_type.

Usage:
    python scripts/error_analysis.py
"""
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import (BASELINE, COLORS, DATA, DISPLAY, FIGURES, LANGS, LANG_NAMES, LLM_SYSTEMS,
                    METRICS, NMT_SYSTEMS, PRIMARY_LLM, TABLES, ensure_dirs, load_lines,
                    load_reference, load_source, supports)
import analysis  # noqa: F401  (applies the shared matplotlib style)
from analysis import save

OUT = METRICS / "analysis"
SYSTEMS = [BASELINE] + NMT_SYSTEMS + LLM_SYSTEMS

PLACEHOLDER = re.compile(r"%\d+|%[a-zA-Z]|\{\w*\}")
ENTITY = re.compile(r"&\s?[\w-]+;")
IDENT = re.compile(r"\b[a-z]+[A-Z]\w*|\b[A-Z][a-z]+[A-Z]\w*|\b\w+_\w+\b")
COMMENTARY = re.compile(r"(?i)\btranslat(?:ion|ed|e)\b|\bnote\s*:|翻译|翻訳")

SCRIPT = {
    "hi": r"ऀ-ॿ", "mr": r"ऀ-ॿ", "bn": r"ঀ-৿",
    "pa": r"਀-੿", "ta": r"஀-௿", "te": r"ఀ-౿",
    "ar": r"؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿",
    "zh": r"一-鿿㐀-䶿", "ja": r"぀-ヿ一-鿿㐀-䶿ｦ-ﾟ",
}
LATIN = r"A-Za-zÀ-ɏ"


def script_ratio(text, rng):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    return sum(bool(re.match(f"[{rng}]", c)) for c in letters) / len(letters)


def intrusion(text, lang):
    allowed = LATIN + SCRIPT.get(lang, "")
    return any(c.isalpha() and not re.match(f"[{allowed}]", c) for c in text)


def categories(src):
    return {
        "placeholder": bool(PLACEHOLDER.search(src)),
        "accelerator": "&" in ENTITY.sub("", src),
        "identifier": bool(IDENT.search(src)),
        "colon": src.rstrip().endswith(":"),
        "ellipsis": src.rstrip().endswith("..."),
    }


def preserved(cat, src, hyp):
    h = hyp.rstrip()
    if cat == "placeholder":
        need = PLACEHOLDER.findall(src)
        return all(hyp.count(t) >= need.count(t) for t in set(need))
    if cat == "accelerator":
        return "&" in hyp
    if cat == "identifier":
        return all(t in hyp for t in IDENT.findall(src))
    if cat == "colon":
        return h.endswith(":") or h.endswith("：")
    if cat == "ellipsis":
        return h.endswith("...") or h.endswith("…") or h.endswith("。。。")


def length_bucket(src):
    n = len(src.split())
    return "1 word" if n <= 1 else "2-3 words" if n <= 3 else "4+ words"


def analyse_strings(src):
    cats = [categories(s) for s in src]
    art_rows, fail_rows = [], []
    for system in SYSTEMS:
        for lang in LANGS:
            if not supports(system, lang):
                continue
            hyp = load_lines(system, lang)
            ref = load_reference(lang)
            for cat in cats[0]:
                idx = [i for i, c in enumerate(cats) if c[cat]]
                ok = sum(preserved(cat, src[i], hyp[i]) for i in idx)
                art_rows.append({"system": system, "lang": lang, "category": cat, "n": len(idx),
                                 "preserved_pct": 100 * ok / len(idx)})

            f = dict.fromkeys(["empty", "untranslated", "wrong_script", "script_intrusion",
                               "overgeneration", "meta_commentary", "corrupt_char"], 0)
            for s, h, r in zip(src, hyp, ref):
                if not h:
                    f["empty"] += 1
                    continue
                f["untranslated"] += h == s and r != s
                if lang in SCRIPT:
                    rh, rr = script_ratio(h, SCRIPT[lang]), script_ratio(r, SCRIPT[lang])
                    f["wrong_script"] += rh is not None and rr is not None and rr >= 0.5 and rh < 0.5
                f["script_intrusion"] += intrusion(h, lang) and not intrusion(s, lang)
                f["overgeneration"] += len(h) > 3 * len(r) and len(h) - len(r) > 15
                f["meta_commentary"] += bool(COMMENTARY.search(h)) and not COMMENTARY.search(s)
                f["corrupt_char"] += "�" in h
            fail_rows.append({"system": system, "lang": lang, "n": len(src),
                              **{k: 100 * v / len(src) for k, v in f.items()}})
        print(f"[strings] {system} done")
    art = pd.DataFrame(art_rows)
    fail = pd.DataFrame(fail_rows)
    art.to_csv(OUT / "artifact_preservation_by_language.csv", index=False, float_format="%.3f")
    fail.to_csv(OUT / "failure_modes_by_language.csv", index=False, float_format="%.4f")
    return art, fail


def order(idx):
    return [s for s in SYSTEMS if s in idx]


def latex(df, path, caption, label, fmt="{:.1f}"):
    cols = list(df.columns)
    lines = ["\\begin{table*}[t]", "\\centering", f"\\caption{{{caption}\\label{{{label}}}}}",
             "\\begin{tabular}{l" + "r" * len(cols) + "}", "\\toprule",
             "System & " + " & ".join(c.replace("_", " ") for c in cols) + " \\\\", "\\midrule"]
    for idx, row in df.iterrows():
        lines.append(f"{DISPLAY.get(idx, idx)} & " +
                     " & ".join("--" if pd.isna(v) else fmt.format(v) for v in row) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def grouped_bars(df, ylabel, name, log=False):
    systems = order(df.index)
    cats = list(df.columns)
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    w = 0.8 / len(systems)
    x = np.arange(len(cats))
    for i, s in enumerate(systems):
        ax.bar(x + (i - (len(systems) - 1) / 2) * w, df.loc[s].values, w * 0.9, color=COLORS[s],
               label=DISPLAY[s], edgecolor="white", linewidth=0.4)
    ax.set_xticks(x, [c.replace("_", " ") for c in cats])
    ax.set_ylabel(ylabel)
    if log:
        ax.set_yscale("symlog", linthresh=0.1)
    ax.legend(ncol=4, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    save(fig, name)


def by_string_type(src):
    sent = METRICS / "sentence_level" / "chrf_sentence.csv.gz"
    if not sent.exists():
        print("[skip] sentence-level chrF++ not found; run significance.py first")
        return
    s = pd.read_csv(sent)
    lab = pd.DataFrame([categories(x) for x in src])
    lab["length"] = [length_bucket(x) for x in src]
    lab["line"] = np.arange(1, len(src) + 1)
    m = s.merge(lab, on="line")
    rows = []
    for cat in ["placeholder", "accelerator", "identifier", "colon", "ellipsis"]:
        g = m[m[cat]].groupby("system").chrf.mean()
        rows.append(g.rename(cat))
    for b in ["1 word", "2-3 words", "4+ words"]:
        rows.append(m[m.length == b].groupby("system").chrf.mean().rename(b))
    rows.append(m.groupby("system").chrf.mean().rename("all"))
    t = pd.concat(rows, axis=1).reindex(order(set(m.system)))
    t.to_csv(OUT / "chrf_by_string_type.csv", float_format="%.3f")
    print("\nMean sentence chrF++ by string type (all languages pooled):\n" + t.round(1).to_string())
    grouped_bars(t.drop(columns="all"), "Mean sentence chrF++", "fig_chrf_by_string_type")


def latency():
    rows = []
    for system in LLM_SYSTEMS:
        p = DATA / system / "latency.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d["system"] = system
        rows.append(d)
    if not rows:
        return
    d = pd.concat(rows)
    d = d[d.system == PRIMARY_LLM]
    stat = d.groupby("lang").latency_sec.agg(
        mean="mean", median="median", p95=lambda x: x.quantile(0.95), total_h=lambda x: x.sum() / 3600)
    stat.loc["all"] = [d.latency_sec.mean(), d.latency_sec.median(), d.latency_sec.quantile(0.95),
                       d.latency_sec.sum() / 3600]
    stat["strings_per_min"] = 60 / stat["mean"]
    stat = stat.reindex(LANGS + ["all"])
    stat.to_csv(OUT / "latency_summary.csv", float_format="%.3f")
    t = stat.copy()
    t.index = [LANG_NAMES.get(i, "All languages") for i in t.index]
    lines = ["\\begin{table}[t]", "\\centering",
             f"\\caption{{Per-string inference latency of {DISPLAY[PRIMARY_LLM]} (seconds, local Ollama, "
             "temperature 0).\\label{tab:latency}}", "\\begin{tabular}{lrrrrr}", "\\toprule",
             "Language & Mean & Median & P95 & Total (h) & Strings/min \\\\", "\\midrule"]
    for i, r in t.iterrows():
        lines.append(f"{i} & {r['mean']:.2f} & {r['median']:.2f} & {r.p95:.2f} & {r.total_h:.2f} & "
                     f"{r.strings_per_min:.0f} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    (TABLES / "tab_latency.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nLatency (s):\n" + stat.round(2).to_string())

    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    data = [d[d.lang == l].latency_sec.values for l in LANGS]
    bp = ax.boxplot(data, showfliers=False, widths=0.5, patch_artist=True,
                    medianprops={"color": "#1a1a19", "linewidth": 1})
    for b in bp["boxes"]:
        b.set(facecolor=COLORS[PRIMARY_LLM], edgecolor="#5f5e5a", linewidth=0.6)
    ax.set_xticks(range(1, len(LANGS) + 1), [LANG_NAMES[l] for l in LANGS], rotation=30, ha="right")
    ax.set_ylabel("Seconds per string")
    ax.set_title(f"{DISPLAY[PRIMARY_LLM]} latency by target language (outliers hidden)")
    save(fig, "fig_latency_by_language")


def main():
    ensure_dirs()
    src = load_source()
    art, fail = analyse_strings(src)

    a = art.groupby(["system", "category"]).preserved_pct.mean().unstack().reindex(order(set(art.system)))
    n = art.drop_duplicates("category").set_index("category").n
    a.columns = [f"{c} (n={n[c]})" for c in a.columns]
    a.to_csv(OUT / "artifact_preservation.csv", float_format="%.2f")
    latex(a, TABLES / "tab_artifacts.tex",
          "Artifact preservation rate (\\%, mean over supported languages). n = source strings of each type.",
          "tab:artifacts")
    grouped_bars(a, "Preserved (%)", "fig_artifact_preservation")
    print("\nArtifact preservation (%):\n" + a.round(1).to_string())

    f = fail.groupby("system")[[c for c in fail.columns if c not in ("system", "lang", "n")]].mean()
    f = f.reindex(order(f.index))
    f.to_csv(OUT / "failure_modes.csv", float_format="%.4f")
    latex(f, TABLES / "tab_failures.tex",
          "Failure modes (\\% of strings, mean over supported languages).", "tab:failures", fmt="{:.2f}")
    grouped_bars(f, "% of strings (symlog)", "fig_failure_modes", log=True)
    print("\nFailure modes (% of strings):\n" + f.round(3).to_string())

    by_string_type(src)
    latency()


if __name__ == "__main__":
    main()
