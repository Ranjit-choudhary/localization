"""
Convert raw LLM run CSVs (translations_<language>.csv, produced by test_run.py)
into the aligned one-string-per-line format used by the NMT benchmark repo:

    data/<system>/<lang>.txt        10,228 lines, line N <-> data/source/en.txt line N
    data/<system>/latency.csv       lang, line, latency_sec (per-string wall time)
    data/<system>/MISSING.csv       lines with no usable output (to fill / report)

Alignment
---------
test_run.py read Dataset-Translated.xlsx with pandas defaults and called
.dropna() on the first column, then enumerated the survivors as string_id.
That dropped 6 of the 10,231 spreadsheet rows:
    - 3 genuinely empty rows (spreadsheet rows 5388, 9698, 10185, 0-based),
      which the NMT repo also removed (remove_empty_lines.py: lines 5389,
      9699, 10186, 1-based) -> 10,228-line corpus;
    - 3 rows holding the literal string '#ERROR!' that pandas parses as NaN.
      These ARE in en.txt and were never sent to the LLM; they are written as
      empty lines and listed in MISSING.csv (reason=not_sent).
string_id k therefore maps to spreadsheet row idx[k] (k-th non-NaN row) and
to en.txt line idx[k] minus the number of removed empty rows above it. The
mapping is verified against en.txt (whitespace/case-normalised) and the
script aborts on any mismatch.

Output normalisation
--------------------
One string per line is required, so embedded newlines (LLM commentary such as
'\n(Translation of "X" to Tamil is ...)') are flattened to a single space.
This is the PRIMARY (raw) system. With --clean-variant a second system
<system>_clean is also written, keeping only the first line and stripping
wrapping quotes; it is a post-processing ablation, not the system as run.

Usage:
    python scripts/prepare_llm_outputs.py --raw-dir Qwen2.5 --system qwen25_coder_7b --clean-variant
"""
import argparse
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / "data" / "source" / "en.txt"
XLSX = BASE / "Dataset-Translated.xlsx"

REMOVED_EMPTY_ROWS = [5388, 9698, 10185]  # 0-based spreadsheet data rows
N_LINES = 10228

LANG_FILES = {
    "hi": "hindi", "es": "spanish", "fr": "french", "ja": "japanese",
    "ar": "arabic", "bn": "bengali", "de": "german", "mr": "marathi",
    "pa": "punjabi", "ta": "tamil", "te": "telugu", "zh": "chinese",
}


def norm(s):
    return " ".join(str(s).split()).lower()


def flatten(s):
    return " ".join(str(s).split())


def clean(s):
    """First non-empty line, with wrapping quotes removed."""
    for line in str(s).split("\n"):
        line = line.strip().strip("\"'“”").strip()
        if line:
            return line
    return ""


def string_id_to_line():
    """Reproduce test_run.py's enumeration and map each string_id to an en.txt index."""
    col = pd.read_excel(XLSX).iloc[:, 0]
    for r in REMOVED_EMPTY_ROWS:
        assert pd.isna(col.iloc[r]), f"expected empty spreadsheet row {r}"
    rows = col.dropna().index.tolist()
    return [r - sum(x < r for x in REMOVED_EMPTY_ROWS) for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True, help="folder of translations_<language>.csv")
    ap.add_argument("--system", required=True, help="output system name, e.g. qwen25_coder_7b")
    ap.add_argument("--clean-variant", action="store_true", help="also write <system>_clean")
    args = ap.parse_args()

    en = SOURCE.read_text(encoding="utf-8").split("\n")[:-1]
    assert len(en) == N_LINES, len(en)
    id2line = string_id_to_line()

    raw_dir = BASE / args.raw_dir
    out = BASE / "data" / args.system
    out.mkdir(parents=True, exist_ok=True)
    out_clean = BASE / "data" / f"{args.system}_clean"
    if args.clean_variant:
        out_clean.mkdir(parents=True, exist_ok=True)

    missing, latency = [], []
    for lang, name in LANG_FILES.items():
        f = raw_dir / f"translations_{name}.csv"
        if not f.exists():
            print(f"[skip] {f.name} not found")
            continue
        df = pd.read_csv(f, keep_default_na=False, dtype={"translation": str, "source_en": str})
        hyp = [None] * N_LINES
        for r in df.itertuples():
            line = id2line[int(r.string_id)]
            if norm(r.source_en) != norm(en[line]):
                raise SystemExit(f"ABORT {f.name}: string_id {r.string_id} != en.txt line {line + 1}")
            hyp[line] = r.translation
            latency.append({"lang": lang, "line": line + 1, "latency_sec": r.latency_sec})

        for i, h in enumerate(hyp):
            if h is None:
                missing.append({"lang": lang, "line": i + 1, "source": en[i], "reason": "not_sent"})
            elif h.strip() == "":
                missing.append({"lang": lang, "line": i + 1, "source": en[i], "reason": "empty_output"})

        # Re-apply lines produced by fill_missing_llm.py (logged in FILLED.csv),
        # so re-running this script never discards them.
        filled = out / "FILLED.csv"
        if filled.exists():
            fl = pd.read_csv(filled, keep_default_na=False, dtype={"output": str})
            for r in fl[fl.lang == lang].itertuples():
                hyp[r.line - 1] = r.output

        raw_lines = [flatten(h) if h else "" for h in hyp]
        (out / f"{lang}.txt").write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        if args.clean_variant:
            cl = [clean(h) if h else "" for h in hyp]
            (out_clean / f"{lang}.txt").write_text("\n".join(cl) + "\n", encoding="utf-8")
        n_nl = sum(1 for h in hyp if h and "\n" in h.strip())
        print(f"[done] {lang}: {sum(h is not None for h in hyp)} rows mapped, "
              f"{sum(1 for h in hyp if h is not None and not h.strip())} empty, {n_nl} multi-line")

    # MISSING.csv always describes the ORIGINAL run (before filling).
    pd.DataFrame(missing).to_csv(out / "MISSING.csv", index=False)
    pd.DataFrame(latency).sort_values(["lang", "line"]).to_csv(out / "latency.csv", index=False)
    print(f"\nMissing/empty lines in original run: {len(missing)} -> {out / 'MISSING.csv'}")
    if (out / "FILLED.csv").exists():
        print("Filled lines from FILLED.csv applied.")


if __name__ == "__main__":
    main()
