"""
Unified Invariant Audit Script for Software UI Localization
Evaluates LLM baselines, LLM repaired systems, and classic NMT systems.
Checks deterministic invariants per string:
1. Placeholders preserved (%1, %2, %d, %s, %n, {name}, etc. - matching count & identity, flags extra)
2. Keyboard accelerators (&File preserved, including non-Latin scripts)
3. Script contamination (characters from wrong script)
4. UTF-8 corruption (presence of \\ufffd)
5. Conversational chatter (instructional filler / AI chatter)
6. Untranslated copy fallback (identical to source, excluding allowlisted NTTs)
7. Empty output (blank translation when source is non-empty)

Safe and idempotent: overwrites outputs in results/, leaves originals untouched.
"""

import os
import re
import sys
import json
import random
import argparse
import pandas as pd
from pathlib import Path

# Force utf-8 stdout
sys.stdout.reconfigure(encoding="utf-8")

# Workspace root configuration
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
REPO1_DATA = WORKSPACE_ROOT / "cloud-native-llm-benchmark-main" / "cloud-native-llm-benchmark-main" / "data"
REPO2_DATA = WORKSPACE_ROOT / "nmt-benchmarking-paper-main" / "data"
RESULTS_DIR = WORKSPACE_ROOT / "paper1_llm_vs_nmt" / "results"
SOURCE_FILE = REPO1_DATA / "source" / "en.txt"

# 12 Target languages and forbidden script regexes
LANGUAGES = [
    ("ar", "Arabic", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff]')),
    ("bn", "Bengali", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]')),
    ("de", "German", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff\u0980-\u09ff]')),
    ("es", "Spanish", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff\u0980-\u09ff]')),
    ("fr", "French", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff\u0980-\u09ff]')),
    ("hi", "Hindi", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]')),
    ("ja", "Japanese", re.compile(r'[\u0400-\u04ff\u0600-\u06ff\uac00-\ud7af]')),
    ("mr", "Marathi", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]')),
    ("pa", "Punjabi", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]')),
    ("ta", "Tamil", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]')),
    ("te", "Telugu", re.compile(r'[\u4e00-\u9fff\uac00-\ud7af\u0400-\u04ff\u0600-\u06ff]')),
    ("zh", "Chinese", re.compile(r'[\u0400-\u04ff\u0600-\u06ff\uac00-\ud7af]'))
]

# Audit Regexes
CHATTER_REGEX = re.compile(r'(?i)^(here is the translation|translation:|note:|as an ai|translate into|arabic:|spanish:|bengali:)')
PLACEHOLDER_REGEX = re.compile(r'%\d+|%[a-zA-Z]|\{[^}]+\}')
XML_ENTITY_REGEX = re.compile(r'&\s*[a-zA-Z0-9._-]+;')
# KDE4/OPUS tokenisation writes accelerators with a space ("& Outline"), so an
# optional single space is allowed after '&'. (The LLM repo's original pattern
# r'&[^\s\d_;]' matched only 1 of the 785 accelerator strings in the corpus.)
ACCELERATOR_REGEX = re.compile(r'&\s?[^\s\d_;&]')
REPLACEMENT_CHAR_REGEX = re.compile(r'\ufffd')

# Non-Translatable Token (NTT) Allowlist and Pattern Matchers
FORMULA_REGEX = re.compile(r'^[A-Z0-9_]+\([^)]*\)$')
POSIX_FMT_REGEX = re.compile(r'^%[a-zA-Z](\s*\([^)]*\))?$')
XML_ONLY_REGEX = re.compile(r'^&\s*[a-zA-Z0-9._-]+;$')
CAMEL_OR_SNAKE_REGEX = re.compile(r'([a-z][A-Z]|_[a-zA-Z])')
X11_COLOR_REGEX = re.compile(r'^[A-Za-z]+[1-4]$')
UA_STRING_REGEX = re.compile(r'^UADescription\s*\(.*\)$')
TZ_PATH_REGEX = re.compile(r'^[A-Za-z]+/\s*[A-Za-z_]+$')
EURO_COGNATE_PHRASE_REGEX = re.compile(r'^(\d+\s+Points|Position\s+[xyz]:?|Pixmap:?|Kig\s+figure|Dithering\s+PPI)$', re.IGNORECASE)

KNOWN_NTTS = {
    'SCSI', 'S-ATA', 'IEEE 1394', 'SD/ MMC', 'RITOn', 'kcm_partition', 'KTraderClient',
    'USB', 'PCI', 'BIOS', 'IPv4', 'IPv6', 'UUID', 'HDMI', 'TCP', 'UDP', 'DHCP', 'DNS',
    'RAM', 'CPU', 'GPU', 'Samba', 'OpenVPN', 'Cisco', 'ALSA', 'MIME', 'UTF-8', 'ASCII',
    'HTML', 'HTTP', 'HTTPS', 'LDAP', 'IMAP', 'POP3', 'SMTP', 'X11', 'OpenGL',
    'Iptc', 'NoPCL3GUI', 'SDP UUid:', 'KMobileTools EngineXP', 'Linediff: A< - > B'
}

def has_accelerator(text: str) -> bool:
    cleaned = XML_ENTITY_REGEX.sub('', text)
    return bool(ACCELERATOR_REGEX.search(cleaned))

def is_legitimate_ntt(src_str: str, lang_code: str = "") -> bool:
    """
    Identifies strings that should legitimately remain untranslated (NTTs),
    preventing them from being falsely penalized as 'copy fallback'.
    Built from:
    1. Industry-standard hardware/protocol acronyms (SCSI, USB, IPv4, etc.)
    2. Mathematical/spreadsheet formulas (e.g. BIN2OCT(value))
    3. Technical format descriptors, XML entity tokens, and X11 color specifiers
    4. Short uppercase identifiers and timezone tokens
    5. Western European cognates (de, es, fr) that are lexically identical.
    """
    s = src_str.strip()
    if s in KNOWN_NTTS:
        return True
    if (FORMULA_REGEX.match(s) or POSIX_FMT_REGEX.match(s) or XML_ONLY_REGEX.match(s)
            or X11_COLOR_REGEX.match(s) or UA_STRING_REGEX.match(s) or TZ_PATH_REGEX.match(s)):
        return True
    if re.match(r'^[A-Z0-9\s/\-\.]{2,12}$', s) and not s.isalpha():
        return True
    if s.isupper() and len(s) <= 6:
        return True
    if lang_code in ("de", "es", "fr"):
        if EURO_COGNATE_PHRASE_REGEX.match(s):
            return True
        if " " not in s and not CAMEL_OR_SNAKE_REGEX.search(s) and re.match(r'^[A-Za-z\-]+:?$', s):
            return True
    return False

def discover_systems():
    """
    Locates available systems across Repo 1 and NMT directories.
    Returns dict: system_name -> directory_path
    """
    systems = {}

    # Repo 1 LLMs (5 baseline + 5 repaired)
    if REPO1_DATA.exists():
        for d in sorted(REPO1_DATA.iterdir()):
            if d.is_dir() and (d.name.startswith("baseline_") or d.name.startswith("repaired_")):
                systems[d.name] = d

    # NMT systems: read ONLY from the Track 1 repo (nmt-benchmarking-paper-main/data).
    # The ../dump folder is never used (project decision 2026-11-12).
    # 0-byte stub files are skipped automatically in run_audit().
    nmt_candidates = [
        "baseline_google_translate",
        "microsoft_translator",
        "nllb200",
        "indictrans2",
        "madlad400",
        "amazon_translate"
    ]
    for sys_name in nmt_candidates:
        if REPO2_DATA.exists() and (REPO2_DATA / sys_name).exists():
            systems[sys_name] = REPO2_DATA / sys_name

    return systems

def run_audit(sample_size_flagged=100, sample_size_unflagged=50, random_seed=42, new_sample=False):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Source file not found at {SOURCE_FILE}")

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        source_lines = [l.rstrip("\r\n") for l in f]
    
    total_source_lines = len(source_lines)
    src_placeholders = [sorted(PLACEHOLDER_REGEX.findall(s)) for s in source_lines]

    systems = discover_systems()
    print(f"Discovered {len(systems)} systems to audit: {list(systems.keys())}")

    defects_per_string = []
    summary_rows = []
    unflagged_pool = []
    flagged_pool = []

    for sys_name, sys_dir in systems.items():
        print(f"Auditing {sys_name} from {sys_dir}...")
        for code, lang_name, forbidden_re in LANGUAGES:
            file_path = sys_dir / f"{code}.txt"
            if not file_path.exists():
                # Expected for indictrans2 on non-indic languages
                continue

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                hyp_lines = [l.rstrip("\r\n") for l in f]

            if len(hyp_lines) == 0:
                print(f"  [WARN] {sys_name}/{code}.txt is 0 bytes (missing translation data). Skipping.")
                continue

            script_contamination = 0
            broken_placeholders = 0
            broken_accelerators = 0
            encoding_corruption = 0
            conversational_chatter = 0
            copy_fallback = 0
            empty_output = 0
            total_flawed = 0

            n_lines = min(total_source_lines, len(hyp_lines))

            for idx in range(n_lines):
                src = source_lines[idx]
                hyp = hyp_lines[idx]
                issues = []

                # 1. Script Contamination
                if forbidden_re.search(hyp):
                    issues.append("script_contamination")
                    script_contamination += 1

                # 2. Broken Placeholders (Missing or Hallucinated)
                hyp_p = sorted(PLACEHOLDER_REGEX.findall(hyp))
                if src_placeholders[idx] != hyp_p:
                    issues.append("broken_placeholder")
                    broken_placeholders += 1

                # 3. Broken Accelerators
                if has_accelerator(src) and not has_accelerator(hyp):
                    issues.append("broken_accelerator")
                    broken_accelerators += 1

                # 4. Encoding Corruption (\ufffd)
                if REPLACEMENT_CHAR_REGEX.search(hyp):
                    issues.append("encoding_corruption")
                    encoding_corruption += 1

                # 5. Conversational Chatter
                if CHATTER_REGEX.search(hyp):
                    issues.append("conversational_chatter")
                    conversational_chatter += 1

                # 6. Empty Output
                src_strip = src.strip()
                hyp_strip = hyp.strip()
                if hyp_strip == "" and src_strip != "":
                    issues.append("empty_output")
                    empty_output += 1

                # 7. Copy Fallback (identical to source, excluding allowlisted NTTs)
                if src_strip == hyp_strip and len(src_strip) > 3 and any(c.isalpha() for c in src_strip):
                    if not is_legitimate_ntt(src_strip, code):
                        issues.append("copy_fallback")
                        copy_fallback += 1

                line_id = idx + 1
                if issues:
                    total_flawed += 1
                    issue_str = ";".join(issues)
                    defects_per_string.append({
                        "system": sys_name,
                        "lang": code,
                        "line_id": line_id,
                        "defect_types": issue_str
                    })
                    flagged_pool.append({
                        "system": sys_name,
                        "lang": code,
                        "line_id": line_id,
                        "source": src,
                        "output": hyp,
                        "flagged_type": issue_str,
                        "my_verdict": ""
                    })
                else:
                    unflagged_pool.append({
                        "system": sys_name,
                        "lang": code,
                        "line_id": line_id,
                        "source": src,
                        "output": hyp,
                        "flagged_type": "none",
                        "my_verdict": ""
                    })

            total_evaluated = n_lines
            defect_rate = (total_flawed / total_evaluated * 100) if total_evaluated > 0 else 0.0

            summary_rows.append({
                "system": sys_name,
                "lang": code,
                "total_strings": total_evaluated,
                "script_contamination": script_contamination,
                "broken_placeholder": broken_placeholders,
                "broken_accelerator": broken_accelerators,
                "encoding_corruption": encoding_corruption,
                "conversational_chatter": conversational_chatter,
                "copy_fallback": copy_fallback,
                "empty_output": empty_output,
                "total_flawed": total_flawed,
                "defect_rate_pct": round(defect_rate, 4)
            })

    # Save defects_per_string.csv
    df_defects = pd.DataFrame(defects_per_string)
    defects_csv = RESULTS_DIR / "defects_per_string.csv"
    df_defects.to_csv(defects_csv, index=False, encoding="utf-8")
    print(f"\nSaved line-level defects to {defects_csv} ({len(df_defects)} flagged lines)")

    # Save defect_summary.csv
    df_summary = pd.DataFrame(summary_rows)
    summary_csv = RESULTS_DIR / "defect_summary.csv"
    df_summary.to_csv(summary_csv, index=False, encoding="utf-8")
    print(f"Saved defect summary to {summary_csv} ({len(df_summary)} system-lang pairs)")

    # System-level aggregation summary
    sys_agg = df_summary.groupby("system").agg({
        "total_strings": "sum",
        "total_flawed": "sum",
        "script_contamination": "sum",
        "broken_placeholder": "sum",
        "broken_accelerator": "sum",
        "encoding_corruption": "sum",
        "conversational_chatter": "sum",
        "copy_fallback": "sum",
        "empty_output": "sum"
    }).reset_index()
    sys_agg["defect_rate_pct"] = (sys_agg["total_flawed"] / sys_agg["total_strings"] * 100).round(2)
    sys_agg_csv = RESULTS_DIR / "defect_summary_by_system.csv"
    sys_agg.to_csv(sys_agg_csv, index=False, encoding="utf-8")
    print(f"Saved system-level summary to {sys_agg_csv}")

    # Validation sample: manual_check_sample.csv. It holds human/model grades, so it is
    # only (re)drawn when missing or when --new-sample is passed.
    sample_csv = RESULTS_DIR / "manual_check_sample.csv"
    if sample_csv.exists() and not new_sample:
        print(f"Kept existing graded sample {sample_csv} (use --new-sample to redraw)")
        flagged_pool = []
    random.seed(random_seed)
    sampled_flagged = random.sample(flagged_pool, min(sample_size_flagged, len(flagged_pool)))
    sampled_unflagged = random.sample(unflagged_pool, min(sample_size_unflagged, len(unflagged_pool)))

    sample_combined = sampled_flagged + sampled_unflagged
    random.shuffle(sample_combined)

    if flagged_pool:
        df_sample = pd.DataFrame(sample_combined)
        df_sample.to_csv(sample_csv, index=False, encoding="utf-8")
        print(f"Saved manual validation sample to {sample_csv} ({len(df_sample)} rows: {len(sampled_flagged)} flagged + {len(sampled_unflagged)} unflagged, seed={random_seed})")

    # Print summary table to console
    print("\n" + "=" * 95)
    print(f"{'System':<28} | {'Strings':<8} | {'Flawed':<8} | {'Defect %':<9} | {'%1 Err':<8} | {'& Err':<7} | {'Copy Fallback':<13}")
    print("-" * 95)
    for _, row in sys_agg.sort_values(by="defect_rate_pct").iterrows():
        print(f"{row['system']:<28} | {int(row['total_strings']):<8} | {int(row['total_flawed']):<8} | {row['defect_rate_pct']:>6.2f}%  | {int(row['broken_placeholder']):<8} | {int(row['broken_accelerator']):<7} | {int(row['copy_fallback']):<13}")
    print("=" * 95 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Invariant Audit")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for manual check sample")
    parser.add_argument("--flagged-sample", type=int, default=100, help="Number of flagged samples")
    parser.add_argument("--unflagged-sample", type=int, default=50, help="Number of unflagged samples")
    parser.add_argument("--new-sample", action="store_true", help="Redraw manual_check_sample.csv (overwrites grades)")
    args = parser.parse_args()

    run_audit(
        sample_size_flagged=args.flagged_sample,
        sample_size_unflagged=args.unflagged_sample,
        random_seed=args.seed,
        new_sample=args.new_sample
    )
