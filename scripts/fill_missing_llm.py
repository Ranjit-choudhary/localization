"""
Fill the lines listed in data/<system>/MISSING.csv by querying the same Ollama
model with the SAME system prompt and decoding options as test_run.py.

- reason=not_sent     : string was never sent in the original run (translated now)
- reason=empty_output : model returned "" in the original run (retried once; with
                        temperature 0 it usually returns "" again, which is kept
                        as the system's genuine output)

Every attempt is logged to data/<system>/FILLED.csv so the paper can report
exactly which lines were produced in the follow-up run.

Usage:
    python scripts/fill_missing_llm.py --system qwen25_coder_7b --model qwen2.5-coder:7b
"""
import argparse
import datetime
import time
from pathlib import Path

import ollama
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

LANG_NAMES = {
    "hi": "Hindi", "es": "Spanish", "fr": "French", "ja": "Japanese",
    "ar": "Arabic", "bn": "Bengali", "de": "German", "mr": "Marathi",
    "pa": "Punjabi", "ta": "Tamil", "te": "Telugu", "zh": "Chinese",
}

# Identical to test_run.py
SYSTEM_PROMPT = """You are an expert software localization engine.
Translate the user interface (UI) text from English to the specified target language.

RULES:
1. Preserve all format specifiers, code, tags, and placeholders exactly as they are (e.g., %s, %d, {count}, <b>...</b>, &File).
2. Keep the translation concise, natural, and suited for software interfaces.
3. Return ONLY the translated string. Do NOT add greetings, quotes, or explanations."""
OPTIONS = {"temperature": 0.0, "top_p": 0.9, "num_predict": 100}


def translate(model, text, lang_name):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Target Language: {lang_name}\nSource Text: \"{text}\"\nTranslation:"},
    ]
    start = time.time()
    resp = ollama.chat(model=model, messages=messages, options=OPTIONS)
    return resp["message"]["content"].strip().strip("\"'"), round(time.time() - start, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--model", required=True, help="Ollama model tag")
    args = ap.parse_args()

    sysdir = BASE / "data" / args.system
    missing = pd.read_csv(sysdir / "MISSING.csv", keep_default_na=False)
    log = []
    for lang, grp in missing.groupby("lang"):
        path = sysdir / f"{lang}.txt"
        lines = path.read_text(encoding="utf-8").split("\n")[:-1]
        for r in grp.itertuples():
            out, lat = translate(args.model, r.source, LANG_NAMES[lang])
            flat = " ".join(out.split())
            lines[r.line - 1] = flat
            log.append({"lang": lang, "line": r.line, "reason": r.reason, "source": r.source,
                        "output": flat, "empty_again": flat == "", "latency_sec": lat,
                        "model": args.model, "date": datetime.date.today().isoformat()})
            print(f"{lang}:{r.line} [{r.reason}] -> {flat[:60]!r}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    pd.DataFrame(log).to_csv(sysdir / "FILLED.csv", index=False)
    df = pd.DataFrame(log)
    print(f"\nFilled {len(df)} lines; still empty: {int(df.empty_again.sum())}")


if __name__ == "__main__":
    main()
