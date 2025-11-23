#!/usr/bin/env python3
"""
Setting 3.2: Retrieval-augmented generation (RAG) over PDF segments.

- Per paper:
    - Extracts text + tables from the PDF via pdf_extractor.PDFExtractor
    - Chunks the extracted content into smaller segments
    - Embeds all segments with an Ollama embedding model (e.g., nomic-embed-text:latest)

- Per query folder Qnn_*:
    - Reads metadata.json to get the modeled table number(s)
    - Builds a retrieval query from table labels (or falls back to the NL query)
    - Retrieves top-k most similar chunks via cosine similarity
    - Reads natural_language_query_detailed.md
    - Calls an LLM (via OpenAI-compatible endpoint) with the retrieved segments as context
    - Writes the model's answer to results_rag_[modelname].csv in the query folder
"""

import json
import math
import re
from pathlib import Path
from typing import List, Tuple

from openai import OpenAI
import ollama

from pdf_extractor import PDFExtractor  # assumes pdf_extractor.py is in the same directory

BASE_URL_DEFAULT = "https://chat-ai.academiccloud.de/v1"
MODEL_DEFAULT = "meta-llama-3.1-8b-instruct"
EMBEDDING_MODEL_DEFAULT = "nomic-embed-text:latest"  # Ollama embedding model
# Chunking / retrieval parameters
CHUNK_SIZE = 8000       # larger chunks so tables are not split
CHUNK_OVERLAP = 0     # overlap to catch tables that straddle boundaries
TOP_K = 1           # how many chunks to retrieve per query


# ==============================================================================
# Prompts
# ==============================================================================

SYSTEM_PROMPT = """
You are an assistant specialized in retrieval-augmented question answering over scientific PDFs.

You are operating in the following setting:
- The original PDF has been split into smaller text segments.
- A retrieval step has selected the segments most relevant to a table-focused query.
- You ONLY see these retrieved segments, not the full document.
- You must answer the query solely by reasoning over these retrieved segments.

Important constraints:
- Do NOT invent or hallucinate data that is not supported by the retrieved segments.
- If the retrieved segments do not contain sufficient information to fully answer the query,
  clearly state what is missing or ambiguous.
- Follow the instructions in the natural language query exactly, including:
  - Required columns and their names
  - Required units or conditions (e.g., temperature ranges)
  - Aggregation and ordering requirements
  - Any constraints on which rows to include
- Produce the output in the exact format specified in the query (e.g., one CSV table only).
- Do not add extra explanations before or after the table unless explicitly requested.

Your goal is to act as a precise, table-aware question answering system grounded
only in the retrieved PDF segments.
"""


def build_user_prompt(retrieved_segments: List[str], nl_query_detailed: str) -> str:
    """
    Build the user prompt that provides the retrieved segments and the detailed NL query.
    """
    segments_text = "\n\n--- SEGMENT BREAK ---\n\n".join(retrieved_segments)

    return f"""You are given a set of retrieved text segments from a scientific article
(text and tables converted to text) and a detailed natural language query describing
what information to extract and how to format the answer.

Use ONLY the information contained in the retrieved segments to answer the query.

<RETRIEVED_SEGMENTS>
{segments_text}
</RETRIEVED_SEGMENTS>

<NATURAL_LANGUAGE_QUERY>
{nl_query_detailed}
</NATURAL_LANGUAGE_QUERY>

Now, using the retrieved segments above, answer the natural language query.
Follow the query's instructions exactly, especially the requested output format.
"""


# ==============================================================================
# Utility helpers
# ==============================================================================

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
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def read_json_file(path: Path):
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_query_folder(path: Path) -> bool:
    """
    Return True if the folder name looks like a query folder: QNN_* (e.g. Q01_reactor-LHAR).
    """
    return path.is_dir() and re.match(r"Q\d+_.*", path.name) is not None


# ==============================================================================
# Chunking & embeddings (via Ollama)
# ==============================================================================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Simple character-based text chunking with overlap.
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= text_len:
            break
        start = end - chunk_overlap  # overlap

    return chunks


def embed_texts_ollama(texts: List[str], embedding_model: str) -> List[List[float]]:
    """
    Embed a list of texts using Ollama's embeddings API.

    Requires:
        - Ollama running locally
        - The specified embedding model pulled, e.g.:
          `ollama pull nomic-embed-text:latest`
    """
    vectors = []
    for t in texts:
        resp = ollama.embeddings(model=embedding_model, prompt=t)
        # Ollama returns {'embedding': [...]}
        vectors.append(resp["embedding"])
    return vectors


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two embedding vectors.
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(vec1, vec2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot / (math.sqrt(norm1) * math.sqrt(norm2))

def expand_with_neighbors(indices, total, radius=1):
    idx_set = set()
    for i in indices:
        for j in range(i - radius, i + radius + 1):
            if 0 <= j < total:
                idx_set.add(j)
    return sorted(idx_set)


def get_top_k_chunks(
    chunks: List[str],
    chunk_embeddings: List[List[float]],
    query_text: str,
    embedding_model: str,
    k: int = 10,
) -> List[Tuple[int, str]]:
    """
    Given precomputed embeddings for chunks and a query text, return the top-k
    most similar chunks as (index, chunk_text) pairs.
    """
    if not chunks or not chunk_embeddings:
        return []

    # Embed query via Ollama
    query_emb = embed_texts_ollama([query_text], embedding_model)[0]

    scored = []
    for idx, emb in enumerate(chunk_embeddings):
        score = cosine_similarity(query_emb, emb)
        scored.append((score, idx))

    scored.sort(reverse=True, key=lambda x: x[0])
    top = scored[:k]
    base_indices = [idx for (score, idx) in top]

    expanded_indices = expand_with_neighbors(base_indices, len(chunks), radius=2)

    return [(idx, chunks[idx]) for idx in expanded_indices]



# ==============================================================================
# Metadata → retrieval query
# ==============================================================================

def build_retrieval_query_from_metadata(metadata: dict, fallback_query: str) -> str:
    """
    Build a retrieval query string from metadata.json, using table labels if available.
    If no table labels are present, fall back to the description or the detailed NL query.
    """
    if not metadata:
        return fallback_query

    paper_ctx = metadata.get("paper_context", {})
    table_modeled = paper_ctx.get("table_modeled")
    tables_modeled = paper_ctx.get("tables_modeled")

    labels = []

    if isinstance(table_modeled, str) and table_modeled.strip():
        labels.append(table_modeled.strip())

    if isinstance(tables_modeled, list):
        for t in tables_modeled:
            label = t.get("label")
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())

    if labels:
        # e.g. "Table 2" or "Table 3; Table 5"
        return "; ".join(labels)

    # Otherwise fall back to description_short or the detailed NL query
    desc = metadata.get("description_short")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()

    return fallback_query


# ==============================================================================
# Per-paper processing
# ==============================================================================

def extract_pdf_content_as_text(pdf_path: Path) -> str:
    """
    Use PDFExtractor to extract all relevant content from a PDF and return it
    as one long formatted string (text + tables).
    """
    extractor = PDFExtractor(str(pdf_path))
    extractor.extract_all(exclude_end_matter=True)
    return extractor.get_formatted_output()


def process_dataset(
    root: Path,
    client: OpenAI,
    model: str,
    embedding_model: str,
    top_k: int = 10,
):
    """
    Process the full dataset:
    - For each category (ALD, ALE, ...)
    - For each paper folder:
        - Extract and chunk PDF content
        - Embed chunks (per paper, using Ollama)
        - For each query folder:
            - Read metadata.json -> retrieval query from table labels
            - Read natural_language_query_detailed.md
            - Retrieve top-k segments
            - Call LLM and write results_[model].csv
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

            # Chunk and embed this paper's content (per-paper index)
            print("    Chunking PDF content for RAG...")
            chunks = chunk_text(pdf_content, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
            print(f"    Created {len(chunks)} chunks.")

            if not chunks:
                print("    No chunks to index, skipping this paper.")
                continue

            print(f"    Embedding chunks with Ollama model '{embedding_model}'...")
            try:
                chunk_embeddings = embed_texts_ollama(chunks, embedding_model)
            except Exception as e:
                print(f"    ERROR: Failed to embed chunks via Ollama: {e}")
                continue
            print("    Chunk embeddings computed.")

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

                metadata_path = q_dir / "metadata.json"
                metadata = read_json_file(metadata_path)

                # Build retrieval query from table labels (or fall back to NL query)
                retrieval_query = build_retrieval_query_from_metadata(
                    metadata, fallback_query=nl_query_detailed
                )

                print(f"      Retrieval query: {retrieval_query!r}")

                # Retrieve top-k chunks
                try:
                    top_chunks = get_top_k_chunks(
                        chunks,
                        chunk_embeddings,
                        query_text=retrieval_query,
                        embedding_model=embedding_model,
                        k=top_k,
                    )
                except Exception as e:
                    print(f"      ERROR during retrieval: {e}")
                    continue

                if not top_chunks:
                    print("      WARNING: No chunks retrieved, skipping this query.")
                    continue
                
                print(f"      Retrieved {len(top_chunks)} chunks as context for this query.")

                # Extract just the texts (preserving ranking order)
                retrieved_texts = [text for (_, text) in top_chunks]

                # Build user prompt
                user_prompt = build_user_prompt(retrieved_texts, nl_query_detailed)

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
                out_filename = f"results_rag_{model_safe}.csv"
                out_path = q_dir / out_filename

                try:
                    out_path.write_text(answer, encoding="utf-8")
                    print(f"      Saved model output to {out_filename}")
                except Exception as e:
                    print(f"      ERROR writing results file: {e}")
                    continue


def process_single_query_folder(
    query_folder: Path,
    client: OpenAI,
    model: str,
    embedding_model: str,
    top_k: int = 10,
):
    """
    Process exactly one query folder Qnn_*:
    - Determine its paper folder and PDF
    - Extract + chunk + embed the paper once
    - Run RAG only for this single query folder
    """
    if not query_folder.is_dir():
        print(f"ERROR: Query folder '{query_folder}' is not a directory.")
        return

    if not is_query_folder(query_folder):
        print(f"ERROR: '{query_folder.name}' does not look like a Qnn_* folder.")
        return

    paper_dir = query_folder.parent
    category_dir = paper_dir.parent

    print(f"\n{'=' * 80}")
    print(f"Single-query mode")
    print(f"Category (inferred): {category_dir.name}")
    print(f"Paper folder: {paper_dir.name}")
    print(f"Query folder: {query_folder.name}")
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

    # Chunk + embed
    print("  Chunking PDF content for RAG...")
    chunks = chunk_text(pdf_content, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    print(f"  Created {len(chunks)} chunks.")

    if not chunks:
        print("  No chunks to index, aborting.")
        return

    print(f"  Embedding chunks with Ollama model '{embedding_model}'...")
    try:
        chunk_embeddings = embed_texts_ollama(chunks, embedding_model)
    except Exception as e:
        print(f"  ERROR: Failed to embed chunks via Ollama: {e}")
        return
    print("  Chunk embeddings computed.")

    model_safe = sanitize_model_name(model)

    print(f"\n  --- Processing query folder: {query_folder.name} ---")
    nl_query_path = query_folder / "natural_language_query_detailed.md"
    nl_query_detailed = read_text_file(nl_query_path)
    if not nl_query_detailed:
        print(f"    WARNING: {nl_query_path.name} missing or empty, aborting.")
        return

    metadata_path = query_folder / "metadata.json"
    metadata = read_json_file(metadata_path)

    retrieval_query = build_retrieval_query_from_metadata(
        metadata, fallback_query=nl_query_detailed
    )
    print(f"    Retrieval query: {retrieval_query!r}")

    try:
        top_chunks = get_top_k_chunks(
            chunks,
            chunk_embeddings,
            query_text=retrieval_query,
            embedding_model=embedding_model,
            k=top_k,
        )
    except Exception as e:
        print(f"    ERROR during retrieval: {e}")
        return

    if not top_chunks:
        print("    WARNING: No chunks retrieved, aborting.")
        return

    print(f"    Retrieved {len(top_chunks)} chunks as context for this query.")

    retrieved_texts = [text for (_, text) in top_chunks]
    user_prompt = build_user_prompt(retrieved_texts, nl_query_detailed)

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

    out_filename = f"results_rag_{model_safe}.csv"
    out_path = query_folder / out_filename

    try:
        out_path.write_text(answer, encoding="utf-8")
        print(f"    Saved model output to {out_filename}")
    except Exception as e:
        print(f"    ERROR writing results file: {e}")


# ==============================================================================
# Main
# ==============================================================================

def main():
    print("=== Setting 3.2: RAG over PDF segments (Ollama embeddings) ===")

    mode = input("Run mode: [1] full dataset, [2] single query folder (1/2) [1]: ").strip() or "1"

    api_key = input("API key (for chat/completions): ").strip()
    base_url = input(f"Base URL [{BASE_URL_DEFAULT}]: ").strip() or BASE_URL_DEFAULT
    model = input(f"Chat model name [{MODEL_DEFAULT}]: ").strip() or MODEL_DEFAULT
    embedding_model = input(
        f"Ollama embedding model [{EMBEDDING_MODEL_DEFAULT}]: "
    ).strip() or EMBEDDING_MODEL_DEFAULT

    # OpenAI-compatible client for chat completions (AcademicCloud)
    client = OpenAI(api_key=api_key, base_url=base_url)

    if mode == "2":
        # Single query folder mode – expect absolute path
        query_path_str = input("Absolute path to query folder (Qnn_*): ").strip()
        q_dir = Path(query_path_str).expanduser().resolve()
        process_single_query_folder(q_dir, client, model, embedding_model, top_k=TOP_K)
    else:
        # Full dataset mode
        dataset_root = input("Dataset root directory: ").strip()
        root = Path(dataset_root).expanduser().resolve()
        if not root.is_dir():
            print("ERROR: Invalid dataset directory.")
            return
        process_dataset(root, client, model, embedding_model, top_k=TOP_K)


if __name__ == "__main__":
    main()
