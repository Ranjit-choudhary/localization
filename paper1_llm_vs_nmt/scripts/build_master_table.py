"""
Week 2 - Build the master table for Paper 1 (LLM vs NMT).

Merges, per (system, language):
  * invariant defect counts/rates from results/defect_summary.csv (audit.py output)
  * CometKiwi (Unbabel/wmt22-cometkiwi-da) mean scores from both repos

Inputs (read-only):
  paper1_llm_vs_nmt/results/defect_summary.csv
  cloud-native-llm-benchmark-main/.../metrics/cometkiwi/cometkiwi_scores.csv
  cloud-native-nmt-benchmark-main/metrics/cometkiwi/cometkiwi_scores.csv

Outputs (overwritten):
  results/master_table.csv            one row per system x language
  results/master_table_by_system.csv  one row per system

NMT defect columns stay empty until Track 1 provides the NMT translation files
(cloud-native-nmt-benchmark-main/data/*.txt are 0-byte stubs). The ../dump folder
is never used.

Run:  python paper1_llm_vs_nmt/scripts/build_master_table.py
"""
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "paper1_llm_vs_nmt" / "results"
LLM_CK = ROOT / "cloud-native-llm-benchmark-main" / "cloud-native-llm-benchmark-main" / "metrics" / "cometkiwi" / "cometkiwi_scores.csv"
NMT_CK = ROOT / "cloud-native-nmt-benchmark-main" / "metrics" / "cometkiwi" / "cometkiwi_scores.csv"

HIGH_RESOURCE = {"de", "fr", "zh", "es", "ja"}  # as defined in the Track 1 paper
LANGS = ["ar", "bn", "de", "es", "fr", "hi", "ja", "mr", "pa", "ta", "te", "zh"]

# audit directory name -> canonical system name used in the paper
NMT_ALIASES = {"baseline_google_translate": "google_translate"}

SYSTEM_INFO = {
    # system: (family, tier, display label)
    "baseline_gpt4o":        ("LLM", "baseline", "GPT-4o-mini"),
    "baseline_llama_8b":     ("LLM", "baseline", "Llama-3.1-8B"),
    "baseline_mistral_nemo": ("LLM", "baseline", "Mistral-Nemo-12B"),
    "baseline_gemma_9b":     ("LLM", "baseline", "Gemma-2-9B"),
    "baseline_qwen_7b":      ("LLM", "baseline", "Qwen-2.5-7B"),
    "repaired_gpt4o":        ("LLM", "repaired", "GPT-4o-mini + repair"),
    "repaired_llama_8b":     ("LLM", "repaired", "Llama-3.1-8B + repair"),
    "repaired_mistral_nemo": ("LLM", "repaired", "Mistral-Nemo-12B + repair"),
    "repaired_gemma_9b":     ("LLM", "repaired", "Gemma-2-9B + repair"),
    "repaired_qwen_7b":      ("LLM", "repaired", "Qwen-2.5-7B + repair"),
    "google_translate":      ("NMT", "commercial", "Google Translate"),
    "microsoft_translator":  ("NMT", "commercial", "Microsoft Translator"),
    "nllb200":               ("NMT", "open", "NLLB-200 (600M)"),
    "madlad400":             ("NMT", "open", "MADLAD-400 (3B)"),
    "indictrans2":           ("NMT", "open", "IndicTrans2 (1B)"),
}

DEFECT_COLS = ["script_contamination", "broken_placeholder", "broken_accelerator",
               "encoding_corruption", "conversational_chatter", "copy_fallback",
               "empty_output", "total_flawed"]


def main():
    defects = pd.read_csv(RESULTS / "defect_summary.csv")
    defects["system"] = defects["system"].replace(NMT_ALIASES)
    defects = defects.rename(columns={"total_strings": "n_strings_audited"})

    llm_ck = pd.read_csv(LLM_CK).rename(columns={"language": "lang"})[["system", "lang", "cometkiwi"]]
    nmt_ck = pd.read_csv(NMT_CK)[["system", "lang", "cometkiwi"]]
    ck = pd.concat([llm_ck, nmt_ck], ignore_index=True)

    # Full grid of every known system x language it covers (from either source)
    keys = pd.concat([defects[["system", "lang"]], ck[["system", "lang"]]]).drop_duplicates()
    master = keys.merge(defects, on=["system", "lang"], how="left").merge(ck, on=["system", "lang"], how="left")

    unknown = set(master["system"]) - set(SYSTEM_INFO)
    if unknown:
        raise ValueError(f"Systems missing from SYSTEM_INFO: {unknown}")

    master["family"] = master["system"].map(lambda s: SYSTEM_INFO[s][0])
    master["tier"] = master["system"].map(lambda s: SYSTEM_INFO[s][1])
    master["label"] = master["system"].map(lambda s: SYSTEM_INFO[s][2])
    master["resource"] = master["lang"].map(lambda l: "high" if l in HIGH_RESOURCE else "low")
    master["cometkiwi"] = master["cometkiwi"].round(4)
    master["defect_data_available"] = master["total_flawed"].notna()

    order = list(SYSTEM_INFO)
    master["_o"] = master["system"].map(order.index)
    master = master.sort_values(["_o", "lang"]).drop(columns="_o")
    cols = ["system", "label", "family", "tier", "lang", "resource", "n_strings_audited",
            *DEFECT_COLS, "defect_rate_pct", "cometkiwi", "defect_data_available"]
    master = master[cols]
    master.to_csv(RESULTS / "master_table.csv", index=False, encoding="utf-8")

    # System-level roll-up
    rows = []
    for sysname in order:
        g = master[master["system"] == sysname]
        if g.empty:
            continue
        has_def = g["defect_data_available"].all()
        row = {"system": sysname, "label": SYSTEM_INFO[sysname][2],
               "family": SYSTEM_INFO[sysname][0], "tier": SYSTEM_INFO[sysname][1],
               "n_languages": len(g)}
        if has_def:
            n = g["n_strings_audited"].sum()
            row["n_strings_audited"] = int(n)
            for c in DEFECT_COLS:
                row[c] = int(g[c].sum())
            row["defect_rate_pct"] = round(row["total_flawed"] / n * 100, 2)
            hi = g[g.resource == "high"]; lo = g[g.resource == "low"]
            row["defect_rate_high_pct"] = round(hi["total_flawed"].sum() / hi["n_strings_audited"].sum() * 100, 2) if len(hi) else None
            row["defect_rate_low_pct"] = round(lo["total_flawed"].sum() / lo["n_strings_audited"].sum() * 100, 2) if len(lo) else None
        row["cometkiwi_mean"] = round(g["cometkiwi"].mean(), 4)
        row["cometkiwi_high"] = round(g[g.resource == "high"]["cometkiwi"].mean(), 4) if (g.resource == "high").any() else None
        row["cometkiwi_low"] = round(g[g.resource == "low"]["cometkiwi"].mean(), 4) if (g.resource == "low").any() else None
        row["defect_data_available"] = has_def
        rows.append(row)
    by_sys = pd.DataFrame(rows)
    by_sys.to_csv(RESULTS / "master_table_by_system.csv", index=False, encoding="utf-8")

    print(f"master_table.csv: {len(master)} rows "
          f"({master['defect_data_available'].sum()} with defect data, "
          f"{master['cometkiwi'].notna().sum()} with CometKiwi)")
    show = by_sys[["label", "n_languages", "defect_rate_pct", "cometkiwi_mean", "cometkiwi_high", "cometkiwi_low"]]
    print(show.to_string(index=False))
    missing = by_sys.loc[~by_sys["defect_data_available"], "label"].tolist()
    if missing:
        print(f"\nNo defect data yet (translation files missing): {', '.join(missing)}")


if __name__ == "__main__":
    main()
