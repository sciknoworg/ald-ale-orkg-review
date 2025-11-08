#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse, json, re, subprocess, sys, os, io, csv, shutil
from pathlib import Path

import pandas as pd
from io import StringIO

# Optional backends
try:
    import fitz  # PyMuPDF
    _HAVE_PYMUPDF = True
except Exception:
    _HAVE_PYMUPDF = False

try:
    import camelot  # type: ignore
    _HAVE_CAMELOT = True
except Exception:
    _HAVE_CAMELOT = False

try:
    import tabula  # type: ignore
    _HAVE_TABULA = True
except Exception:
    _HAVE_TABULA = False


def run_mineru(pdf_path: Path, out_root: Path) -> Path:
    """Run MinerU and return the resolved 'auto' output folder."""
    raw_dir = out_root / "_mineru_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mineru",
        "-p", str(pdf_path),
        "-o", str(raw_dir),
        "-b", "pipeline",  # full doc pipeline; gives middle.json + images
    ]
    print(f"[1/3] Running MinerU: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("ERROR: 'mineru' CLI not found on PATH. Please install MinerU and ensure 'mineru' is available.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: MinerU failed (exit {e.returncode}).")
        sys.exit(1)

    # Find .../<doc_name>/auto
    # There should be one child dir under _mineru_raw matching the PDF stem
    # with an 'auto' subdir.
    stem = pdf_path.stem
    # MinerU may normalize the name (e.g., spaces -> hyphens). Walk for 'auto'.
    auto_dir = None
    for p in raw_dir.rglob("auto"):
        # Make sure this belongs to our PDF
        if p.parent.name.lower().startswith(stem.lower()[:10]) or p.parent.name.lower().find(stem.lower()[:10]) >= 0:
            auto_dir = p
            break
    if auto_dir is None:
        # fallback: pick any 'auto'
        autos = list(raw_dir.rglob("auto"))
        if autos:
            auto_dir = autos[0]
    if auto_dir is None:
        print("ERROR: Could not find MinerU 'auto' output folder.")
        sys.exit(1)
    return auto_dir


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _pipe_md_to_rows(md_block: str):
    """
    Convert a GitHub-style pipe table to rows.
    """
    rows = []
    lines = [ln.strip() for ln in md_block.strip().splitlines() if ln.strip()]
    # find header sep (---|---)
    if len(lines) >= 2 and re.search(r'^\s*\|?[\s:\-\|]+\|?\s*$', lines[1]):
        table_lines = [ln for ln in lines if ln.startswith("|") or "|" in ln]
        for ln in table_lines:
            # trim leading/trailing pipe
            s = ln.strip()
            if s.startswith("|"): s = s[1:]
            if s.endswith("|"): s = s[:-1]
            parts = [c.strip() for c in s.split("|")]
            # skip alignment line
            if all(re.match(r'^:?-{3,}:?$', p) for p in parts):
                continue
            rows.append(parts)
    return rows


def _save_rows_csv(rows, out_csv: Path):
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)


def _try_pandas_read_html(html_str: str):
    try:
        dfs = pd.read_html(StringIO(html_str))  # ✅ suppresses FutureWarning
        if dfs:
            return dfs[0]
    except Exception:
        pass
    return None



def _crop_pdf_region(pdf_path: Path, page_num: int, bbox, out_pdf: Path):
    """
    bbox = [x0, y0, x1, y1] in PDF coordinate space (origin top-left or bottom-left,
    we'll robustly try both based on page height).
    """
    if not _HAVE_PYMUPDF:
        raise RuntimeError("PyMuPDF (fitz) not installed; cannot crop regions.")

    x0, y0, x1, y1 = bbox
    with fitz.open(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            raise ValueError(f"Invalid page {page_num} for {pdf_path}")
        page = doc[page_num - 1]
        W, H = page.rect.width, page.rect.height

        # Heuristic: if y0 < 0 or y1 < 0, or looks like 0..1 normalized -> scale up
        maybe_norm = 0 <= y0 <= 1 and 0 <= y1 <= 1 and 0 <= x0 <= 1 and 0 <= x1 <= 1
        if maybe_norm:
            X0, Y0, X1, Y1 = x0 * W, y0 * H, x1 * W, y1 * H
        else:
            # Try as top-left origin first; if height looks inverted, try bottom-left
            X0, Y0, X1, Y1 = x0, y0, x1, y1
            if Y0 < 0 or Y1 < 0 or Y0 > H or Y1 > H:
                # fallback: bottom-left
                Y0, Y1 = H - y0, H - y1
                if Y0 > Y1:
                    Y0, Y1 = Y1, Y0

        rect = fitz.Rect(float(X0), float(Y0), float(X1), float(Y1)).normalize()
        new_doc = fitz.open()
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page_num - 1, clip=rect)
        new_doc.save(out_pdf)
        new_doc.close()


def _table_pdf_to_csv(table_pdf: Path, out_csv: Path) -> bool:
    """Camelot lattice→stream, then Tabula lattice→stream."""
    # Camelot
    if _HAVE_CAMELOT:
        try:
            t = camelot.read_pdf(str(table_pdf), flavor="lattice", pages="1")
            if t and len(t) > 0:
                t[0].to_csv(str(out_csv))
                print(f"[camelot-lattice] {table_pdf.name} -> {out_csv.name}")
                return True
        except Exception as e:
            print(f"[camelot-lattice] failed: {e}")
        try:
            t = camelot.read_pdf(str(table_pdf), flavor="stream", pages="1")
            if t and len(t) > 0:
                t[0].to_csv(str(out_csv))
                print(f"[camelot-stream]  {table_pdf.name} -> {out_csv.name}")
                return True
        except Exception as e:
            print(f"[camelot-stream]  failed: {e}")
    # Tabula
    if _HAVE_TABULA:
        try:
            dfs = tabula.read_pdf(str(table_pdf), pages=1, multiple_tables=False, lattice=True)
            if dfs and len(dfs) > 0:
                dfs[0].to_csv(str(out_csv), index=False)
                print(f"[tabula-lattice]  {table_pdf.name} -> {out_csv.name}")
                return True
        except Exception as e:
            print(f"[tabula-lattice]  failed: {e}")
        try:
            dfs = tabula.read_pdf(str(table_pdf), pages=1, multiple_tables=False, stream=True)
            if dfs and len(dfs) > 0:
                dfs[0].to_csv(str(out_csv), index=False)
                print(f"[tabula-stream]   {table_pdf.name} -> {out_csv.name}")
                return True
        except Exception as e:
            print(f"[tabula-stream]   failed: {e}")
    return False


def main():
    ap = argparse.ArgumentParser(description="Extract tables to CSV from MinerU output; preserves GROBID index format.")
    ap.add_argument("--pdf", required=True, help="Path to input PDF")
    ap.add_argument("--out", required=True, help="Output folder")
    ap.add_argument("--skip-run", action="store_true", help="Do not run MinerU; reuse existing _mineru_raw output")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = out_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    # 1) Run (or reuse) MinerU
    if args.skip_run:
        # try to locate an auto folder under _mineru_raw
        auto_dir = None
        raw_dir = out_dir / "_mineru_raw"
        for p in raw_dir.rglob("auto"):
            auto_dir = p
            break
        if auto_dir is None:
            print("ERROR: --skip-run given but no previous _mineru_raw/*/auto found.")
            sys.exit(1)
    else:
        auto_dir = run_mineru(pdf_path, out_dir)

    stem = pdf_path.stem
    md_path = next((p for p in auto_dir.glob("*.md")), None)
    content_json = next((p for p in auto_dir.glob("*_content_list.json")), None)
    middle_json = next((p for p in auto_dir.glob("*_middle.json")), None)
    origin_pdf = next((p for p in auto_dir.glob("*_origin.pdf")), None)
    if origin_pdf is None:
        # fallback: use the input PDF
        origin_pdf = pdf_path

    records = []

    # 2) If Markdown includes pipe-tables or HTML tables — save them directly
    wrote_any_from_text = False
    if md_path and md_path.exists():
        md_text = _read_text(md_path)

        # Pipe-style tables
        pipe_tables = re.findall(r"(^\|.*\n(?:\|.*\n)+)", md_text, flags=re.M)
        count = 0
        for block in pipe_tables:
            rows = _pipe_md_to_rows(block)
            if rows:
                count += 1
                tbl_id = f"mineru_md_{count:02d}"
                out_csv = tables_dir / f"{tbl_id}.csv"
                _save_rows_csv(rows, out_csv)
                records.append({
                    "table_id": tbl_id,
                    "page": None,
                    "bbox": None,
                    "label": "",
                    "caption": "",
                    "csv_path": str(out_csv),
                    "status": "ok_from_md"
                })
        # HTML tables
        html_blocks = re.findall(r"(<table[\s\S]*?</table>)", md_text, flags=re.I)
        for blk in html_blocks:
            df = _try_pandas_read_html(blk)
            if df is not None:
                tbl_id = f"mineru_html_{len(records)+1:02d}"
                out_csv = tables_dir / f"{tbl_id}.csv"
                df.to_csv(out_csv, index=False)
                records.append({
                    "table_id": tbl_id,
                    "page": None,
                    "bbox": None,
                    "label": "",
                    "caption": "",
                    "csv_path": str(out_csv),
                    "status": "ok_from_html"
                })
        wrote_any_from_text = any(r.get("csv_path") for r in records)

    # 3) If MinerU only produced table IMAGES, use middle.json bboxes → crop → Camelot/Tabula
    if not wrote_any_from_text and middle_json and middle_json.exists():
        try:
            data = json.loads(_read_text(middle_json))
        except Exception as e:
            data = None
            print(f"[warn] Could not parse middle.json: {e}")

        # MinerU middle.json commonly contains a top-level 'pages' list with blocks.
        # We search for blocks whose category/type looks like a table and extract (page, bbox).
        crops_root = out_dir / "_mineru_crops"
        crops_root.mkdir(exist_ok=True)

        found = 0
        if isinstance(data, dict):
            pages = data.get("pages") or data.get("page_list") or []
            for p_idx, page in enumerate(pages, start=1):
                blocks = page.get("blocks") or page.get("elements") or page.get("layout") or []
                for b in blocks:
                    cat = (b.get("category") or b.get("type") or "").lower()
                    if "table" not in cat:
                        continue
                    # bbox variants seen in the wild:
                    #  - 'bbox': [x0,y0,x1,y1] (pixel or pdf units)
                    #  - 'box': {'x0':..,'y0':..,'x1':..,'y1':..}
                    bbox = b.get("bbox") or b.get("box") or b.get("rect") or b.get("position")
                    if isinstance(bbox, dict):
                        bbox = [bbox.get("x0"), bbox.get("y0"), bbox.get("x1"), bbox.get("y1")]
                    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
                        continue

                    found += 1
                    crop_pdf = crops_root / f"p{p_idx:03d}_t{found:02d}.pdf"
                    try:
                        _crop_pdf_region(origin_pdf, p_idx, bbox, crop_pdf)
                    except Exception as e:
                        records.append({
                            "table_id": f"mineru_bbox_p{p_idx}_{found:02d}",
                            "page": p_idx,
                            "bbox": [float(x) for x in bbox] if bbox else None,
                            "label": "",
                            "caption": "",
                            "csv_path": None,
                            "status": f"crop_failed: {e}"
                        })
                        continue

                    out_csv = tables_dir / f"mineru_bbox_p{p_idx}_{found:02d}.csv"
                    ok = _table_pdf_to_csv(crop_pdf, out_csv)
                    records.append({
                        "table_id": f"mineru_bbox_p{p_idx}_{found:02d}",
                        "page": p_idx,
                        "bbox": [float(x) for x in bbox],
                        "label": "",
                        "caption": "",
                        "csv_path": str(out_csv) if ok else None,
                        "status": "ok" if ok else "extraction_failed"
                    })

        print(f"[2/3] MinerU bbox-based tables detected: {sum(1 for r in records if r['table_id'].startswith('mineru_bbox_'))}")

    # 4) Final index
    idx_path = out_dir / "index.csv"
    pd.DataFrame.from_records(records).to_csv(idx_path, index=False)
    print(f"[3/3] Wrote index: {idx_path}")
    print(f"Tables: {tables_dir}")


if __name__ == "__main__":
    main()
