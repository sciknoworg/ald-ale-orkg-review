#!/usr/bin/env python3
"""
Neurosymbolic table QA over ORKG CSV inputs.

This script replaces PDF-based context with ORKG-derived CSV tables.

Per query folder Qnn_*:
- Reads metadata.json to determine which table(s) from the paper are modeled
  (table_modeled for single-table, tables_modeled for cross-table).
- Locates corresponding CSV files in the same folder, following naming patterns like:
    orkg_table2_symbolic_input.csv
    orkg_tableII_symbolic_input.csv
- Reads natural_language_query_detailed.md as the detailed query.
- Builds an LLM prompt where each CSV is preceded by its paper table identifier, e.g.:

    Table 2

    <CSV>
    ...csv content...
    </CSV>

    Table 3

    <CSV>
    ...csv content...
    </CSV>

- Sends this neurosymbolic context + NL query to an open-weights LLM.
- Writes the model's answer to results_neurosymbolic_{modelname}.csv
  inside each Qnn_* folder.

Two modes:
  [1] Full dataset: walk root/ALD|ALE/paperX/Qnn_*
  [2] Single query folder: run for exactly one Qnn_* folder given by absolute path.
"""

import json
import re
from pathlib import Path
from typing import List, Tuple, Optional

from openai import OpenAI

BASE_URL_DEFAULT = "https://chat-ai.academiccloud.de/v1"
MODEL_DEFAULT = "meta-llama-3.1-8b-instruct"


# --------------------------------------------------------------------------------------
# Utility helpers
# --------------------------------------------------------------------------------------

def strip_markdown_code_fences(text: str) -> str:
    """
    Remove surrounding Markdown triple backtick fences (``` or ```csv, ```table, etc.)
    from the given text, if present.
    """
    if not text:
        return text

    s = text.strip()

    # Regex for: ```<optional-lang>\n...content...\n``` (or without final newline)
    fence_match = re.match(r"^```[a-zA-Z0-9_-]*\s*\n(.*?)(\n```)?\s*$",
                           s, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Fallback: generic triple-backtick wrapper
    if s.startswith("```") and s.endswith("```"):
        return s[3:-3].strip()

    return s


def sanitize_model_name(model: str) -> str:
    """
    Sanitize model name for use in file names.
    Keeps letters, digits, dot, dash, underscore; replaces others with '_'.
    """
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', model)


def read_text_file(path: Path) -> str:
    """
    Read UTF-8 text from a file, or return empty string if it doesn't exist.
    """
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def read_json_file(path: Path):
    """
    Read a JSON file and return its content, or None if missing/invalid.
    """
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_query_folder(path: Path) -> bool:
    """
    Return True if the folder name looks like a query folder: QNN_* (e.g. Q01_reactor-LHAR).
    """
    return path.is_dir() and re.match(r"Q\d+_.*", path.name) is not None


# --------------------------------------------------------------------------------------
# Table label ↔ CSV matching
# --------------------------------------------------------------------------------------

def int_to_roman(num: int) -> str:
    """
    Convert integer to (upper-case) Roman numeral. Handles typical table index ranges.
    """
    if num <= 0:
        return ""
    vals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    res = []
    x = num
    for v, sym in vals:
        while x >= v:
            res.append(sym)
            x -= v
    return "".join(res)


def normalize_str(s: str) -> str:
    """
    Lowercase and remove all non-alphanumeric characters.
    """
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def extract_table_labels_from_metadata(metadata: dict) -> List[str]:
    """
    From metadata.json, extract a list of table labels, e.g. ["Table 2", "Table 3"].
    Handles both single-table and cross-table metadata variants.
    """
    if not metadata:
        return []

    labels = []
    paper_ctx = metadata.get("paper_context", {})

    table_modeled = paper_ctx.get("table_modeled")
    if isinstance(table_modeled, str) and table_modeled.strip():
        labels.append(table_modeled.strip())

    tables_modeled = paper_ctx.get("tables_modeled")
    if isinstance(tables_modeled, list):
        for t in tables_modeled:
            label = t.get("label")
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())

    return labels


def match_csv_for_label(label: str, csv_files: List[Path]) -> Optional[Path]:
    """
    Given a table label like "Table 2" or "Table II" and a list of CSV files
    (e.g. orkg_table2_symbolic_input.csv, orkg_tableII_symbolic_input.csv),
    try to find the best matching CSV file.

    Matching strategy:
      - Normalize label and filenames (lowercase, strip non-alnum)
      - Use numeric part (if any) to also consider Roman forms.
    """
    if not csv_files:
        return None

    label_norm = normalize_str(label)  # e.g. "table2" or "tableii"
    candidate_norms = {label_norm}

    # If label contains a numeric part, also consider Roman numeral variants.
    m = re.search(r"(\d+)", label)
    if m:
        num = int(m.group(1))
        roman = int_to_roman(num)  # e.g. "II"
        if roman:
            candidate_norms.add(normalize_str("table" + roman))
            candidate_norms.add(normalize_str(roman))

    # Also consider the "table" + stripped remainder if it looks Roman-like.
    # (e.g. "Table II" → "tableii")
    label_no_table = re.sub(r'\btable\b', '', label, flags=re.IGNORECASE).strip()
    if label_no_table:
        candidate_norms.add(normalize_str("table" + label_no_table))

    # Try to find a filename whose normalized form contains any candidate norm.
    for csv_path in csv_files:
        name_norm = normalize_str(csv_path.stem)  # e.g. "orkgtable2symbolicinput"
        for cn in candidate_norms:
            if cn and cn in name_norm:
                return csv_path

    return None


def derive_label_from_filename(csv_path: Path) -> str:
    """
    If no metadata label is available, derive a generic table label from the filename
    e.g. orkg_table2_symbolic_input.csv -> "Table 2"
         orkg_tableII_symbolic_input.csv -> "Table II"
    """
    stem = csv_path.stem  # e.g. "orkg_table2_symbolic_input"
    # Try to find "table..." segment
    m = re.search(r'table([a-z0-9]+)', stem, flags=re.IGNORECASE)
    if m:
        suffix = m.group(1)
        # If suffix is digits, we can label as "Table <digits>"
        if suffix.isdigit():
            return f"Table {suffix}"
        else:
            # Likely Roman or other text
            return f"Table {suffix.upper()}"

    # Fallback
    return f"Table from {stem}"


def load_neurosymbolic_tables(q_dir: Path) -> List[Tuple[str, str]]:
    """
    Load neurosymbolic table(s) for a given query folder.

    Returns a list of (table_label, csv_text) pairs, where table_label is
    the paper's table identifier (e.g. "Table 2") and csv_text is the raw CSV content.
    """
    metadata_path = q_dir / "metadata.json"
    metadata = read_json_file(metadata_path) or {}

    # Find candidate CSV files that look like ORKG table inputs
    csv_files = [
        p for p in q_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".csv"
        and p.name.lower().startswith("orkg_table")
        and p.name.lower().endswith("_symbolic_input.csv")
    ]

    if not csv_files:
        print(f"    WARNING: No ORKG table CSV files found in {q_dir}")
        return []

    labels = extract_table_labels_from_metadata(metadata)

    tables: List[Tuple[str, str]] = []

    if labels:
        # Use metadata labels to select matching CSVs
        used_paths = set()
        for label in labels:
            csv_match = match_csv_for_label(label, csv_files)
            if not csv_match:
                print(f"    WARNING: No CSV file matched label '{label}' in {q_dir}")
                continue
            if csv_match in used_paths:
                # Already added (e.g. repeated label), skip
                continue
            used_paths.add(csv_match)
            csv_text = read_text_file(csv_match)
            tables.append((label, csv_text))

        if tables:
            return tables
        # If labels existed but none matched, fall through to generic fallback.

    # Fallback: no usable labels or no matches, include all CSVs with derived labels.
    for csv_path in sorted(csv_files):
        label = derive_label_from_filename(csv_path)
        csv_text = read_text_file(csv_path)
        tables.append((label, csv_text))

    return tables


# --------------------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an assistant specialized in neurosymbolic table question answering.

You receive:
1) One or more machine-actionable tables exported from ORKG comparisons, in CSV format.
2) A detailed natural language query that specifies what information to compute and how to format the answer.

Context:
- Each CSV corresponds to a specific table in the source paper (e.g., "Table 2", "Table 3").
- In the prompt, every CSV is preceded by its paper table identifier.
- Tables may come from a single table ("single-table" queries) or multiple tables ("cross-table" queries).

Your tasks and constraints:
- Use ONLY the data in the provided CSV tables to answer the query.
- Do NOT invent or hallucinate values that are not derivable from the tables.
- If the query requires information that is not present or is ambiguous in the tables, explicitly state this.
- Carefully follow the detailed query instructions, including:
  - Which rows to include or filter.
  - Required column names and units.
  - Any aggregations, derived metrics, or joins across tables.
  - Sorting, ranking, or grouping requirements.
- Produce the output in the exact format requested in the query
  (typically a single CSV table with one header row and one row per result).
- Do not add extra narrative text before or after the output table unless the query explicitly asks for it.
"""

def build_user_prompt(
    tables: List[Tuple[str, str]],
    nl_query_detailed: str,
) -> str:
    """
    Build the user prompt that provides the neurosymbolic tables and the detailed NL query.

    `tables` is a list of (table_label, csv_text) pairs.
    """
    table_blocks = []
    for label, csv_text in tables:
        block = f"""{label}

<CSV>
{csv_text}
</CSV>"""
        table_blocks.append(block)

    tables_section = "\n\n".join(table_blocks)

    return f"""You are given one or more machine-actionable tables derived from ORKG comparisons.
Each table is provided in CSV format and is preceded by its identifier in the source paper
(e.g., "Table 2"). You are also given a detailed natural language query that specifies the
task and the desired output format.

Use ONLY the information contained in the CSV tables to answer the query.

<NEUROSYMBOLIC_TABLES>
{tables_section}
</NEUROSYMBOLIC_TABLES>

<NATURAL_LANGUAGE_QUERY>
{nl_query_detailed}
</NATURAL_LANGUAGE_QUERY>

Now, using ONLY the data in the CSV tables above, answer the natural language query.
Follow the query's instructions exactly, especially the requested output format.
"""


# --------------------------------------------------------------------------------------
# Main processing logic
# --------------------------------------------------------------------------------------

def process_single_query_folder(q_dir: Path, client: OpenAI, model: str):
    """
    Process exactly one query folder Qnn_* in neurosymbolic CSV mode:
    - Load metadata.json to determine which tables to use.
    - Load the corresponding ORKG CSV tables.
    - Read natural_language_query_detailed.md.
    - Call the LLM and write results_neurosymbolic_{model}.csv into this folder.
    """
    if not q_dir.is_dir():
        print(f"ERROR: Query folder '{q_dir}' is not a directory.")
        return

    if not is_query_folder(q_dir):
        print(f"ERROR: '{q_dir.name}' does not look like a Qnn_* folder.")
        return

    print(f"\n{'=' * 80}")
    print("Single-query mode: Neurosymbolic table QA over ORKG CSV inputs")
    print(f"Query folder: {q_dir}")
    print(f"{'=' * 80}")

    # Load tables
    tables = load_neurosymbolic_tables(q_dir)
    if not tables:
        print("  ERROR: No neurosymbolic tables could be loaded; aborting.")
        return

    # Load detailed NL query
    nl_query_path = q_dir / "natural_language_query_detailed.md"
    nl_query_detailed = read_text_file(nl_query_path)
    if not nl_query_detailed:
        print(f"  ERROR: {nl_query_path.name} missing or empty; aborting.")
        return

    user_prompt = build_user_prompt(tables, nl_query_detailed)
    model_safe = sanitize_model_name(model)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        answer_raw = (resp.choices[0].message.content or "").strip()
        answer = strip_markdown_code_fences(answer_raw)
    except Exception as e:
        print(f"  ERROR during API call: {e}")
        return

    if not answer:
        print("  WARNING: Empty response from model, skipping write.")
        return

    out_filename = f"results_neurosymbolic_{model_safe}.csv"
    out_path = q_dir / out_filename

    try:
        out_path.write_text(answer, encoding="utf-8")
        print(f"  Saved model output to {out_filename}")
    except Exception as e:
        print(f"  ERROR writing results file: {e}")


def process_dataset(root: Path, client: OpenAI, model: str):
    """
    Process the full dataset in neurosymbolic mode:

    Expected structure:
      root/
        ├── ALD/
        │   ├── paper1/
        │   │   ├── Q01_.../
        │   │   │   ├── metadata.json
        │   │   │   ├── natural_language_query_detailed.md
        │   │   │   └── orkg_table*_symbolic_input.csv
        │   │   └── Q02_.../
        │   └── paper2/
        └── ALE/
            └── paperX/
                └── Qnn_.../

    For each Qnn_* folder:
      - Load neurosymbolic tables from CSV
      - Read natural_language_query_detailed.md
      - Call LLM
      - Write results_neurosymbolic_{model}.csv
    """
    if not root.is_dir():
        print(f"ERROR: Dataset root '{root}' is not a directory.")
        return

    categories = [d for d in root.iterdir() if d.is_dir()]
    if not categories:
        print(f"No category folders found under {root}")
        return

    print(f"Found {len(categories)} category folders")

    model_safe = sanitize_model_name(model)

    for category_dir in sorted(categories):
        print(f"\n{'=' * 80}")
        print(f"Processing category: {category_dir.name}")
        print(f"{'=' * 80}")

        paper_dirs = [d for d in category_dir.iterdir() if d.is_dir()]
        print(f"  Found {len(paper_dirs)} paper folders in {category_dir.name}")

        for paper_dir in sorted(paper_dirs):
            print(f"\n  Processing paper folder: {category_dir.name}/{paper_dir.name}")

            query_dirs = [d for d in paper_dir.iterdir() if is_query_folder(d)]
            if not query_dirs:
                print("    No query folders (Qnn_*) found in this paper folder.")
                continue

            print(f"    Found {len(query_dirs)} query folders.")

            for q_dir in sorted(query_dirs):
                print(f"\n    --- Processing query folder: {q_dir.name} ---")

                # Load tables
                tables = load_neurosymbolic_tables(q_dir)
                if not tables:
                    print("      ERROR: No neurosymbolic tables could be loaded; skipping.")
                    continue

                # Load detailed NL query
                nl_query_path = q_dir / "natural_language_query_detailed.md"
                nl_query_detailed = read_text_file(nl_query_path)
                if not nl_query_detailed:
                    print(f"      WARNING: {nl_query_path.name} missing or empty; skipping.")
                    continue

                user_prompt = build_user_prompt(tables, nl_query_detailed)

                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.0,
                    )
                    answer_raw = (resp.choices[0].message.content or "").strip()
                    answer = strip_markdown_code_fences(answer_raw)
                except Exception as e:
                    print(f"      ERROR during API call: {e}")
                    continue

                if not answer:
                    print("      WARNING: Empty response from model, skipping write.")
                    continue

                out_filename = f"results_neurosymbolic_{model_safe}.csv"
                out_path = q_dir / out_filename

                try:
                    out_path.write_text(answer, encoding="utf-8")
                    print(f"      Saved model output to {out_filename}")
                except Exception as e:
                    print(f"      ERROR writing results file: {e}")
                    continue


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def main():
    print("=== Neurosymbolic table QA over ORKG CSV inputs ===")

    mode = input("Run mode: [1] full dataset, [2] single query folder (1/2) [1]: ").strip() or "1"

    api_key = input("API key: ").strip()
    base_url = input(f"Base URL [{BASE_URL_DEFAULT}]: ").strip() or BASE_URL_DEFAULT
    model = input(f"Model name [{MODEL_DEFAULT}]: ").strip() or MODEL_DEFAULT

    client = OpenAI(api_key=api_key, base_url=base_url)

    if mode == "2":
        # Single query folder mode – expect absolute path
        query_path_str = input("Absolute path to query folder (Qnn_*): ").strip()
        q_dir = Path(query_path_str).expanduser().resolve()
        process_single_query_folder(q_dir, client, model)
    else:
        # Full dataset mode
        dataset_root = input("Dataset root directory: ").strip()
        root = Path(dataset_root).expanduser().resolve()
        if not root.is_dir():
            print("ERROR: Invalid dataset directory.")
            return
        process_dataset(root, client, model)


if __name__ == "__main__":
    main()
