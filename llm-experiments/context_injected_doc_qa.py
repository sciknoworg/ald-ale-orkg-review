#!/usr/bin/env python3
"""
Setting 3.1: Context-injected prompting (single-shot document QA)

This script:
- Walks a dataset directory with structure: root/ALD|ALE/paperX/*.pdf + Qnn_* query folders
- For each paper, extracts text + tables from the PDF using pdfplumber via pdf_extractor.PDFExtractor
- For each Qnn_* folder, reads `natural_language_query_detailed.md`
- Sends the full PDF content + the detailed NL query to an open-weights LLM in a single context window
- Writes the model's answer to `results_[modelname].csv` inside each query folder
"""

import os
import re
import csv
import json
from pathlib import Path
from openai import OpenAI

from pdf_extractor import PDFExtractor  # assumes pdf_extractor.py is in the same directory

BASE_URL_DEFAULT = "https://chat-ai.academiccloud.de/v1"
MODEL_DEFAULT = "meta-llama-3.1-8b-instruct"

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


# --------------------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an assistant specialized in question answering over scientific PDFs.

You receive:
1) The full text and table contents extracted from a single scientific article.
2) A natural language query that specifies what information to extract and how to format the answer.

This corresponds to a context-injected, single-shot document QA setting:
- All relevant content (text and tables) from the paper is provided in one long context window.
- You must answer solely by reasoning over this provided context.
- Do NOT invent or hallucinate data not supported by the context.
- If information requested in the query is missing or ambiguous in the context, explicitly state that.

Always:
- Follow the instructions in the natural language query exactly.
- Respect any requested column names, units, aggregations, and ordering.
- Produce the output in the exact format specified in the query (e.g., one CSV table only, with a single header row).
- Do not add extra prose or explanations before or after the table unless the query explicitly asks for it.
"""

def build_user_prompt(pdf_content: str, nl_query_detailed: str) -> str:
    """
    Build the user prompt that provides the PDF content and the detailed NL query.
    """
    return f"""You are given the content of a scientific article (text and tables)
and a detailed natural language query describing what information to extract
and how to format the answer.

Use ONLY the information contained in the PDF content to answer the query.

<PDF_CONTENT>
{pdf_content}
</PDF_CONTENT>

<NATURAL_LANGUAGE_QUERY>
{nl_query_detailed}
</NATURAL_LANGUAGE_QUERY>

Now, using the PDF content above, answer the natural language query.
Follow the query's instructions exactly, especially the requested output format.
"""

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def sanitize_model_name(model: str) -> str:
    """
    Sanitize model name for use in file names.
    Keeps letters, digits, dot, dash, underscore; replaces others with '_'.
    """
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', model)


def extract_pdf_content_as_text(pdf_path: Path) -> str:
    """
    Use PDFExtractor to extract all relevant content from a PDF and return it
    as one long formatted string (text + tables).
    """
    extractor = PDFExtractor(str(pdf_path))
    # Exclude end matter (References, etc.) as in your original usage
    extractor.extract_all(exclude_end_matter=True)
    return extractor.get_formatted_output()


def is_query_folder(path: Path) -> bool:
    """
    Return True if the folder name looks like a query folder: QNN_* (e.g. Q01_reactor-LHAR).
    """
    return path.is_dir() and re.match(r"Q\d+_.*", path.name) is not None


def read_text_file(path: Path) -> str:
    """
    Read UTF-8 text from a file, or return empty string if it doesn't exist.
    """
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------------------
# Main processing logic
# --------------------------------------------------------------------------------------

def process_dataset(root: Path, client: OpenAI, model: str):
    """
    Process the full dataset:
    - For each category (ALD, ALE, ...)
    - For each paper folder
        - Extract PDF content once
        - For each query folder Qnn_*
            - Read natural_language_query_detailed.md
            - Call the LLM
            - Save result to results_[model].csv
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
            print(f"\n  Processing paper: {category_dir.name}/{paper_dir.name}")

            # Find PDFs in this paper folder
            pdf_files = list(paper_dir.glob("*.pdf"))
            if not pdf_files:
                print(f"    No PDF files found in {paper_dir}")
                continue

            if len(pdf_files) > 1:
                print(f"    WARNING: Multiple PDFs found in {paper_dir}, using the first one.")

            pdf_path = pdf_files[0]
            print(f"    Using PDF: {pdf_path.name}")

            # Extract PDF content once per paper
            try:
                print("    Extracting PDF content (text + tables)...")
                pdf_content = extract_pdf_content_as_text(pdf_path)
                print("    PDF extraction complete.")
            except Exception as e:
                print(f"    ERROR: Failed to extract PDF content: {e}")
                continue

            # Collect query folders like Q01_*, Q02_*, ...
            query_dirs = [d for d in paper_dir.iterdir() if is_query_folder(d)]
            if not query_dirs:
                print("    No query folders (Qnn_*) found in this paper folder.")
                continue

            print(f"    Found {len(query_dirs)} query folders.")

            for q_dir in sorted(query_dirs):
                print(f"\n    --- Processing query folder: {q_dir.name} ---")

                nl_query_path = q_dir / "natural_language_query_detailed.md"
                nl_query_detailed = read_text_file(nl_query_path)

                if not nl_query_detailed:
                    print(f"      WARNING: {nl_query_path.name} missing or empty, skipping.")
                    continue

                # Build user prompt
                user_prompt = build_user_prompt(pdf_content, nl_query_detailed)

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

                # Write result as CSV text file; we trust the model to output CSV per query.
                out_filename = f"results_{model_safe}.csv"
                out_path = q_dir / out_filename

                try:
                    # We just write the raw text; it is expected to be CSV.
                    out_path.write_text(answer, encoding="utf-8")
                    print(f"      Saved model output to {out_filename}")
                except Exception as e:
                    print(f"      ERROR writing results file: {e}")
                    continue

def process_single_query_folder(q_dir: Path, client: OpenAI, model: str):
    """
    Process exactly one query folder Qnn_* in context-injected mode:
    - Infer its paper folder and PDF
    - Extract full PDF content once
    - Read natural_language_query_detailed.md in this Q folder
    - Call the LLM and write results_[model].csv into this folder
    """
    if not q_dir.is_dir():
        print(f"ERROR: Query folder '{q_dir}' is not a directory.")
        return

    if not is_query_folder(q_dir):
        print(f"ERROR: '{q_dir.name}' does not look like a Qnn_* folder.")
        return

    paper_dir = q_dir.parent
    category_dir = paper_dir.parent

    print(f"\n{'=' * 80}")
    print("Single-query mode (Setting 3.1, context-injected)")
    print(f"Category (inferred): {category_dir.name}")
    print(f"Paper folder: {paper_dir.name}")
    print(f"Query folder: {q_dir.name}")
    print(f"{'=' * 80}")

    # Find PDF in this paper folder
    pdf_files = list(paper_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"  No PDF files found in paper folder {paper_dir}")
        return

    if len(pdf_files) > 1:
        print(f"  WARNING: Multiple PDFs found in {paper_dir}, using the first one.")

    pdf_path = pdf_files[0]
    print(f"  Using PDF: {pdf_path.name}")

    # Extract PDF content once
    try:
        print("  Extracting PDF content (text + tables)...")
        pdf_content = extract_pdf_content_as_text(pdf_path)
        print("  PDF extraction complete.")
    except Exception as e:
        print(f"  ERROR: Failed to extract PDF content: {e}")
        return

    model_safe = sanitize_model_name(model)

    print(f"\n  --- Processing query folder: {q_dir.name} ---")
    nl_query_path = q_dir / "natural_language_query_detailed.md"
    nl_query_detailed = read_text_file(nl_query_path)

    if not nl_query_detailed:
        print(f"    WARNING: {nl_query_path.name} missing or empty, aborting.")
        return

    user_prompt = build_user_prompt(pdf_content, nl_query_detailed)

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
        print(f"    ERROR during API call: {e}")
        return

    if not answer:
        print("    WARNING: Empty response from model, skipping write.")
        return

    out_filename = f"results_{model_safe}.csv"
    out_path = q_dir / out_filename

    try:
        out_path.write_text(answer, encoding="utf-8")
        print(f"    Saved model output to {out_filename}")
    except Exception as e:
        print(f"    ERROR writing results file: {e}")


def main():
    print("=== Setting 3.1: Context-injected document QA over PDFs ===")

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
