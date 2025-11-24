import argparse
import os
from typing import Dict, List, Tuple

import pandas as pd

from pathlib import Path
from pandas.errors import ParserError

# Import DePlot RMS metrics (make sure you run this script from eval_deplot_rms/)
from deplot import metrics


def df_to_deplot_markdown(df: pd.DataFrame) -> str:
    """Convert a pandas DataFrame to DePlot-style markdown table.

    - No title row (we don't want 'title' to influence RMS).
    - Columns become the header row.
    - Each DataFrame row becomes one table row.
    - NaN / missing values are rendered as empty strings, so they are treated
      as text, not as numbers, by the DePlot metrics.
    """
    if df.empty:
        header_line = " | ".join(str(c) for c in df.columns)
        return header_line

    header_line = " | ".join(str(c) for c in df.columns)
    lines: List[str] = [header_line]

    for _, row in df.iterrows():
        row_vals = []
        for v in row.tolist():
            # Treat pandas NaN and similar missing markers as empty text
            if pd.isna(v):
                row_vals.append("")
            else:
                row_vals.append(str(v))
        lines.append(" | ".join(row_vals))

    return "\n".join(lines)


def classify_system(filename: str) -> Dict[str, object]:
    """Map a results_*.csv filename to setting metadata.

    Returns a dict with:
      - system_name: short model/system id (e.g., 'chatgpt5-1', 'gemma-3-27b-it')
      - system_label: the raw label after 'results_' (e.g., 'neurosymbolic_gemma-3-27b-it')
      - setting_major: 1, 2, or 3
      - setting_id: '1', '2.1', '2.2a', '2.2b', '3.1', or '3.2'
      - variant: one of {'symbolic', 'neural_proprietary', 'neural_open_context',
                         'neural_open_rag', 'neurosym_proprietary', 'neurosym_open'}
      - is_gold: True iff this is the SPARQL gold-standard
    """
    base = os.path.basename(filename)
    if not base.endswith(".csv"):
        raise ValueError(f"Not a CSV file: {base}")
    stem = base[:-4]  # remove .csv
    if not stem.startswith("results_"):
        raise ValueError(f"Unexpected results file name (expected 'results_*.csv'): {base}")

    label = stem[len("results_"):]  # e.g., 'SPARQL', 'chatgpt5-1', 'neurosymbolic_...'

    # Setting 1: SPARQL gold-standard
    if label.lower() == "sparql":
        return {
            "system_name": "SPARQL",
            "system_label": label,
            "setting_major": 1,
            "setting_id": "1",
            "variant": "symbolic",
            "is_gold": True,
        }

    # Neurosymbolic variants (Setting 3)
    if label.startswith("neurosymbolic_"):
        model_id = label[len("neurosymbolic_"):]
        proprietary_models = {"chatgpt5-1", "claude-sonnet-4_5", "gemini3-pro"}
        if model_id in proprietary_models:
            setting_id = "3.1"
            variant = "neurosym_proprietary"
        else:
            setting_id = "3.2"
            variant = "neurosym_open"
        return {
            "system_name": model_id,
            "system_label": label,
            "setting_major": 3,
            "setting_id": setting_id,
            "variant": variant,
            "is_gold": False,
        }

    # Proprietary models (Setting 2.1)
    proprietary_models = {"chatgpt5-1", "claude-sonnet-4_5", "gemini3-pro"}
    if label in proprietary_models:
        return {
            "system_name": label,
            "system_label": label,
            "setting_major": 2,
            "setting_id": "2.1",
            "variant": "neural_proprietary",
            "is_gold": False,
        }

    # RAG open-weights (Setting 2.2b)
    if label.startswith("rag_"):
        model_id = label[len("rag_"):]
        return {
            "system_name": model_id,
            "system_label": label,
            "setting_major": 2,
            "setting_id": "2.2b",
            "variant": "neural_open_rag",
            "is_gold": False,
        }

    # Open-weights context-injected prompting (Setting 2.2a)
    return {
        "system_name": label,
        "system_label": label,
        "setting_major": 2,
        "setting_id": "2.2a",
        "variant": "neural_open_context",
        "is_gold": False,
    }


def iter_query_dirs(root_dir: str):
    """Yield (domain, paper, query_folder, query_path) triples under the dataset root.

    Expected structure:
      root/
        ALD/
          paper1/
            Q01_.../
            Q02_.../
          paper2/
            ...
        ALE/
          paper1/
            ...
    """
    for domain_name in sorted(os.listdir(root_dir)):
        domain_path = os.path.join(root_dir, domain_name)
        if not os.path.isdir(domain_path):
            continue
        for paper_name in sorted(os.listdir(domain_path)):
            paper_path = os.path.join(domain_path, paper_name)
            if not os.path.isdir(paper_path):
                continue
            for query_folder in sorted(os.listdir(paper_path)):
                query_path = os.path.join(paper_path, query_folder)
                if not os.path.isdir(query_path):
                    continue
                if not query_folder.lower().startswith("q"):
                    # Skip non-query folders
                    continue
                yield domain_name, paper_name, query_folder, query_path

def _parse_csv_loose(path: str) -> pd.DataFrame:
    """Very tolerant CSV/TSV parser.

    - Detects delimiter (tab vs comma) from header line.
    - Drops completely empty lines.
    - Drops trailing empty cells on each row.
    - Returns a rectangular DataFrame (rows padded or truncated to header length).
    """
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = [ln.rstrip("\n\r") for ln in text.splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame()

    header_line = lines[0]
    # crude delimiter detection
    if "\t" in header_line:
        delim = "\t"
    else:
        delim = ","

    raw_headers = [h.strip() for h in header_line.split(delim)]
    # drop completely empty header cells
    headers = [h for h in raw_headers if h]
    if not headers:
        # fall back: single unnamed column
        headers = ["col0"]
    n_cols = len(headers)

    rows = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(delim)]
        # drop trailing empty cells
        while parts and parts[-1] == "":
            parts.pop()
        if not parts:
            continue
        if len(parts) > n_cols:
            parts = parts[:n_cols]
        elif len(parts) < n_cols:
            parts += [""] * (n_cols - len(parts))
        rows.append(parts)

    return pd.DataFrame(rows, columns=headers)


def _load_gold_df(path: str) -> pd.DataFrame:
    """Gold tables are clean; normal pandas read is enough."""
    return pd.read_csv(path)


def _load_pred_df(path: str, gold_cols: List[str]) -> pd.DataFrame:
    """Load a prediction CSV, being tolerant of bad formatting.

    Returns a DataFrame whose columns are aligned to gold_cols:
    - Extra columns are dropped.
    - Missing columns are added as empty.
    - If nothing parses, returns an empty DataFrame with gold_cols.
    """
    try:
        df = pd.read_csv(path)
    except (ParserError, UnicodeDecodeError):
        # Fall back to loose parsing for messy LLM CSVs
        print(f"[WARN] Using loose parser for: {path}")
        df = _parse_csv_loose(path)

    if df is None or df.empty:
        # Completely broken prediction → treat as empty table
        return pd.DataFrame(columns=gold_cols)

    df = df.copy()

    # Drop columns that are entirely empty (all blanks)
    def _is_all_blank(series: pd.Series) -> bool:
        return (series.astype(str).str.strip() == "").all()

    df = df.loc[:, [c for c in df.columns if not _is_all_blank(df[c])]]
    if df.shape[1] == 0:
        return pd.DataFrame(columns=gold_cols)

    existing_cols = list(df.columns)
    # align the first len(gold_cols) columns to gold col names
    n = min(len(existing_cols), len(gold_cols))
    rename_map = {existing_cols[i]: gold_cols[i] for i in range(n)}
    df = df.rename(columns=rename_map)

    # Keep only the columns we’ve aligned
    df = df[list(rename_map.values())]

    # Add any missing gold columns as empty strings
    for c in gold_cols[n:]:
        df[c] = ""

    # Reorder to match gold
    df = df[gold_cols]

    return df


def compute_rms_for_query(
    gold_csv_path: str,
    pred_csv_path: str,
) -> Tuple[float, float, float]:
    """Compute RMS (table_datapoints precision/recall/F1) for a single query.

    - Gold CSV: loaded strictly.
    - Pred CSV: loaded with a tolerant parser; if it degenerates to empty,
      the RMS will be 0 across the board.
    """
    gold_df = _load_gold_df(gold_csv_path)
    gold_cols = list(gold_df.columns)

    # For SPARQL vs SPARQL we still call this: pred_df == gold_df
    if os.path.abspath(gold_csv_path) == os.path.abspath(pred_csv_path):
        pred_df = gold_df.copy()
    else:
        pred_df = _load_pred_df(pred_csv_path, gold_cols)

    # Completely empty prediction → zero score
    if pred_df.empty:
        return 0.0, 0.0, 0.0

    gold_table = df_to_deplot_markdown(gold_df)
    pred_table = df_to_deplot_markdown(pred_df)

    targets = [[gold_table]]
    predictions = [pred_table]

    score_dict = metrics.table_datapoints_precision_recall(targets, predictions)
    return (
        float(score_dict["table_datapoints_precision"]),
        float(score_dict["table_datapoints_recall"]),
        float(score_dict["table_datapoints_f1"]),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Apply DePlot RMS metric to all results_*.csv files "
                    "in an ALD/ALE dataset tree."
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Root directory of the dataset (contains ALD/, ALE/, ...).",
    )
    parser.add_argument(
        "--out-per-query-detailed",
        default="rms_per_query_detailed.csv",
        help="Output CSV file for per-query *per paper* per-system RMS scores.",
    )
    parser.add_argument(
        "--out-per-query-cumulative-ald",
        default="rms_per_query_cumulative_ALD.csv",
        help="Output CSV file for cumulative per-query scores for ALD.",
    )
    parser.add_argument(
        "--out-per-query-cumulative-ale",
        default="rms_per_query_cumulative_ALE.csv",
        help="Output CSV file for cumulative per-query scores for ALE.",
    )
    parser.add_argument(
        "--out-best-per-query",
        default="rms_best_per_query.csv",
        help="Output CSV file with the best cumulative setting per query (per domain).",
    )
    parser.add_argument(
        "--out-per-query-avg-ald",
        default="rms_per_query_avg_ALD.csv",
        help="Output CSV file for per-query scores averaged over all systems (ALD).",
    )
    parser.add_argument(
        "--out-per-query-avg-ale",
        default="rms_per_query_avg_ALE.csv",
        help="Output CSV file for per-query scores averaged over all systems (ALE).",
    )
    parser.add_argument(
        "--out-overall",
        default="rms_overall.csv",
        help="Output CSV file for aggregated RMS scores per system.",
    )
    args = parser.parse_args()
    root_dir = os.path.abspath(args.root)

    per_query_rows: List[Dict[str, object]] = []

    n_queries = 0
    n_system_evals = 0

    for domain, paper, query_folder, query_path in iter_query_dirs(root_dir):
        gold_csv = os.path.join(query_path, "results_SPARQL.csv")
        if not os.path.exists(gold_csv):
            print(f"[WARN] Skipping query '{query_path}': no results_SPARQL.csv found.")
            continue

        n_queries += 1

        # Parse query index and label from folder name, e.g. 'Q01_reactor-LHAR-combinations'
        q_idx = query_folder
        q_label = ""
        if "_" in query_folder:
            q_idx, q_label = query_folder.split("_", 1)

        # Collect all results_*.csv files
        all_results = [
            f for f in os.listdir(query_path)
            if f.startswith("results_") and f.endswith(".csv")
        ]

        # Evaluate SPARQL vs itself (Setting 1) so it appears in the tables as upper bound.
        try:
            meta_sp = classify_system("results_SPARQL.csv")
        except Exception as e:
            print(f"[ERROR] Failed to classify SPARQL in {query_path}: {e}")
            meta_sp = {
                "system_name": "SPARQL",
                "system_label": "SPARQL",
                "setting_major": 1,
                "setting_id": "1",
                "variant": "symbolic",
                "is_gold": True,
            }
        # SPARQL vs SPARQL: should give 100 across the board, but we compute it explicitly.
        try:
            p_sp, r_sp, f_sp = compute_rms_for_query(gold_csv, gold_csv)
            n_system_evals += 1
            per_query_rows.append(
                {
                    "domain": domain,
                    "paper": paper,
                    "query_folder": query_folder,
                    "query_id": q_idx,
                    "query_label": q_label,
                    "gold_file": os.path.relpath(gold_csv, root_dir),
                    "prediction_file": os.path.relpath(gold_csv, root_dir),
                    "system_name": meta_sp["system_name"],
                    "system_label": meta_sp["system_label"],
                    "setting_major": meta_sp["setting_major"],
                    "setting_id": meta_sp["setting_id"],
                    "variant": meta_sp["variant"],
                    "is_gold_system": meta_sp["is_gold"],
                    "rms_precision": p_sp,
                    "rms_recall": r_sp,
                    "rms_f1": f_sp,
                }
            )
        except Exception as e:
            print(f"[ERROR] Failed to compute RMS for SPARQL in {query_path}: {e}")

        # Evaluate all other systems against SPARQL
        for fname in sorted(all_results):
            if fname == "results_SPARQL.csv":
                continue
            pred_csv = os.path.join(query_path, fname)
            rel_pred_csv = os.path.relpath(pred_csv, root_dir)
            try:
                meta = classify_system(fname)
            except Exception as e:
                print(f"[WARN] Skipping unrecognized results file '{fname}' in {query_path}: {e}")
                continue

            try:
                p, r, f = compute_rms_for_query(gold_csv, pred_csv)
            except Exception as e:
                print(f"[ERROR] Failed to compute RMS for '{rel_pred_csv}': {e}")
                continue

            n_system_evals += 1
            per_query_rows.append(
                {
                    "domain": domain,
                    "paper": paper,
                    "query_folder": query_folder,
                    "query_id": q_idx,
                    "query_label": q_label,
                    "gold_file": os.path.relpath(gold_csv, root_dir),
                    "prediction_file": rel_pred_csv,
                    "system_name": meta["system_name"],
                    "system_label": meta["system_label"],
                    "setting_major": meta["setting_major"],
                    "setting_id": meta["setting_id"],
                    "variant": meta["variant"],
                    "is_gold_system": meta["is_gold"],
                    "rms_precision": p,
                    "rms_recall": r,
                    "rms_f1": f,
                }
            )

    if not per_query_rows:
        print("[ERROR] No evaluations performed. Check the root directory structure and file names.")
        return

    per_query_df = pd.DataFrame(per_query_rows)

    # Global set of non-SPARQL *system configurations* (should be 21); used for constant denominator
    non_sparql_mask = ~per_query_df["is_gold_system"]  # only SPARQL has is_gold_system=True
    non_sparql_systems = sorted(
        per_query_df.loc[non_sparql_mask, "system_label"].unique()
    )
    n_non_sparql_systems = len(non_sparql_systems)
    print(f"[INFO] Non-SPARQL system configurations counted for averages: {n_non_sparql_systems}")

    # 1) Detailed per-query table (one row per (domain, paper, query_folder, system))
    out_per_query_detailed_path = os.path.abspath(args.out_per_query_detailed)
    per_query_df.to_csv(out_per_query_detailed_path, index=False)
    print(f"[INFO] Wrote detailed per-query RMS table to: {out_per_query_detailed_path}")


    def _make_cumulative_per_query(df_domain: pd.DataFrame, domain_name: str) -> pd.DataFrame:
        """Aggregate per_query_df to cumulative scores per (query_id, system) for one domain."""
        if df_domain.empty:
            return pd.DataFrame()

        group_cols_query = [
            "query_id",
            "query_label",
            "setting_major",
            "setting_id",
            "variant",
            "system_name",
            "system_label",
        ]

        cum_df = (
            df_domain
            .groupby(group_cols_query, dropna=False)
            .agg(
                n_instances=("rms_f1", "count"),  # how many paper-level instances of this query
                rms_precision_mean=("rms_precision", "mean"),
                rms_recall_mean=("rms_recall", "mean"),
                rms_f1_mean=("rms_f1", "mean"),
            )
            .reset_index()
            .sort_values(
                ["query_id", "setting_major", "setting_id", "variant", "system_name"]
            )
        )
        cum_df.insert(0, "domain", domain_name)
        return cum_df


    # 2) Cumulative per-query tables for ALD and ALE separately
    ald_df = per_query_df[per_query_df["domain"] == "ALD"]
    ale_df = per_query_df[per_query_df["domain"] == "ALE"]

    ald_cum_df = _make_cumulative_per_query(ald_df, "ALD")
    ale_cum_df = _make_cumulative_per_query(ale_df, "ALE")

    out_ald_path = os.path.abspath(args.out_per_query_cumulative_ald)
    ald_cum_df.to_csv(out_ald_path, index=False)
    print(f"[INFO] Wrote cumulative per-query RMS table for ALD to: {out_ald_path}")

    out_ale_path = os.path.abspath(args.out_per_query_cumulative_ale)
    ale_cum_df.to_csv(out_ale_path, index=False)
    print(f"[INFO] Wrote cumulative per-query RMS table for ALE to: {out_ale_path}")

    def _make_avg_per_query(
        cum_df: pd.DataFrame,
        all_non_sparql_systems: list[str],
    ) -> pd.DataFrame:
        """Average cumulative per-query scores across all non-SPARQL systems.

        - Excludes only SPARQL.
        - Uses a constant denominator = len(all_non_sparql_systems),
        treating missing system-query pairs as 0.
        """
        if cum_df.empty:
            return pd.DataFrame()

        # Drop SPARQL row(s) only
        df = cum_df[cum_df["system_name"] != "SPARQL"].copy()
        if df.empty:
            return pd.DataFrame()

        n_total = len(all_non_sparql_systems)

        group_cols = ["domain", "query_id", "query_label"]

        agg = (
            df.groupby(group_cols, dropna=False)
            .agg(
                sum_precision=("rms_precision_mean", "sum"),
                sum_recall=("rms_recall_mean", "sum"),
                sum_f1=("rms_f1_mean", "sum"),
                n_systems_present=("rms_f1_mean", "count"),
            )
            .reset_index()
        )

        agg["n_systems_total"] = n_total
        # Constant denominator: missing systems implicitly contribute 0
        agg["rms_precision_mean"] = agg["sum_precision"] / n_total
        agg["rms_recall_mean"] = agg["sum_recall"] / n_total
        agg["rms_f1_mean"] = agg["sum_f1"] / n_total

        agg = agg[
            [
                "domain",
                "query_id",
                "query_label",
                "n_systems_present",
                "n_systems_total",
                "rms_precision_mean",
                "rms_recall_mean",
                "rms_f1_mean",
            ]
        ].sort_values(["domain", "query_id"])

        return agg

    ald_avg_df = _make_avg_per_query(ald_cum_df, non_sparql_systems)
    ale_avg_df = _make_avg_per_query(ale_cum_df, non_sparql_systems)

    out_ald_avg_path = os.path.abspath(args.out_per_query_avg_ald)
    ald_avg_df.to_csv(out_ald_avg_path, index=False)
    print(f"[INFO] Wrote per-query average (across non-symbolic systems) RMS table for ALD to: {out_ald_avg_path}")

    out_ale_avg_path = os.path.abspath(args.out_per_query_avg_ale)
    ale_avg_df.to_csv(out_ale_avg_path, index=False)
    print(f"[INFO] Wrote per-query average (across non-symbolic systems) RMS table for ALE to: {out_ale_avg_path}")

    # 3) Best cumulative setting per query (per domain)
    all_cum_df = pd.concat([ald_cum_df, ale_cum_df], ignore_index=True)

    if not all_cum_df.empty:
        # Exclude SPARQL (symbolic baseline) from "best" selection
        # You can filter either by variant or by system_name; both are redundant.
        candidates_df = all_cum_df[all_cum_df["variant"] != "symbolic"]
        # Alternatively:
        # candidates_df = all_cum_df[all_cum_df["system_name"] != "SPARQL"]

        if candidates_df.empty:
            print("[WARN] No non-symbolic systems found; best-per-query table not written.")
        else:
            # For each (domain, query_id, query_label), pick the non-symbolic row with max F1
            group_keys = ["domain", "query_id", "query_label"]
            idx = candidates_df.groupby(group_keys)["rms_f1_mean"].idxmax()
            best_per_query_df = (
                candidates_df
                .loc[idx]
                .sort_values(["domain", "query_id", "setting_major", "setting_id"])
            )

            out_best_path = os.path.abspath(args.out_best_per_query)
            best_per_query_df.to_csv(out_best_path, index=False)
            print(f"[INFO] Wrote best-per-query RMS table to: {out_best_path}")
    else:
        print("[WARN] No cumulative per-query data; best-per-query table not written.")

    # Aggregate over all queries per system (overall results for all settings)
    # We average precision/recall/F1 across queries for each system.
    group_cols = ["setting_major", "setting_id", "variant", "system_name", "system_label"]
    overall_df = (
        per_query_df
        .groupby(group_cols, dropna=False)
        .agg(
            n_queries=("rms_f1", "count"),
            rms_precision_mean=("rms_precision", "mean"),
            rms_recall_mean=("rms_recall", "mean"),
            rms_f1_mean=("rms_f1", "mean"),
        )
        .reset_index()
        .sort_values(["setting_major", "setting_id", "variant", "system_name"])
    )

    out_overall_path = os.path.abspath(args.out_overall)
    overall_df.to_csv(out_overall_path, index=False)
    print(f"[INFO] Wrote overall RMS table to: {out_overall_path}")

    print(f"[INFO] Processed {n_queries} queries and {n_system_evals} system evaluations.")


if __name__ == "__main__":
    main()
