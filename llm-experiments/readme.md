# ALD/ALE Dataset - LLM Experiments

This repository contains tools for working with the ALD/ALE dataset for LLM-based table extraction experiments.

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

---

## 1. NL Query Generator (Single-Table CSV Output)

The script `nl_query_generator_csv_onetable.py` automatically converts each SPARQL query in the ALD/ALE dataset into a detailed natural-language query.

### Purpose
These NL queries are intended for LLM experiments where the model is given only the **PDF of the scientific article** and must reproduce the same table that the SPARQL query returns over the ORKG comparison.

### What It Does
For each query folder, the script:
- Reads the SPARQL query, lightweight NL query, metadata, and example result table
- Uses an LLM to generate a **fully detailed natural-language query** that:
  - Refers to the correct table in the article (e.g., "Table 2")
  - Describes the precise filtering/selection logic encoded in the SPARQL
  - Requires the LLM to return **exactly one table**
  - Requires the output table to be in **CSV format**
  - Uses the same column headers as the sample result table (excluding ORKG/ID columns)
- Writes (or overwrites) the output to `natural_language_query_detailed.md` in each query's folder

### Running the Script
From the project directory:
```bash
python llm-experiments/nl_query_generator_csv_onetable.py
```

### Example Run (Windows)
```bash
python llm-experiments\nl_query_generator_csv_onetable.py
=== Generate detailed NL queries from SPARQL ===
Dataset root directory: C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset
API key: ***
Base URL [https://chat-ai.academiccloud.de/v1]:
Model name [meta-llama-3.1-8b-instruct]: mistral-large-instruct
Found 33 query folders.
```

The script will then generate and overwrite `natural_language_query_detailed.md` for every query folder in the dataset.

---

## 2. PDF Text and Table Extraction

The `pdf_extractor.py` script extracts text and tables from PDFs in the ALD/ALE folder structure for use in in-context learning experiments.

### Key Features
- **Clean Text Extraction**: Removes excessive whitespace while preserving content
- **Automatic End Matter Exclusion**: Stops extraction at end matter sections:
  - References/Bibliography
  - Funding sources
  - Conflicts of interest
  - Acknowledgements
- **Output Location**: JSON files saved alongside each PDF (not in separate directory)
- **Importable Function**: Use `extract_from_folder()` in your own workflows

### Install Dependencies

```bash
pip install pdfplumber
```

Or use the provided requirements file:

```bash
pip install -r requirements.txt
```

### Usage

```bash
# Process all PDFs in the folder structure
python pdf_extractor.py /path/to/root
```

### Expected Folder Structure
```
root/
├── ALD/
│   ├── paper1/
│   │   ├── document.pdf
│   │   └── document_extracted.json  # Created by script
│   └── paper2/
│       ├── research.pdf
│       └── research_extracted.json  # Created by script
└── ALE/
    └── paperX/
        ├── study.pdf
        └── study_extracted.json      # Created by script
```

### Output Format

Each PDF generates a JSON file (e.g., `document_extracted.json`) containing:
- Metadata (title, author, dates, etc.)
- Page-by-page text content (excludes: References, Funding, Acknowledgements, Conflicts of interest)
- Tables extracted from each page (when detectable)
- Page dimensions

**Note on tables**: Simple tables are extracted. Complex tables (rotated, merged cells) may be embedded in text content instead, which is actually preferable for LLM processing.

### Using in Your Workflow

Import the extraction function in your Python code:

```python
from pdf_extractor import extract_from_folder

# Extract content from all PDFs (silent mode, excludes end matter)
results = extract_from_folder('/path/to/root')

# Access extracted data
for category in results['categories']:
    for paper in results['categories'][category]['papers']:
        for pdf_name, pdf_data in results['categories'][category]['papers'][paper]['pdf_files'].items():
            # pdf_data contains: metadata, pages (with text and tables)
            for page in pdf_data['pages']:
                text = page['text']          # Clean text without end matter
                tables = page['tables']      # List of tables (when detected)
```

### Advanced Options

```python
# Include end matter sections
results = extract_from_folder('/path/to/root', exclude_references=False)

# Show progress during extraction
results = extract_from_folder('/path/to/root', verbose=True)
```

---

## 3. Setting 3.1 – Context-injected Document QA (Single-Shot)

In this setting, **the entire extracted PDF content** (text + tables) for a paper is sent to the LLM in a **single context window**, together with the detailed natural-language query from each `Qnn_*` folder.

The script:

- Uses `pdf_extractor.PDFExtractor` to extract text + tables for each `paperX/*.pdf`
- Reads `natural_language_query_detailed.md` in each `Qnn_*` folder
- Calls an open-weights LLM via an OpenAI-compatible endpoint
- Writes the model’s answer as CSV to `results_[modelname].csv` inside each query folder

The script supports **two modes**:

### 3.1.1 Full-dataset mode

Runs Setting 3.1 for **all** queries in the dataset.

```bash
python llm-experiments/context_injected_doc_qa.py
```

You will be prompted for:

- `Dataset root directory` (e.g. `C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset`)
- `API key`
- `Base URL` (e.g. `https://chat-ai.academiccloud.de/v1`)
- `Model name` (e.g. `gemma-3-27b-it`, `qwen3-32b`, etc.)

For each `ALD` / `ALE` paper and each `Qnn_*` folder, the script:

1. Extracts the PDF once per paper.
2. Sends the **full extracted content** plus the query in `natural_language_query_detailed.md` to the LLM.
3. Saves the answer to:

```text
ALD/paperX/Qnn_*/results_[modelname].csv
ALE/paperY/Qmm_*/results_[modelname].csv
```

The output is expected to be **one CSV table only**, as specified in the detailed NL query.

### 3.1.2 Single-query mode

Runs Setting 3.1 for **one specific query folder** only (useful for debugging a single query).

```bash
python llm-experiments/context_injected_doc_qa.py
```

When asked for the run mode, choose:

- `Run mode: [1] full dataset, [2] single query folder (1/2) [1]: 2`

You will then be prompted for:

- `API key`, `Base URL`, `Model name` (as above)
- `Absolute path to query folder (Qnn_*)`, e.g.:

```text
C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset\ALD\paper3\Q14_RE-MOSLED-efficiency-per-volt
```

The script will:

1. Infer the corresponding paper folder and PDF.
2. Extract the full PDF content.
3. Read `natural_language_query_detailed.md` in that `Qnn_*` folder.
4. Call the LLM once and write:

```text
Q14_RE-MOSLED-efficiency-per-volt/results_[modelname].csv
```

---

## 4. Setting 3.2 – Retrieval-augmented Generation (RAG) over PDF Segments

In this setting, the extracted PDF content is **chunked, embedded, and indexed**, and only the **most relevant chunks** are supplied to the LLM as context.

The Setting 3.2 script:

- Uses `pdf_extractor.PDFExtractor` to extract text + tables per paper
- Chunks the extracted content into segments
- Embeds all chunks with an **Ollama** embedding model (default: `nomic-embed-text:latest`)
- For each query folder:
  - Reads `metadata.json` to derive a retrieval query (e.g. table labels like “Table 2”, “Table 3 + Table 5”)
  - Retrieves top-k relevant chunks via cosine similarity
  - Reads `natural_language_query_detailed.md`
  - Calls the LLM with **only the retrieved chunks** as context
  - Writes the answer to `results_rag_[modelname].csv` in the query folder

### 4.1 Installation

```bash
pip install ollama
```

Ensure Ollama is running and pull the embedding model:

```bash
ollama pull nomic-embed-text:latest
```

You also need the same dependencies as for `pdf_extractor.py` and the Setting 3.1 script (`openai`, `pdfplumber`, etc.).

### 4.2 Full-dataset mode

From the project directory (where `rag_pdf_segments_doc_qa.py` and `pdf_extractor.py` live):

```bash
python llm-experiments/rag_pdf_segments_doc_qa.py
```

You will be prompted for:

- `Run mode` → choose `1` for full dataset
- `Dataset root directory` (e.g. `C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset`)
- `API key (for chat/completions)`
- `Base URL` (e.g. `https://chat-ai.academiccloud.de/v1`)
- `Chat model name` (e.g. `gemma-3-27b-it`, `qwen3-30b-a3b-instruct-2507`, `llama-3.3-70b-instruct`, etc.)
- `Ollama embedding model` (press Enter to use `nomic-embed-text:latest`)

For each paper, the script:

1. Extracts the PDF once.
2. Chunks and embeds the content with Ollama.
3. For each `Qnn_*` folder:
   - Builds a retrieval query from `metadata.json` (table labels / description).
   - Retrieves the top-k chunks (plus neighbors) from the per-paper index.
   - Calls the chat model for that query only.
   - Writes:

```text
ALD/paperX/Qnn_*/results_rag_[modelname].csv
ALE/paperY/Qmm_*/results_rag_[modelname].csv
```

The number and size of chunks is controlled in the script via:

```python
CHUNK_SIZE      # characters per chunk
CHUNK_OVERLAP   # overlap between chunks
TOP_K           # how many chunks to retrieve per query
```

The script will print how many chunks are created per paper and how many are retrieved per query, so you can monitor how “focused” the RAG context is.

### 4.3 Single-query mode

You can also run Setting 3.2 for **one specific query folder**:

```bash
python llm-experiments/rag_pdf_segments_doc_qa.py
```

Choose:

- `Run mode: [1] full dataset, [2] single query folder (1/2) [1]: 2`

Then provide:

- `API key`, `Base URL`, `Chat model name`, `Ollama embedding model`
- `Absolute path to query folder (Qnn_*)`, e.g.:

```text
C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset\ALD\paper3\Q14_RE-MOSLED-efficiency-per-volt
```

The script will:

1. Infer the paper folder and PDF.
2. Extract, chunk, and embed the PDF once.
3. Build the retrieval query from `metadata.json`.
4. Retrieve the top-k chunks.
5. Call the LLM and write:

```text
Q14_RE-MOSLED-efficiency-per-volt/results_rag_[modelname].csv
```

This mode is useful for debugging or comparing RAG vs. context-injected behavior on a single query.
