# RMS Evaluation for ALD/ALE ORKG Review

This folder contains the RMS-based evaluation pipeline for comparing **LLM-generated tables** against **SPARQL gold-standard tables** for all ALD/ALE review queries.

The main script is:

```bash
python eval_rms_all_queries.py --root "C:\Users\DSouzaJ\Datasets\ald-e-zenodo-dataset"
```

where `--root` points to the dataset root containing:

```text
<root>/
  ALD/
    paper1/
      Q01_.../
        results_SPARQL.csv          # gold
        results_*.csv               # LLM outputs (various settings)
      Q02_.../
      ...
    paper2/
    ...
  ALE/
    paper1/
    ...
```

Each `Qnn_*` folder corresponds to one query (e.g. `Q03_phosphor-sio2`).

## Installation

From `eval_deplot_rms/`:

```bash
pip install numpy scipy pandas absl-py python-Levenshtein
python -m deplot.metrics_test  # optional: check RMS metric
```

## What the script produces

Running `eval_rms_all_queries.py` writes several CSVs into `eval_deplot_rms/`:

- **`rms_per_query_detailed.csv`**  
  One row per *(domain, paper, query_folder, system)* with RMS precision/recall/F1 vs `results_SPARQL.csv`.

- **`rms_per_query_cumulative_ALD.csv` / `rms_per_query_cumulative_ALE.csv`**  
  Cumulative scores per query ID (e.g. `Q01`, `Q02`, …) and system, aggregated over all papers **within ALD / ALE**.

- **`rms_best_per_query.csv`**  
  For each *(domain, query ID)*, the **best non-symbolic system/setting** (highest cumulative RMS F1).

- **`rms_overall.csv`**  
  Overall RMS scores per system across **all queries and domains**, including the SPARQL symbolic upper bound.

Internally, the script uses the DePlot **Relative Mapping Similarity (RMS)** metric, which is invariant to row/column order and compares tables as sets of (row header, column header → value) mappings.
