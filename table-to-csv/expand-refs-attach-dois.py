#!/usr/bin/env python3
"""
Expand reference lists (with or without square brackets) and attach DOIs from a Crossref mapping,
prompting for missing DOIs and updating the mapping file in-place.

Usage:
  python expand_refs_attach_doi.py \
    --data data.csv \
    --mapping references-resolved-dois.csv \
    --out data_expanded.csv \
    --refs-col "Ref."

Notes:
- The references column may contain numbers, comma-separated lists, and ranges:
    "59" | "40,41,90,91" | "69-71" | "69 – 71" | "\"44,64\""
  Brackets like "[28,224-226]" are also supported but NOT required.
- The mapping CSV is updated in-place when you manually provide a DOI:
    * only 'best_doi' and 'decision' are changed (to the provided DOI and 'accepted');
      all other columns are preserved as-is.
- Rows with no accepted DOIs for their refs are dropped.
"""

import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

EN_DASHES = ["–", "—", "‒", "−"]  # common unicode dashes


def _cleanup_token(tok: str) -> str:
    tok = (tok or "").strip().strip("\"'“”‘’")
    for d in EN_DASHES:
        tok = tok.replace(d, "-")
    tok = re.sub(r"\s*-\s*", "-", tok)
    return tok


def _expand_token_to_numbers(tok: str) -> List[int]:
    tok = _cleanup_token(tok)
    if "-" in tok:
        parts = [p.strip() for p in tok.split("-") if p.strip()]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            a, b = int(parts[0]), int(parts[1])
            return list(range(min(a, b), max(a, b) + 1))
    if re.fullmatch(r"\d+", tok):
        return [int(tok)]
    return []


def parse_refs_cell(val: Optional[str]) -> List[int]:
    s = ("" if val is None else str(val)).strip()
    if not s:
        return []
    for d in EN_DASHES:
        s = s.replace(d, "-")
    groups = re.findall(r"\[(.*?)\]", s)
    tokens: List[str] = []
    if groups:
        for g in groups:
            tokens.extend([t.strip() for t in re.split(r"[;,]", g) if t.strip()])
    else:
        tokens = [t.strip() for t in re.split(r"[;,]", s) if t.strip()]

    nums: List[int] = []
    for tok in tokens:
        nums.extend(_expand_token_to_numbers(tok))

    if not nums:
        for rng in re.findall(r"\b(\d+\s*-\s*\d+)\b", s):
            nums.extend(_expand_token_to_numbers(rng))
        for n in re.findall(r"\b\d+\b", s):
            iv = int(n)
            if iv not in nums:
                nums.append(iv)

    seen = set()
    out = []
    for n in nums:
        if n not in seen:
            out.append(n)
            seen.add(n)
    return out


def read_csv_any(path: Path, **kwargs):
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1,
        f"Could not decode {path.name} with utf-8/utf-8-sig/cp1252/latin-1. "
        "Open and re-save as UTF-8 (CSV) or tell the script which encoding to use.")


def autodetect_refs_col(df: pd.DataFrame, preferred: str) -> str:
    if preferred and preferred in df.columns:
        return preferred
    candidates = ["Reference", "Refs.", "Refs", "Ref", "Citations"]
    for c in candidates:
        if c in df.columns:
            return c
    lowmap = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lowmap:
            return lowmap[c.lower()]
    raise ValueError(f"Could not find a references column. Tried {candidates}. Available: {list(df.columns)}")


# ---------- Mapping helpers (now keep the full DataFrame so we can update it) ----------

RE_DOI = re.compile(r"^10\.\S+/\S+$", re.IGNORECASE)

def load_mapping_df(mapping_csv: Path) -> pd.DataFrame:
    df_map = read_csv_any(mapping_csv, sep=None, engine="python")
    # normalize column names (trim)
    df_map = df_map.rename(columns={c: c.strip() for c in df_map.columns})
    # ensure required columns exist
    for c in ["idx", "best_doi", "decision"]:
        if c not in df_map.columns:
            df_map[c] = ""  # create empty col if missing
    return df_map


def mapping_to_dict(df_map: pd.DataFrame) -> Dict[int, str]:
    df_ok = df_map[
        df_map["decision"].astype(str).str.lower().str.contains("accept", na=False)
        & (df_map["best_doi"].astype(str).str.strip() != "")
    ].copy()
    df_ok["idx"] = pd.to_numeric(df_ok["idx"], errors="coerce").astype("Int64")
    df_ok = df_ok.dropna(subset=["idx"])
    return {int(r["idx"]): str(r["best_doi"]).strip() for _, r in df_ok.iterrows()}


def save_mapping_df(df_map: pd.DataFrame, mapping_path: Path) -> None:
    # preserve column order; write as UTF-8 with BOM for Excel-friendliness
    df_map.to_csv(mapping_path, index=False, encoding="utf-8-sig")


def _confirm(prompt: str) -> bool:
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def prompt_for_doi(idx: int) -> Optional[str]:
    print(f"\nReference {idx} has no accepted DOI in mapping.")
    print("Enter DOI for this reference (empty or 'skip' to skip).")
    print("Examples: 10.1021/acs.jpcc.0c01234   10.1116/6.0001234\n")
    while True:
        raw = input(f"DOI for ref {idx}: ").strip()
        if raw == "" or raw.lower() == "skip":
            return None
        # Accept typical DOIs; if it doesn't match, allow override with confirmation
        if RE_DOI.match(raw):
            return raw
        else:
            if _confirm(f"'{raw}' does not look like a standard DOI. Use it anyway?"):
                return raw
            # else loop again


def upsert_mapping_entry(df_map: pd.DataFrame, idx: int, doi: str) -> pd.DataFrame:
    """
    Set best_doi and decision='accepted' for row with idx.
    If not present, append a new row with only these columns set (others empty).
    Do NOT touch any other columns/values.
    """
    # ensure correct dtypes
    if "idx" not in df_map.columns:
        df_map["idx"] = ""
    # locate row(s)
    with pd.option_context('mode.chained_assignment', None):
        mask = pd.to_numeric(df_map["idx"], errors="coerce") == idx
        if mask.any():
            df_map.loc[mask, "best_doi"] = str(doi).strip()
            df_map.loc[mask, "decision"] = "accepted"
        else:
            # Append minimal row preserving all columns
            new_row = {c: "" for c in df_map.columns}
            new_row["idx"] = idx
            new_row["best_doi"] = str(doi).strip()
            new_row["decision"] = "accepted"
            df_map = pd.concat([df_map, pd.DataFrame([new_row])], ignore_index=True)
    return df_map


def main():
    ap = argparse.ArgumentParser(description="Expand references (numbers, lists, ranges) and attach DOIs from a mapping; prompt for missing DOIs and update the mapping.")
    ap.add_argument("--data", required=True, help="Input data CSV (table rows with a references column and optional DOI column).")
    ap.add_argument("--mapping", required=True, help="Resolved refs CSV (e.g., references-resolved-dois.csv; must have/allow columns: idx, best_doi, decision).")
    ap.add_argument("--out", required=True, help="Output CSV path.")
    ap.add_argument("--refs-col", default="Reference", help="Name of the references column in the data CSV (default: 'Reference'). Auto-detects common variants if missing.")
    ap.add_argument("--doi-col", default="doi", help="Name of the DOI column in the data CSV. If empty, use 'doi' or 'doi_list' if present; otherwise create 'doi'.")
    ap.add_argument("--no-ask-missing", action="store_true", help="Disable interactive prompting for missing DOIs (skip instead).")
    args = ap.parse_args()

    data_path = Path(args.data).expanduser().resolve()
    mapping_path = Path(args.mapping).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    # Load mapping as full DF (so we can write back)
    df_map = load_mapping_df(mapping_path)
    ref_to_doi = mapping_to_dict(df_map)

    # Load data
    df = read_csv_any(data_path, sep=None, engine="python", dtype=str).fillna("")

    # Figure out DOI column
    doi_col = args.doi_col.strip()
    if not doi_col:
        if "doi" in df.columns:
            doi_col = "doi"
        elif "doi_list" in df.columns:
            doi_col = "doi_list"
        else:
            doi_col = "doi"
            df[doi_col] = ""

    # Detect references column
    refs_col = autodetect_refs_col(df, args.refs_col)

    # Build new rows
    new_rows = []
    kept = 0
    expanded = 0
    dropped = 0

    # Keep columns order
    columns = list(df.columns)
    if doi_col not in columns:
        columns.append(doi_col)

    ask_missing = not args.no-ask-missing

    for _, row in df.iterrows():
        row_dict = {c: row.get(c, "") for c in columns}
        has_doi = str(row_dict.get(doi_col, "")).strip() != ""
        refs_val = row_dict.get(refs_col, "")

        if has_doi:
            new_rows.append(row_dict)
            kept += 1
            continue

        ref_nums = parse_refs_cell(refs_val)
        wrote_any = False
        for n in ref_nums:
            doi = ref_to_doi.get(n, "")

            if not doi and ask_missing:
                # interactively ask the user
                entered = prompt_for_doi(n)
                if entered:
                    # update mapping DF (only best_doi & decision), save immediately
                    df_map = upsert_mapping_entry(df_map, n, entered)
                    save_mapping_df(df_map, mapping_path)
                    # refresh dict for immediate use
                    ref_to_doi[n] = entered
                    doi = entered
                else:
                    # user chose to skip this ref number
                    doi = ""

            if not doi:
                continue  # still unresolved → skip this ref id

            rnew = dict(row_dict)
            rnew[doi_col] = doi
            rnew[refs_col] = str(n)  # record exactly which ref index was used
            new_rows.append(rnew)
            wrote_any = True
            expanded += 1

        if not wrote_any:
            dropped += 1

    out_df = pd.DataFrame(new_rows, columns=columns)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Done. Wrote: {out_path}")
    print(f"Kept with DOI: {kept} | Expanded rows created: {expanded} | Dropped (no accepted DOI): {dropped}")
    if ask_missing:
        print(f"Mapping file updated in-place (when you entered DOIs): {mapping_path}")


if __name__ == "__main__":
    main()
