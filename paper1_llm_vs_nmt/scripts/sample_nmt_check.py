"""
Draw a validation sample of NMT audit flags (50 flagged + 25 unflagged, seed 42)
-> results/manual_check_sample_nmt.csv. Only written if the file does not exist
(it holds grades); pass --new-sample to redraw.

Run:  python paper1_llm_vs_nmt/scripts/sample_nmt_check.py
"""
import sys, random, argparse
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "paper1_llm_vs_nmt" / "results"
DATA = ROOT / "nmt-benchmarking-paper-main" / "data"
NMT = ["baseline_google_translate", "microsoft_translator", "nllb200", "madlad400", "indictrans2"]

ap = argparse.ArgumentParser(); ap.add_argument("--new-sample", action="store_true"); args = ap.parse_args()
out = RESULTS / "manual_check_sample_nmt.csv"
if out.exists() and not args.new_sample:
    print(f"Kept existing graded sample {out}"); sys.exit(0)

src = [l.rstrip("\r\n") for l in open(DATA / "source" / "en.txt", encoding="utf-8")]
dps = pd.read_csv(RESULTS / "defects_per_string.csv")
flags = {(r.system, r.lang, r.line_id): r.defect_types for r in dps.itertuples()}
flagged, clean = [], []
for s in NMT:
    for f in sorted((DATA / s).glob("*.txt")):
        hyp = [l.rstrip("\r\n") for l in open(f, encoding="utf-8")]
        for i, h in enumerate(hyp):
            key = (s, f.stem, i + 1)
            row = {"system": s, "lang": f.stem, "line_id": i + 1, "source": src[i], "output": h,
                   "flagged_type": flags.get(key, "none")}
            (flagged if key in flags else clean).append(row)
random.seed(42)
rows = random.sample(flagged, 50) + random.sample(clean, 25)
random.shuffle(rows)
df = pd.DataFrame(rows); df["model_verdict"] = ""; df["model_note"] = ""; df["my_verdict"] = ""
df.to_csv(out, index=False, encoding="utf-8")
print(f"Saved {out} ({len(df)} rows)")
