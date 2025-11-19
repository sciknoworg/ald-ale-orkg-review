## NL Query Generator (Single-Table CSV Output)

The script `nl_query_generator_csv_onetable.py` automatically converts each SPARQL query in the ALD/ALE dataset into a detailed natural-language query.  
These NL queries are intended for LLM experiments where the model is given only the **PDF of the scientific article** and must reproduce the same table that the SPARQL query returns over the ORKG comparison.

For each query folder, the script:
- Reads the SPARQL query, lightweight NL query, metadata, and example result table.
- Uses an LLM to generate a **fully detailed natural-language query** that:
  - Refers to the correct table in the article (e.g., “Table 2”)
  - Describes the precise filtering/selection logic encoded in the SPARQL
  - Requires the LLM to return **exactly one table**
  - Requires the output table to be in **CSV format**
  - Uses the same column headers as the sample result table (excluding ORKG/ID columns)
- Writes (or overwrites) the output to `natural_language_query_detailed.md` in each query’s folder.

### Running the script

From the project directory:

```bash
python llm-experiments\nl_query_generator_csv_onetable.py
```

### Example run (Windows)

```bash
C:\Users\DSouzaJ\Code\ald-ale-orkg-review>python llm-experiments\nl_query_generator_csv_onetable.py
=== Generate detailed NL queries from SPARQL ===
Dataset root directory: C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset
API key: ***
Base URL [https://chat-ai.academiccloud.de/v1]:
Model name [meta-llama-3.1-8b-instruct]: mistral-large-instruct
Found 33 query folders.
```

The script will then generate and overwrite `natural_language_query_detailed.md` for every query folder in the dataset.
