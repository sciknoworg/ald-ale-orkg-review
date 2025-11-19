# ALD/E Survey Table Extractor & Reference-to-DOI Resolver Tools

Extract tables from a PDF via **GROBID → TEI → crop → Camelot/Tabula**, then resolve a plain‑text **reference list (no titles)** to **DOIs** using Crossref with conservative matching.

---

## 1) Quick pipeline

1. Call your local **GROBID** to get **TEI**.  
2. Parse TEI for **tables, captions, pages, and bounding boxes**.  
3. **Crop** each table region to a temp PDF.  
4. Run **Camelot → Tabula** (fallback) to extract tables.  
5. Save **one CSV per table** + a **summary `index.csv`**.  
6. (Optional) Resolve **references** from a TXT list to **DOIs** via Crossref.

---

## 2) Install

```bash
pip install requests lxml pandas pymupdf camelot-py[cv] tabula-py tqdm
```

install grobid

```bash
docker pull grobid/grobid:0.8.2-full
```

> **Windows notes**  
> • Camelot needs **Ghostscript** and **OpenCV**.  
> • Tabula needs **Java**.

---

## 3) Start GROBID

```bash
docker run -t --rm -p 8070:8070 grobid/grobid:0.8.2-full
```

---

## 4) Extract tables

```bash
python table-to-csv\extract_tables_from_pdf.py ^
  --pdf ale\paper4\physical-and-chemical-effects-in-directional-atomic-layer-etching.pdf ^
  --out ale\paper4\output ^
  --grobid "http://localhost:8070"
```

**Outputs**
- `ale\paper4\output\tei.xml`  
- `ale\paper4\output\tables\*.csv`  
- `ale\paper4\output\index.csv` (page, bbox, caption, status)

---

## 4a) Extract tables (GROBID route)

```bash
python table-to-csv\extract_tables_from_pdf.py ^
  --pdf ale\paper4\physical-and-chemical-effects-in-directional-atomic-layer-etching.pdf ^
  --out ale\paper4\output ^
  --grobid "http://localhost:8070"
```

**Outputs**
- `ale\paper4\output\tei.xml`  
- `ale\paper4\output\tables\*.csv`  
- `ale\paper4\output\index.csv` (page, bbox, caption, status)

---

## 4b) **Alternative:** Extract tables with **MinerU** (Markdown/HTML → CSV)

MinerU performs end-to-end document analysis and emits Markdown/HTML fragments for tables;  
the provided wrapper converts those into the **same outputs** as the GROBID route  
(`tables/*.csv` + `index.csv`).

### Install (Windows / clean virtualenv recommended)

```bash
pip install mineru
# If the CLI errors on first run, add these:
pip install doclayout-yolo ultralytics ftfy shapely pyclipper omegaconf
```

- The **pipeline** backend uses document-layout and OCR models (faster, more dependencies).
- The **VLM** backend avoids most vision deps but downloads large transformer weights on first run.

### Run (pipeline backend)

First time.

```bash
python table-to-csv\extract_tables_with_mineru.py ^
  --pdf ale\paper5\atomic-layer-etching-of-sio2-for-nanoscale-semiconductor-devices-a-review.pdf ^
  --out ale\paper5\output
```

If you’ve already run MinerU and just want to re-extract without re-downloading models:

```bash
python table-to-csv\extract_tables_with_mineru.py ^
  --pdf ale\paper5\atomic-layer-etching-of-sio2-for-nanoscale-semiconductor-devices-a-review.pdf ^
  --out ale\paper5\output ^
  --skip-run
```

### Run (VLM backend — fewer deps)

```bash
python table-to-csv\extract_tables_with_mineru.py ^
  --pdf ale\paper5\atomic-layer-etching-of-sio2-for-nanoscale-semiconductor-devices-a-review.pdf ^
  --out ale\paper5\output ^
  --backend vlm-transformers
```

**Outputs (same as GROBID route)**
- `ale\paper5\output\tables\*.csv`  
- `ale\paper5\output\index.csv` (page, bbox, caption, status)

> **Notes**
> - First MinerU run downloads model weights to your Hugging Face cache (~1 GB).  
> - Works on CPU; GPU is optional (requires CUDA-enabled PyTorch).

---

## 5) Resolve references (TXT → DOI)

Prepare `references.txt` like:

```
[1] T. Suntola, Sci Rep 1989, 4, 261.
[2] H. H. Sønsteby, ... J Vac Sci Technol A 2020, 38, 020804.
[3] N. E. Richey, C. De Paula, S. F. Bent, J. Chem. Phys. 2020, 152, 040902.
[4] Y. Zhao, L. Zhang, ... Chem. Soc. Rev. 2021, 50, 3889.
```

First run (quick trial on first 25)

```bash
python table-to-csv\resolve_refs_from_txt_to_doi.py ^
  --txt ale\paper4\references.txt ^
  --out ale\paper4\references-resolved-doi.csv ^
  --min-score 40 ^
  --rows 8 ^
  --pause 0.3 ^
  --limit 25
```

Simplest run (with defaults)

```bash
python table-to-csv\resolve_refs_from_txt_to_doi.py --txt ale\paper4\references.txt --out ale\paper4\references-resolved-dois.csv
```

### Resume later (append from next idx)

The script reads the existing CSV, finds the max idx, and continues with refs where idx > max_idx.
Example (353 total; last written idx=268, so 85 remaining):

```bash
python table-to-csv\resolve_refs_from_txt_to_doi.py ^
  --txt ale\paper4\references.txt ^
  --out ale\paper4\references-resolved-doi.csv ^
  --resume
```

Typical log

```text
[10:04:52] Parsed 353 references from TXT (min idx=1 max idx=353)
[10:04:52] Resuming after idx=268 (found in ...\references-resolved-doi.csv)
[10:07:01] [10/85] idx=278 score=65 decision=accepted → 10.1016/j.surfin.2022.102377
[10:07:33] [20/85] idx=288 score=50 decision=accepted → 10.1016/j.ceramint.2021.02.231
```

Notes

- Rows are appended immediately on resume; the [n/m] counter shows progress within the remaining set.
- To reprocess earlier rows: delete them from the CSV, run without --resume, or use --start-idx N.

---

## 6) Scoring (how matches are accepted)

Each Crossref candidate is scored using metadata present in title‑less refs:

- **Year** exact match ……………………………… **+15**  
- **Journal** (abbr/full substring match) …… **+20**  
- **Volume** exact match ………………………… **+10**  
- **Page OR article number** match ……… up to **+30**  
  - page contains token ………………………… **+15**  
  - article-number digits match …………… **+15**  
- **Author last names** (≤3) …………………… up to **+10**  
  (**+5** per matching family name)

Default accept if **score ≥ 35**; else `low_confidence` or `no_match`.  
You can tighten with `--min-score 40`.

---

## 7) Tips

- Start with `--limit 25` to sanity check.  
- Add common journal abbreviations to the script’s **`JOURNAL_MAP`** (abbr → full) for stronger matches.  
- Some strings (e.g., **“Sci Rep 1989”**) may intentionally remain unresolved to avoid false positives.

---

## 8) Expand table rows with DOIs (attach from reference mapping)

This step takes your **table CSV** (with a `Refs.` column) and the **resolved references CSV** (from Section 5) and produces a row-per-reference output with DOIs filled in.

**Script**: `table-to-csv\expand-refs-attach-dois.py`

**What it does**
- Keeps rows that **already have a DOI** in the chosen DOI column.
- For rows **without** a DOI, it parses `Refs.` (e.g., `[28,224-226]` → `[28]`, `[224]`, `[225]`, `[226]`) and **duplicates** the row once per reference number.
- Looks up each reference number (`idx`) in the mapping file and **fills DOI only if `decision == accepted`**.
- If none of the expanded refs have an accepted DOI, the row is **dropped**.
- For reference numbers **missing in the mapping**, the script will now **prompt you interactively** to enter the DOI.  
  - If you provide a DOI, it’s attached and **the mapping file is automatically updated** (only `best_doi` and `decision` are changed).  
  - If the DOI truly cannot be found, press **Enter** or type **`skip`** to continue without it.

> 💡 To disable prompts and skip unresolved references silently, add the flag `--no-ask-missing`.

**1 Example Run**
```bash
python table-to-csv\expand-refs-attach-dois.py ^
  --data ale\paper4\output\tables\tab_0.csv ^
  --mapping ale\paper4\references-resolved-doi-some-manual.csv ^
  --out ale\paper4\output\tables\tab_0-w-dois.csv ^
  --refs-col "Refs."
```

```yaml
Done. Wrote: C:\Users\DSouzaJ\Code\ald-ale-orkg-review\ale\paper4\output\tables\tab_0-w-dois.csv
Kept with DOI: 0 | Expanded rows created: 9 | Dropped (no accepted DOI): 0
```

**2 Example Run**
```bash
python table-to-csv\expand-refs-attach-dois.py ^
  --data ale\paper4\output\tables\tab_4.csv ^
  --mapping ale\paper4\references-resolved-doi-some-manual.csv ^
  --out ale\paper4\output\tables\tab_4-w-dois.csv ^
  --refs-col "Refs."
```

```yaml
Done. Wrote: C:\Users\DSouzaJ\Code\ald-ale-orkg-review\ale\paper4\output\tables\tab_4-w-dois.csv
Kept with DOI: 0 | Expanded rows created: 8 | Dropped (no accepted DOI): 0
```

**3 Silent Mode Example Run**
```bash
python table-to-csv\expand-refs-attach-dois.py ^
  --data ale\paper4\output\tables\tab_1.csv ^
  --mapping ale\paper4\references-resolved-doi-some-manual.csv ^
  --out ale\paper4\output\tables\tab_1-w-dois.csv ^
  --refs-col "Refs." ^
  --no-ask-missing
```

```yaml
Done. Wrote: C:\Users\DSouzaJ\Code\ald-ale-orkg-review\ale\paper4\output\tables\tab_1-w-dois.csv
Kept with DOI: 2 | Expanded rows created: 5 | Dropped (no accepted DOI): 1
```

Notes

- Matching uses the reference numbers in `Refs.` (e.g., `[28]`) against the mapping CSV’s `idx` column from Section 5.
- Supported `Refs.` formats: `[28,224-226]`, `208`, `207,233`, `[ 184 ]`, and ranges with en-dashes.
- Only accepted mappings are used; `low_confidence` and `no_match` are ignored.
- To preserve rows that already contain DOIs, set `--doi-col` to the existing DOI column (e.g., `doi_list`) or omit the flag for auto-detection.
- When running **interactively (default)**, you can supply missing DOIs manually, and they’ll be stored back into the mapping file.  
  To run **silently**, add `--no-ask-missing` to skip all unresolved references.

---

## Convert to a csv file to upload to ORKG

```bash
python table-to-csv/convert_to_orkg_csv.py ^
  --in ale/paper4/output/tables/tab_0-w-dois.csv ^
  --out ale/paper4/orkg-upload/tab_0-data.csv
```

```bash
python table-to-csv/convert_to_orkg_csv.py ^
  --in ale/paper4/output/tables/tab_4-w-dois.csv ^
  --out ale/paper4/orkg-upload/tab_4-data.csv
```