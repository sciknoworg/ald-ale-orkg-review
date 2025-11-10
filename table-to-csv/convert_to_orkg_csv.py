#!/usr/bin/env python3
"""
Convert merged-w-dois CSV to ORKG-ready CSV.

Auto-detects which ORKG property IDs (PIDs) to include by matching input headers.

Normalization rules for molecule-like columns:
- Remove spaces inside the chemical/molecule, but keep a space before "plasma".
- Prefix non-empty values with "resource:".
"""

import argparse
import re
from pathlib import Path
import pandas as pd

# ==============================================================
# 1) HEADER MAP (your cleaned-up version)
# ==============================================================

CANDIDATE_HEADERS = {
    "P9071":   ["Material"],
    "P180042": ["Precursor 1"],
    "P180043": ["Precursor 2"],
    "P180044": ["Precursor 3"],
    "P180045": ["Precursor 4"],
    "P180041": ["GPC [Å]", "GPC [Ã…]", "GPC [A]"],
    "P180013": ["T [°C]", "T [Â°C]", "T [C]"],
    "doi":     ["doi"],

    "P183117": ["Materials Surface", "Material surface", "Materials surface", "Materialsurface"],
    "P183118": ["Surface adsorption", "Adsorption precursor"],
    "P183119": ["Surface removal", "Removal precursor"],
    "P183120": ["EPC (Å/cycle)", "EPC (A/cycle)", "EPC (Ã…/cycle)", "EPC (Ã/cycle)", "EPC"],
    "P183121": ["Etching temperature", "Etch temperature", "Etching temp", "Etch temp"],

    "P183123": ["Semi-conductor", "Semiconductor", "Semi conductor"],
    "P183124": ["Modification"],
    "P183125": ["Removal"],
    "P183126": ["Activation"],
    "P183127": ["Material type", "Type of material", "Materialtype"],

    "P183144": ["Material etched", "Etched material"],
    "P183145": ["Reactant 1"],
    "P183146": ["Reactant 2"],
    "P183147": ["Reactant 3"],

    # NEW PROPERTIES
    "P183148": ["Direction"],
    "P183149": ["Reaction"],
    "P183150": ["Process Temperature (°C)", "Process temperature (°C)", "Process temp (°C)"],
    "P183151": ["Time of cycle", "Cycle time", "Time/cycle"],

    "P183142": [
        "Precursor Chemistries for Adsorption",
        "Precursor chemistries for adsorption",
        "Precursor Chemistry for Adsorption",
        "Precursor chemistry for adsorption",
        "Precursor chemistries (adsorption)",
        "Precursor Chemistries for Adsorption: P183142",
        "Precursor Chemistries for Adsorption (P183142)",
        "Adsorption precursor chemistries"
    ],
    "P183143": [
        "Energy Source for Etching/Desorption",
        "Energy source for etching/desorption",
        "Energy Source for Etching / Desorption",
        "Energy Source for Desorption",
        "Energy Source for Etching",
        "Energy source (etching/desorption)",
        "Energy Source for Etching/Desorption: P183143",
        "Energy Source for Etching/Desorption (P183143)"
    ],

    "P183129": ["Precursor chemistries for fluorination"],
    "P183130": ["Process temp. (°C)", "Process temperature (°C)"],
    "P183131": ["Etching rate (Å/cycle)", "Etching rate"],
    "P183132": ["Ion energy in the removal step (Bias voltage)"],
    "P183133": ["Selectivity of material"],
    "P173032": ["Selectivity"],
    "P183134": ["Improving etch selectivity method"],
    "P183135": ["Method of removal chamber wall effect"],
    "P183136": ["Etching mechanism"],
    "P183137": ["1st step", "First step"],
    "P183138": ["2nd step", "Second step"],
    "P183139": ["3rd step", "Third step"],
}


# ==============================================================
# 2) TOKEN-AWARE HEADER MATCHER  (replaces your old find_actual_column)
# ==============================================================

def _norm_header(s: str) -> str:
    s = (s or "")
    # strip BOM / zero-width
    s = s.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def _tokens(s: str):
    return [t for t in re.split(r"[^a-z0-9]+", _norm_header(s)) if t]

def find_actual_column(df_cols, candidates):
    norm_map = {_norm_header(c): c for c in df_cols}

    # exact match first
    for cand in candidates:
        nc = _norm_header(cand)
        if nc in norm_map:
            return norm_map[nc]

    # token-aware fallback: only when candidate has >= 2 tokens
    cand_tokens_list = [(cand, _tokens(cand)) for cand in candidates]
    cand_tokens_list = [(cand, toks) for cand, toks in cand_tokens_list if len(toks) >= 2]

    for cand, cand_toks in cand_tokens_list:
        for k_norm, orig in norm_map.items():
            hdr_toks = set(_tokens(orig))
            if all(t in hdr_toks for t in cand_toks):
                return orig

    return None

# ==============================================================
# 3) PID PRIORITY LIST AND COLLISION HANDLING
# ==============================================================

ORDERED_PIDS = [
    "P183129","P183125","P183130","P183131","P183132",
    "P183133","P173032","P183134","P183135",
    "P183136","P183137","P183138","P183139",
    "P183142","P183143",
    "P183117","P183118","P183119","P183120","P183121",
    "P183123","P183124","P183126","P183127",
    "P183144","P183145","P183146","P183147",
    "P183148","P183149","P183150","P183151",
    "P9071","P180042","P180043","P180044","P180045",
    "P180041","P180013",
]


# ==============================================================
# 4) MOLECULE NORMALIZATION HELPER
# ==============================================================

MOLECULE_COL_PIDS = {
    "P183129","P183125","P183117","P183118","P183119",
    "P183142",
    "P183123","P183124","P183126","P183127",
    "P183144","P183145","P183146","P183147",
    "P183148", "P183149",
    "P9071","P180042","P180043","P180044","P180045",
    "P183137","P183138","P183139",
}

def normalize_molecule(value: str) -> str:
    s = (str(value) or "").strip()
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)
    m = re.search(r"\bplasma\b", s, flags=re.IGNORECASE)
    if m:
        base = s[:m.start()].strip()
        base_compact = re.sub(r"\s+", "", base)
        return f"{base_compact} plasma"
    return re.sub(r"\s+", "", s)

# ==============================================================
# MAIN
# ==============================================================

def main():
    ap = argparse.ArgumentParser(description="Convert merged CSV to ORKG-ready CSV with property IDs (auto-detected).")
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV file")
    ap.add_argument("--out", dest="out", required=True, help="Output CSV file")
    args = ap.parse_args()

    inp = Path(args.inp).expanduser().resolve()
    outp = Path(args.out).expanduser().resolve()

    df = pd.read_csv(inp, sep=None, engine="python", dtype=str, encoding="utf-8-sig").fillna("")

    # detect which columns exist
    present = {pid: find_actual_column(df.columns, cands)
               for pid, cands in CANDIDATE_HEADERS.items()}

    # ---- Resolve collisions by priority ----
    seen_src = set()
    pids_used = []
    for pid in ORDERED_PIDS:
        src = present.get(pid)
        if not src:
            continue
        if src in seen_src:
            continue  # skip duplicates (like Removal)
        seen_src.add(src)
        pids_used.append(pid)
    pids_used.append("doi")

    # ---- Forward fill unique source columns ----
    src_cols_to_ffill = [present[pid] for pid in pids_used if pid != "doi" and present.get(pid)]
    seen = set()
    src_cols_to_ffill = [c for c in src_cols_to_ffill if not (c in seen or seen.add(c))]
    if src_cols_to_ffill:
        filled = (
            df[src_cols_to_ffill]
            .replace(r"^\s*$", pd.NA, regex=True)
            .ffill()
        )
        for col in src_cols_to_ffill:
            df[col] = filled[col]

    # ---- Build output ----
    out_df = pd.DataFrame(columns=pids_used)
    for pid in pids_used:
        if pid == "doi":
            src = present.get("doi") or ("doi" if "doi" in df.columns else None)
            out_df["doi"] = df[src].astype(str) if src else ""
            continue

        src = present.get(pid)
        if not src:
            out_df[pid] = ""
            continue
        if pid in MOLECULE_COL_PIDS:
            out_df[pid] = df[src].apply(lambda v: f"resource:{normalize_molecule(v)}" if str(v).strip() else "")
        else:
            out_df[pid] = df[src].astype(str)

    outp.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(outp, index=False, encoding="utf-8-sig")
    print(f"✅ Done. Wrote ORKG CSV: {outp}")
    print("→ Columns:", ", ".join(out_df.columns))


if __name__ == "__main__":
    main()
