# Quick Reference Guide

## TL;DR - Just Want to Extract PDFs?

```bash
# 1. Install dependency
pip install pdfplumber

# 2. Run extraction
python pdf_extractor.py /path/to/your/papers

# 3. Done! JSON files created next to each PDF
```

## What Gets Extracted?

✅ **Included:**
- All main content (Introduction, Methods, Results, Discussion, Conclusions)
- Clean text (no excessive whitespace)
- Tables (simple ones as structured data, complex ones in text)
- Metadata (title, authors, DOI, etc.)

❌ **Excluded:**
- References section
- Funding sources
- Conflicts of interest
- Acknowledgements

## Common Use Cases

### Extract Everything
```bash
python pdf_extractor.py /path/to/papers
```

### Use in Your Python Script
```python
from pdf_extractor import extract_from_folder

results = extract_from_folder('/path/to/papers')
paper_text = results['categories']['ALD']['papers']['paper1']['pdf_files']['doc.pdf']['pages'][0]['text']
```

### Include References (if needed)
```python
results = extract_from_folder('/path/to/papers', exclude_references=False)
```

### Show Progress
```python
results = extract_from_folder('/path/to/papers', verbose=True)
```

## Folder Structure Required

```
your_papers/
├── ALD/              ← Category folder
│   ├── paper1/       ← Paper folder
│   │   └── doc.pdf   ← PDF file
│   └── paper2/
│       └── research.pdf
└── ALE/              ← Another category
    └── study1/
        └── article.pdf
```

## Output Structure

```
your_papers/
├── ALD/
│   ├── paper1/
│   │   ├── doc.pdf
│   │   └── doc_extracted.json          ← Created here!
│   └── paper2/
│       ├── research.pdf
│       └── research_extracted.json     ← Created here!
└── ALE/
    └── study1/
        ├── article.pdf
        └── article_extracted.json       ← Created here!
```

## JSON Structure

```json
{
  "metadata": {
    "Title": "Paper title",
    "Author": "Author name",
    "doi": "10.xxxx/xxxxx"
  },
  "pages": [
    {
      "page_number": 1,
      "text": "Clean text content...",
      "tables": [/* Structured tables when detected */],
      "dimensions": {"width": 595.276, "height": 779.528}
    }
  ]
}
```

## Troubleshooting

### No JSON files created?
- Check folder structure matches required format
- Ensure PDFs are in `category/paper/` folders

### Tables missing?
- Complex tables are in text (this is fine for LLMs!)
- Simple tables are extracted as structured data

### References still included?
- Default excludes them automatically
- Check the last page - should stop before "References"

### Text looks weird?
- This is normal for equations/special symbols
- LLMs handle this well

## Performance

- **Speed:** ~1-2 seconds per page
- **Memory:** Minimal (processes one page at a time)
- **Size:** JSON files are typically 10-50% of PDF size

## For LLM Experiments

**Perfect for:**
- ✅ Feeding to Claude/GPT for table extraction
- ✅ In-context learning experiments
- ✅ Comparing SPARQL results with LLM outputs

**Why it works:**
- Clean text without noise
- No reference clutter
- Tables preserved (text or structured)
- Easy to access and parse
