import os
import json
import csv
from pathlib import Path
from openai import OpenAI

BASE_URL_DEFAULT = "https://chat-ai.academiccloud.de/v1"
MODEL_DEFAULT = "meta-llama-3.1-8b-instruct"

SYSTEM_PROMPT = """You are an expert in SPARQL, scientific tables, and neurosymbolic reasoning.

Your job: Convert a SPARQL query (designed for an ORKG machine-actionable table)
into a detailed, precise, and self-contained natural-language query that a
conversational LLM (with access only to the PDF of the article and its tables,
NOT to ORKG or SPARQL) could answer reliably.

The natural-language query MUST:

1. Refer to the actual table number from the article (e.g., “Table 2”).
2. Refer to column names or column semantics, not SPARQL predicates or ORKG property IDs.
3. Include all logical conditions from the SPARQL query.
4. Avoid mentioning ORKG, SPARQL, URIs, or IDs.
5. Explicitly instruct the LLM that the result MUST be returned:
   - as **one single table only**,
   - **in CSV format**,
   - with one row per result,
   - with the same columns as the sample result table header (excluding ID or ORKG-specific columns).

Output: ONLY the final NL query text.
""".strip()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def read_metadata(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_csv_sample(path: Path, max_rows: int = 5) -> str:
    if not path.is_file():
        return ""
    rows = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= max_rows:
                break
    return "\n".join(",".join(r) for r in rows)


def extract_table_number(metadata: dict) -> str:
    try:
        return metadata["paper_context"]["table_modeled"]
    except Exception:
        return "the table in the article corresponding to this query"


def build_user_prompt(sparql: str, nl_short: str, csv_sample: str, metadata: dict | None):
    table_number = extract_table_number(metadata) if metadata else "the table in the article"

    paper_title = metadata.get("paper_context", {}).get("paper", {}).get("title", "Unknown") if metadata else "Unknown"
    paper_doi = metadata.get("paper_context", {}).get("paper", {}).get("doi", "Unknown") if metadata else "Unknown"
    meta_block = json.dumps(metadata, indent=2) if metadata else "None"

    return f"""You must now generate the detailed natural-language query.

Paper title: {paper_title}
Paper DOI: {paper_doi}
Table referenced: {table_number}

[SPARQL QUERY]
```sparql
{sparql}
```

[SHORT ORIGINAL NL QUERY]
```text
{nl_short}
```

[SAMPLE RESULT TABLE SNIPPET]
```csv
{csv_sample}
```

[METADATA JSON]
```json
{meta_block}
```

Using all the above, write ONE detailed natural-language query that:

- Precisely describes which rows should be retrieved from {table_number}.
- Refers to meaningful column names, not ORKG IDs.
- **Clearly instructs that the result must be returned as exactly ONE table only.**
- **Explicitly instructs that the output table must be provided in CSV format.**
- Ensures the output table has one row per result.
- Uses the same column headers as the sample result table (excluding ORKG/ID columns).

Return ONLY the final NL query text.
""".strip()


def is_query_folder(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "query.sparql").is_file()
        and (path / "natural_language_query.md").is_file()
        and (path / "results_example.csv").is_file()
        and (path / "metadata.json").is_file()
    )


def collect_query_folders(root_path: Path):
    folders = []
    for domain in ["ALD", "ALE"]:
        domain_path = root_path / domain
        if not domain_path.is_dir():
            continue
        for dirpath, _, _ in os.walk(domain_path):
            p = Path(dirpath)
            if is_query_folder(p):
                folders.append(p)
    return sorted(set(folders))


def main():
    print("=== Generate detailed NL queries from SPARQL ===")

    dataset_root = input("Dataset root directory: ").strip()
    api_key = input("API key: ").strip()
    base_url = input(f"Base URL [{BASE_URL_DEFAULT}]: ").strip() or BASE_URL_DEFAULT
    model = input(f"Model name [{MODEL_DEFAULT}]: ").strip() or MODEL_DEFAULT

    root = Path(dataset_root).expanduser().resolve()
    if not root.is_dir():
        print("ERROR: Invalid dataset directory.")
        return

    client = OpenAI(api_key=api_key, base_url=base_url)

    query_folders = collect_query_folders(root)
    if not query_folders:
        print("No query folders found.")
        return

    print(f"Found {len(query_folders)} query folders.")

    for q_dir in query_folders:
        print(f"\n--- Processing {q_dir} ---")
        out_path = q_dir / "natural_language_query_detailed.md"  # Always overwrite

        sparql = read_text(q_dir / "query.sparql")
        nl_short = read_text(q_dir / "natural_language_query.md")
        csv_sample = read_csv_sample(q_dir / "results_example.csv")
        metadata = read_metadata(q_dir / "metadata.json")

        prompt = build_user_prompt(sparql, nl_short, csv_sample, metadata)

        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            detailed_nl = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"  ERROR during API call: {e}")
            continue

        try:
            out_path.write_text(detailed_nl + "\n", encoding="utf-8")
            print(f"  Wrote (overwritten): {out_path}")
        except Exception as e:
            print(f"  ERROR writing file: {e}")


if __name__ == "__main__":
    main()
