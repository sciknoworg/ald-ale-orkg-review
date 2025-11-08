#!/usr/bin/env python3
"""
Convert merged-w-dois CSV to ORKG-ready CSV.

- Column mapping:
  Material      -> P9071
  Precursor 1   -> P180042
  Precursor 2   -> P180043
  Precursor 3   -> P180044
  Precursor 4   -> P180045
  GPC [Å]/[Ã…]  -> P180041
  T [°C]/[Â°C]  -> P180013
  (Keep 'doi' column as-is)

- For Material and Precursor 1..4 values:
  * Remove all spaces inside the chemical/molecule (e.g., "H 2 O" -> "H2O", "Cp 3 Sc" -> "Cp3Sc",
    "Sc(thd) 3" -> "Sc(thd)3")
  * BUT keep a space before trailing "plasma" (e.g., "O 2 plasma" -> "O2 plasma")
  * Prefix non-empty values with "resource:" (e.g., "resource:O3", "resource:O2 plasma")
"""

import argparse
import re
from pathlib import Path
import pandas as pd

# Candidate headers to tolerate encoding differences on Windows
CANDIDATE_HEADERS = {
    "P9071":   ["Material"],
    "P180042": ["Precursor 1"],
    "P180043": ["Precursor 2"],
    "P180044": ["Precursor 3"],
    "P180045": ["Precursor 4"],
    "P180041": ["GPC [Å]", "GPC [Ã…]", "GPC [A]"],    # tolerate odd encodings
    "P180013": ["T [°C]", "T [Â°C]", "T [C]"],        # tolerate odd encodings
    "doi":     ["doi"],

    # --- ALE mapping (unique properties) ---
    "P183117": ["Materials Surface", "Material surface", "Materials surface", "Materialsurface"],
    "P183118": ["Surface adsorption", "Adsorption precursor", "Adsorption"],
    "P183119": ["Surface removal", "Removal precursor", "Removal"],
    "P183120": ["EPC (Å/cycle)", "EPC (A/cycle)", "EPC (Ã…/cycle)", "EPC (Ã/cycle)", "EPC"],
    "P183121": ["Etching temperature", "Etch temperature", "Etching temp", "Etch temp",
                "T [°C]", "T [Â°C]", "T [C]"],

    # --- new ALE+ extension mappings ---
    "P183123": ["Semi-conductor", "Semiconductor", "Semi conductor"],
    "P183124": ["Modification"],
    "P183125": ["Removal"],
    "P183126": ["Activation"],
    "P183127": ["Material type", "Type of material", "Materialtype"],
}

# Molecule-like columns that need chemical normalization + "resource:" prefix
MOLECULE_COL_PIDS = [
    "P9071", "P180042", "P180043", "P180044", "P180045",
    "P183117", "P183118", "P183119",
    "P183123", "P183124", "P183125", "P183126", "P183127",
]


def _norm_header(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")  # NBSP → space
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def find_actual_column(df_cols, candidates):
    # map normalized -> original
    norm_map = {_norm_header(c): c for c in df_cols}
    # exact normalized match
    for cand in candidates:
        nc = _norm_header(cand)
        if nc in norm_map:
            return norm_map[nc]
    # relaxed: substring match on normalized headers
    for cand in candidates:
        nc = _norm_header(cand)
        for k, orig in norm_map.items():
            if nc in k or k in nc:
                return orig
    return None


def normalize_molecule(value: str) -> str:
    """
    Remove spaces within the chemical part, but keep a space before a trailing 'plasma'.
    Examples:
      "O 3"            -> "O3"
      "H 2 O"          -> "H2O"
      "O 2 plasma"     -> "O2 plasma"
      "Sc(thd) 3"      -> "Sc(thd)3"
      "Cp 3 Sc"        -> "Cp3Sc"
    """
    s = (value or "").strip()
    if not s:
        return ""

    # Normalize whitespace
    s = re.sub(r"\s+", " ", s)

    # Detect 'plasma' as a trailing token (case-insensitive)
    m = re.search(r"\bplasma\b", s, flags=re.IGNORECASE)
    if m:
        base = s[:m.start()].strip()
        # join all spaces inside the base
        base_compact = re.sub(r"\s+", "", base)
        return f"{base_compact} plasma"

    # No 'plasma' → remove all spaces
    return re.sub(r"\s+", "", s)


def main():
    ap = argparse.ArgumentParser(description="Convert merged-w-dois CSV to ORKG-ready CSV with property IDs.")
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV (e.g., merged-w-dois-tab-3.csv)")
    ap.add_argument("--out", dest="out", required=True, help="Output CSV for ORKG upload")
    ap.add_argument(
        "--pids",
        nargs="+",
        required=True,
        help=(
            "List of property IDs to include, in order. "
            "Example: --pids P183117 P183118 P183119 P183120 P183121 P183123 P183124 P183125 P183126 P183127"
        ),
    )
    args = ap.parse_args()

    inp = Path(args.inp).expanduser().resolve()
    outp = Path(args.out).expanduser().resolve()

    # Read input (auto-detect delimiter)
    df = pd.read_csv(inp, sep=None, engine="python", dtype=str).fillna("")

    # Resolve actual columns present
    present = {}
    for pid, candidates in CANDIDATE_HEADERS.items():
        col = find_actual_column(df.columns, candidates)
        present[pid] = col  # may be None for optional ones

    # --- forward-fill any user-specified PID columns automatically ---
    src_cols_to_ffill = []
    for pid in args.pids:
        col = present.get(pid)
        if col:  # only if we actually found a column for this PID
            src_cols_to_ffill.append(col)

    if src_cols_to_ffill:
        df[src_cols_to_ffill] = (
            df[src_cols_to_ffill]
            .replace(r"^\s*$", pd.NA, regex=True)
            .ffill()
        )

    # Build output columns dynamically (from user-specified list + doi)
    out_cols = args.pids + ["doi"]
    out_df = pd.DataFrame(columns=out_cols)

    # Copy/transform columns
    for pid in out_cols:
        if pid == "doi":
            # Preserve DOI column as-is
            src = present.get("doi")
            if src:
                out_df["doi"] = df[src].astype(str)
            elif "doi" in df.columns:
                out_df["doi"] = df["doi"].astype(str)
            else:
                out_df["doi"] = ""
            continue

        src = present.get(pid)
        if pid in MOLECULE_COL_PIDS:
            # Normalize molecules and prefix with "resource:"
            if src:
                out_df[pid] = df[src].apply(lambda v: f"resource:{normalize_molecule(v)}" if str(v).strip() else "")
            else:
                out_df[pid] = ""
        else:
            # Direct copy for numeric/text properties
            out_df[pid] = df[src].astype(str) if src else ""

    # Write output
    outp.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(outp, index=False, encoding="utf-8-sig")
    print(f"Done. Wrote ORKG CSV: {outp}")
    print("Columns:", ", ".join(out_df.columns))


if __name__ == "__main__":
    main()
