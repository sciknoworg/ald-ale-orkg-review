import argparse
import os
import io
import json
import re
import shutil
from pathlib import Path

import requests
import pandas as pd
from lxml import etree

# Optional backends; we'll check availability dynamically
try:
    import camelot  # type: ignore
    _HAVE_CAMEL0T = True
except Exception:
    _HAVE_CAMEL0T = False

try:
    import tabula  # type: ignore
    _HAVE_TABULA = True
except Exception:
    _HAVE_TABULA = False

try:
    import fitz  # PyMuPDF
    _HAVE_PYMUPDF = True
except Exception:
    _HAVE_PYMUPDF = False


TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


import time, gc
def _safe_rmtree(p: Path, attempts=8, delay=0.25):
    for _ in range(attempts):
        try:
            shutil.rmtree(p)
            return
        except PermissionError:
            gc.collect()
            time.sleep(delay)
    shutil.rmtree(p, ignore_errors=True)

def call_grobid(pdf_path: Path, grobid_url: str) -> str:
    """
    Send PDF to GROBID /processFulltextDocument and return TEI XML (str).
    """
    endpoint = f"{grobid_url.rstrip('/')}/api/processFulltextDocument"
    with open(pdf_path, "rb") as f:
        files = {"input": (pdf_path.name, f, "application/pdf")}
        data = {
            "consolidateHeader": "1",
            "consolidateCitations": "1",
            # use 'page' instead of 'pb'
            "teiCoordinates": "figure,table,page"
        }
        resp = requests.post(endpoint, files=files, data=data, timeout=180)
    resp.raise_for_status()
    return resp.text


def parse_facsimile_zones(tei_root):
    """
    Build mapping:
      - zone_id -> dict(page_number, bbox=(ulx,uly,lrx,lry))
    Also map surfaces to sequential page numbers.
    """
    zones = {}
    page_num = 0
    for surf in tei_root.xpath("//tei:facsimile/tei:surface", namespaces=TEI_NS):
        page_num += 1
        for z in surf.xpath("./tei:zone", namespaces=TEI_NS):
            zid = z.get("{http://www.w3.org/XML/1998/namespace}id")
            try:
                ulx = float(z.get("ulx"))
                uly = float(z.get("uly"))
                lrx = float(z.get("lrx"))
                lry = float(z.get("lry"))
                zones[zid] = {"page": page_num, "bbox": (ulx, uly, lrx, lry)}
            except (TypeError, ValueError):
                continue
    return zones


def extract_tables_from_tei(tei_xml: str):
    root = etree.fromstring(tei_xml.encode("utf-8"))
    tables = []

    def _norm_text(el):
        return " ".join(" ".join(el.itertext()).split()) if el is not None else ""

    # 1) Any <figure> that either has type="table" OR looks like a table by head/label text
    for fig in root.xpath("//tei:figure", namespaces=TEI_NS):
        typ = (fig.get("type") or "").strip().lower()
        head = fig.find("./tei:head", namespaces=TEI_NS)
        label_el = fig.find("./tei:label", namespaces=TEI_NS)
        figdesc = fig.find("./tei:figDesc", namespaces=TEI_NS)

        head_txt = _norm_text(head)
        label_txt = _norm_text(label_el)
        desc_txt = _norm_text(figdesc)

        looks_like_table = (
            typ == "table" or
            re.match(r"^\s*table\b", head_txt, flags=re.I) or
            re.match(r"^\s*table\b", label_txt, flags=re.I) or
            re.match(r"^\s*table\b", desc_txt,  flags=re.I)
        )
        if not looks_like_table:
            continue

        # pick up facs either on <figure> or <graphic>
        facs = fig.get("facs")
        if not facs:
            g = fig.find(".//tei:graphic", namespaces=TEI_NS)
            if g is not None:
                facs = g.get("facs")
        if facs and facs.startswith("#"):
            facs = facs[1:]

        xml_id = fig.get("{http://www.w3.org/XML/1998/namespace}id") or ""
        has_tei_table = fig.find(".//tei:table", namespaces=TEI_NS) is not None

        caption = head_txt or desc_txt or label_txt
        tables.append({
            "caption": caption,
            "label": label_txt,
            "facs": facs,
            "xml_id": xml_id,
            "has_tei_table": has_tei_table
        })

    # 2) Standalone <tei:table> anywhere
    for t in root.xpath("//tei:table", namespaces=TEI_NS):
        facs = t.get("facs")
        if not facs:
            g = t.find(".//tei:graphic", namespaces=TEI_NS)
            if g is not None:
                facs = g.get("facs")
        if facs and facs.startswith("#"):
            facs = facs[1:]

        head = t.find("./tei:head", namespaces=TEI_NS)
        label_el = t.find("./tei:label", namespaces=TEI_NS)
        caption = _norm_text(head)
        label   = _norm_text(label_el)
        if not caption and label:
            caption = label

        xml_id = t.get("{http://www.w3.org/XML/1998/namespace}id") or ""
        tables.append({
            "caption": caption,
            "label": label,
            "facs": facs,
            "xml_id": xml_id,
            "has_tei_table": True
        })

    # 3) tableWrap (used by some TEI conversions)
    for tw in root.xpath("//tei:tableWrap", namespaces=TEI_NS):
        t = tw.find("./tei:table", namespaces=TEI_NS)
        if t is None:
            continue
        facs = tw.get("facs") or t.get("facs")
        if facs and facs.startswith("#"):
            facs = facs[1:]
        head = tw.find("./tei:head", namespaces=TEI_NS) or t.find("./tei:head", namespaces=TEI_NS)
        label_el = tw.find("./tei:label", namespaces=TEI_NS) or t.find("./tei:label", namespaces=TEI_NS)
        caption = _norm_text(head)
        label   = _norm_text(label_el)
        xml_id = tw.get("{http://www.w3.org/XML/1998/namespace}id") or \
                 t.get("{http://www.w3.org/XML/1998/namespace}id") or ""
        tables.append({
            "caption": caption or label,
            "label": label,
            "facs": facs,
            "xml_id": xml_id,
            "has_tei_table": True
        })

    return tables, root

def _extract_rows_from_tei_table(tei_tbl):
    rows = []
    for row in tei_tbl.findall("./tei:row", namespaces=TEI_NS):
        cells = []
        for cell in row.findall("./tei:cell", namespaces=TEI_NS):
            text = " ".join(" ".join(cell.itertext()).split())
            cells.append(text)
        rows.append(cells)
    return rows


def tei_tables_to_csvs(tei_xml: str, out_dir: Path):
    """
    Export tables that are already parsed in TEI (<table><row><cell>…) to CSV.
    Returns list of record dicts for index.csv.
    NOTE: ignores colspan/rowspan.
    """
    root = etree.fromstring(tei_xml.encode("utf-8"))
    ns = TEI_NS
    records = []
    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    # Iterate all figure tables that contain a TEI <table>
    for fig in root.xpath("//tei:figure[translate(@type,'TABLE','table')='table']", namespaces=ns):
        tei_tbl = fig.find(".//tei:table", namespaces=ns)
        if tei_tbl is None:
            continue

        head = fig.find("./tei:head", namespaces=ns)
        figdesc = fig.find("./tei:figDesc", namespaces=ns)
        label_el = fig.find("./tei:label", namespaces=ns)
        caption = ""
        if head is not None:
            caption = " ".join(" ".join(head.itertext()).split())
        elif figdesc is not None:
            caption = " ".join(" ".join(figdesc.itertext()).split())
        label = " ".join(" ".join(label_el.itertext()).split()) if label_el is not None else ""

        xml_id = fig.get("{http://www.w3.org/XML/1998/namespace}id") or None
        if not xml_id:
            # fallback id
            xml_id = f"table_{len(records)+1:04d}"

        # Collect rows
        rows = []
        for row in tei_tbl.findall("./tei:row", namespaces=ns):
            cells = []
            for cell in row.findall("./tei:cell", namespaces=ns):
                text = " ".join(" ".join(cell.itertext()).split())
                cells.append(text)
            rows.append(cells)

        # Write CSV
        csv_path = tables_dir / f"{xml_id}.csv"
        import csv
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for r in rows:
                writer.writerow(r)

        records.append({
            "table_id": xml_id,
            "page": None,
            "bbox": None,
            "label": label,
            "caption": caption,
            "csv_path": str(csv_path),
            "status": "ok_from_tei"
        })

    # Also handle standalone <tei:table> not under <figure>
    for t in root.xpath("//tei:table[not(ancestor::tei:figure)]", namespaces=ns):
        xml_id = t.get("{http://www.w3.org/XML/1998/namespace}id") or f"table_{len(records)+1:04d}"
        head = t.find("./tei:head", namespaces=ns)
        label_el = t.find("./tei:label", namespaces=ns)
        caption = " ".join(" ".join(head.itertext()).split()) if head is not None else ""
        label = " ".join(" ".join(label_el.itertext()).split()) if label_el is not None else ""

        rows = []
        for row in t.findall("./tei:row", namespaces=ns):
            cells = []
            for cell in row.findall("./tei:cell", namespaces=ns):
                text = " ".join(" ".join(cell.itertext()).split())
                cells.append(text)
            rows.append(cells)

        csv_path = (out_dir / "tables" / f"{xml_id}.csv")
        import csv
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for r in rows:
                writer.writerow(r)

        records.append({
            "table_id": xml_id,
            "page": None,
            "bbox": None,
            "label": label,
            "caption": caption,
            "csv_path": str(csv_path),
            "status": "ok_from_tei"
        })

    # 3) tableWrap/tei:table
    for tw in root.xpath("//tei:tableWrap", namespaces=ns):
        tei_tbl = tw.find("./tei:table", namespaces=ns)
        if tei_tbl is None:
            continue
        xml_id = tw.get("{http://www.w3.org/XML/1998/namespace}id") \
                or tei_tbl.get("{http://www.w3.org/XML/1998/namespace}id") \
                or f"table_{len(records)+1:04d}"
        head = tw.find("./tei:head", namespaces=ns) or tei_tbl.find("./tei:head", namespaces=ns)
        label_el = tw.find("./tei:label", namespaces=ns) or tei_tbl.find("./tei:label", namespaces=ns)
        caption = " ".join(" ".join(head.itertext()).split()) if head is not None else ""
        label = " ".join(" ".join(label_el.itertext()).split()) if label_el is not None else ""

        rows = _extract_rows_from_tei_table(tei_tbl)
        if not rows:
            continue

        csv_path = (out_dir / "tables" / f"{xml_id}.csv")
        import csv
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for r in rows:
                writer.writerow(r)

        records.append({
            "table_id": xml_id,
            "page": None,
            "bbox": None,
            "label": label,
            "caption": caption,
            "csv_path": str(csv_path),
            "status": "ok_from_tei"
        })

    return records


def crop_pdf_region_to_temp(pdf_path: Path, page_num: int, bbox, out_dir: Path) -> Path:
    """
    Crop the region (ulx, uly, lrx, lry) on page_num (1-indexed) to a temp single-page PDF.
    Requires PyMuPDF.
    """
    if not _HAVE_PYMUPDF:
        raise RuntimeError("PyMuPDF (fitz) not installed; cannot crop regions.")

    ulx, uly, lrx, lry = bbox
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / f"crop_p{page_num}_{int(ulx)}_{int(uly)}_{int(lrx)}_{int(lry)}.pdf"

    with fitz.open(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            raise ValueError(f"Invalid page {page_num} for {pdf_path}")
        page = doc[page_num - 1]
        rect = fitz.Rect(ulx, uly, lrx, lry)
        new_doc = fitz.open()
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page_num - 1, clip=rect)
        new_doc.save(out_pdf)
        new_doc.close()
    return out_pdf


def table_pdf_to_csv(table_pdf: Path, out_csv: Path) -> bool:
    """
    Try Camelot (lattice->stream), then Tabula. Return True if something written.
    """
    # Try Camelot first if available
    if _HAVE_CAMEL0T:
        try:
            tables = camelot.read_pdf(str(table_pdf), flavor="lattice", pages="1")
            if tables and len(tables) > 0:
                tables[0].to_csv(str(out_csv))
                print(f"[camelot-lattice] {table_pdf.name} -> {out_csv.name}")
                return True
        except Exception as e:
            print(f"[camelot-lattice] failed: {e}")

        try:
            tables = camelot.read_pdf(str(table_pdf), flavor="stream", pages="1")
            if tables and len(tables) > 0:
                tables[0].to_csv(str(out_csv))
                print(f"[camelot-stream]  {table_pdf.name} -> {out_csv.name}")
                return True
        except Exception as e:
            print(f"[camelot-stream]  failed: {e}")

    # Try Tabula if available
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

# --- NEW: robust table-region finder (PyMuPDF) ---
def _sorted_blocks(page):
    return sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))

def _looks_tabular(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    # Has many numbers or clear column separators?
    digit_ratio = sum(c.isdigit() for c in t) / max(1, len(t))
    has_delims = bool(re.search(r"[,\t;]| {2,}", t))
    many_short_tokens = sum(len(x) <= 4 for x in t.split()) >= 3
    return digit_ratio >= 0.15 or has_delims or many_short_tokens

def _looks_prose_or_caption(text: str) -> bool:
    t = " ".join(text.split())
    if not t:
        return False
    if re.search(r"^(Figure|Table)\s+[IVX0-9]+\.", t, re.I):
        return True
    if "Reproduced with permission" in t or "Copyright" in t:
        return True
    # long sentencey lines → prose
    long_tokens = sum(len(x) >= 8 for x in t.split())
    return long_tokens >= 6 and not _looks_tabular(t)

def detect_table_regions_via_layout(pdf_path: Path):
    import fitz, re
    doc = fitz.open(pdf_path)
    regions = []
    for pno, page in enumerate(doc, start=1):
        blks = _sorted_blocks(page)  # (x0,y0,x1,y1, text, block_no, ...)
        caps = [i for i,b in enumerate(blks) if re.search(r"^Table\s+[IVX0-9]+\.", (b[4] or "").strip(), re.I)]
        for ci in caps:
            cap = blks[ci]; cap_y1 = cap[3]
            xs, ys = [], []
            for j in range(ci+1, len(blks)):
                b = blks[j]; t = (b[4] or "").strip()
                if re.search(r"^(Table|Figure)\s+[IVX0-9]+\.", t, re.I):
                    break
                if b[1] - cap_y1 > 420:               # don't grow too far
                    break
                if _looks_prose_or_caption(t):
                    break
                if not _looks_tabular(t):
                    continue
                # keep blocks roughly under the caption column
                if b[0] < cap[2] + 30:
                    xs.append((b[0], b[2])); ys.append((b[1], b[3]))
            if xs and ys:
                x0 = max(0, min(a for a,_ in xs) - 4)
                x1 = max(b for _,b in xs) + 4
                y0 = cap_y1 + 2
                y1 = max(b for _,b in ys) + 2
                regions.append({"page": pno, "area": [float(y0), float(x0), float(y1), float(x1)],
                                "caption": cap[4].split("\n")[0].strip()})
    doc.close()
    return regions

def _area_has_rules(pdf_path: Path, page_no: int, area):
    """
    Heuristic: check if the extraction rectangle contains several drawn
    horizontal/vertical lines -> prefer lattice if True.
    area = [top,left,bottom,right] (top-left origin)
    """
    import fitz
    top,left,bottom,right = area
    with fitz.open(pdf_path) as d:
        p = d[page_no-1]
        rect = fitz.Rect(left, top, right, bottom)
        cnt = 0
        for dr in p.get_drawings():
            for item in dr["items"]:
                if item[0] != "l":  # only line segments
                    continue
                _, p1, p2 = item
                seg = fitz.Rect(min(p1.x,p2.x), min(p1.y,p2.y), max(p1.x,p2.x), max(p1.y,p2.y))
                if rect.intersects(seg):
                    cnt += 1
        return cnt >= 5

def _clean_csv(path: Path):
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return
    def _bad_row(row_vals):
        t = " ".join(" ".join(map(str, row_vals)).split())
        if not t: return True
        if re.search(r"^(Figure|Table)\s+[IVX0-9]+\.", t, re.I): return True
        if "Reproduced with permission" in t or "Copyright" in t: return True
        empties = sum((str(x).strip()=="" for x in row_vals))
        if empties >= max(2, int(0.6*len(row_vals))): return True
        # lines that look like sentences (lots of long tokens) but few numbers → drop
        num_digits = sum(c.isdigit() for c in t)
        long_tokens = sum(len(x) >= 7 for x in t.split())
        if long_tokens >= 8 and num_digits <= 2:
            return True        
        return False  
    keep_mask = [not _bad_row(row) for _, row in df.iterrows()]
    df2 = df[keep_mask]
    if len(df2) and (len(df2) != len(df)):
        df2.to_csv(path, index=False)


def main():
    ap = argparse.ArgumentParser(description="Extract tables to CSV using GROBID TEI (direct) + optional coords/Camelot/Tabula.")
    ap.add_argument("--pdf", required=True, help="Path to input PDF")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--grobid", default="http://localhost:8070", help="GROBID base URL")
    args = ap.parse_args()

    # >>> move TMP config here <<<
    tmp_root = Path(args.out).expanduser().resolve() / "_tmp"
    os.environ.setdefault("TMPDIR", str(tmp_root))
    os.environ.setdefault("TMP",    str(tmp_root))
    os.environ.setdefault("TEMP",   str(tmp_root))
    tmp_root.mkdir(parents=True, exist_ok=True)
    # pre-clean old temp files but keep the root so 3rd-party atexit doesn't crash
    for p in list(tmp_root.glob("*")):
        try:
            if p.is_dir():
                _safe_rmtree(p)
            else:
                p.unlink(missing_ok=True)
        except Exception:
            pass

    pdf_path = Path(args.pdf).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = out_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    # 1) GROBID
    print("[1/4] Calling GROBID…")
    tei_xml = call_grobid(pdf_path, args.grobid)
    tei_path = out_dir / "tei.xml"
    tei_path.write_text(tei_xml, encoding="utf-8")
    print(f"Saved TEI: {tei_path}")

    # 2) Parse TEI → table nodes + zone map
    print("[2/4] Parsing TEI…")
    table_meta, tei_root = extract_tables_from_tei(tei_xml)
    zones = parse_facsimile_zones(tei_root)
    print(f"Found {len(table_meta)} table-like nodes; zones detected: {len(zones)}")

    # 3) First, export TEI-embedded tables directly to CSV
    print("[3a/4] Exporting TEI tables directly to CSV…")
    records = tei_tables_to_csvs(tei_xml, out_dir)
    tei_ids_done = {r["table_id"] for r in records}
    print(f"Exported {len(records)} tables from TEI")

    # 3b) For figure tables that only have coords (no TEI <table>), crop -> extractor -> CSV
    print("[3b/4] Cropping coord-only tables and extracting…")
    temp_dir = out_dir / "_temp_crops"
    temp_dir.mkdir(exist_ok=True)

    for t in table_meta:
        # Skip if we already exported this table by TEI id
        if t.get("xml_id") and t["xml_id"] in tei_ids_done:
            continue

        facs = t.get("facs")
        if not facs or facs not in zones:
            # no coordinates → nothing to crop here
            continue

        page = zones[facs]["page"]
        bbox = zones[facs]["bbox"]

        # Crop
        try:
            crop_pdf = crop_pdf_region_to_temp(pdf_path, page, bbox, temp_dir)
        except Exception as e:
            records.append({
                "table_id": t.get("xml_id") or f"coord_table_{page}",
                "page": page,
                "bbox": bbox,
                "label": t.get("label", ""),
                "caption": t.get("caption", ""),
                "csv_path": None,
                "status": f"crop_failed: {e}"
            })
            continue

        # Extract to CSV
        out_csv = tables_dir / f"{(t.get('xml_id') or 'coord_table')}.csv"
        ok = table_pdf_to_csv(crop_pdf, out_csv)
        status = "ok" if ok else "extraction_failed"

        records.append({
            "table_id": t.get("xml_id") or f"coord_table_{page}",
            "page": page,
            "bbox": [float(x) for x in bbox],
            "label": t.get("label", ""),
            "caption": t.get("caption", ""),
            "csv_path": str(out_csv) if ok else None,
            "status": status
        })

    # --- NEW: targeted area extraction if nothing came from TEI/coords ---
    if not any(r.get("csv_path") for r in records):
        print("[3c/4] No TEI tables or coords found; using layout-based regions …")
        regions = detect_table_regions_via_layout(pdf_path)
        print(f"Detected {len(regions)} table regions from layout.")
        for k, reg in enumerate(regions, start=1):
            out_csv = tables_dir / f"layout_table_{k:02d}.csv"
            ok = False

            # decide preferred flavor using rules
            use_lattice = False
            try:
                use_lattice = _area_has_rules(pdf_path, reg["page"], reg["area"])
            except Exception as _e:
                pass
            preferred = ["lattice","stream"] if use_lattice else ["stream","lattice"]

            # Prefer Camelot stream/lattice on the specific area (if available)
            if _HAVE_CAMEL0T:
                try:
                    import camelot, fitz
                    with fitz.open(pdf_path) as doc:
                        ph = doc[reg["page"] - 1].rect.height
                    top,left,bottom,right = reg["area"]
                    x1,y1,x2,y2 = left, ph - bottom, right, ph - top
                    area_cam = [x1, y1, x2, y2]

                    for flav in preferred:
                        t = camelot.read_pdf(
                                str(pdf_path),
                                flavor=flav,
                                pages=str(reg["page"]),
                                table_areas=[",".join(str(int(v)) for v in area_cam)]
                            )
                        if t and len(t) > 0:
                            t[0].to_csv(str(out_csv))
                            ok = True
                            _clean_csv(out_csv)
                            break
                except Exception as e:
                    print(f"[layout Camelot] page {reg['page']} failed: {e}")


            # Fallback to Tabula on the exact area (origin top-left)
            if _HAVE_TABULA and not ok:
                try:
                    import tabula
                    for flav in preferred:
                        if flav == "lattice":
                            dfs = tabula.read_pdf(
                                str(pdf_path), pages=reg["page"], area=[reg["area"]],
                                multiple_tables=False, lattice=True
                            )
                        else:
                            dfs = tabula.read_pdf(
                                str(pdf_path), pages=reg["page"], area=[reg["area"]],
                                multiple_tables=False, stream=True
                            )
                        if dfs and len(dfs) > 0:
                            dfs[0].to_csv(str(out_csv), index=False)
                            ok = True
                            _clean_csv(out_csv)
                            break
                except Exception as e:
                    print(f"[layout Tabula] page {reg['page']} failed: {e}")


            records.append({
                "table_id": f"layout_{k:02d}",
                "page": reg["page"],
                "bbox": reg["area"],  # [top,left,bottom,right]
                "label": "",
                "caption": reg["caption"],
                "csv_path": str(out_csv) if ok else None,
                "status": "ok_layout" if ok else "layout_extraction_failed"
            })

        print(f"[3c/4] Layout-based extraction wrote {sum(1 for r in records if r.get('status')=='ok_layout')} CSVs.")


    # 4) Save index.csv
    print("[4/4] Writing index.csv …")
    idx_path = out_dir / "index.csv"
    pd.DataFrame.from_records(records).to_csv(idx_path, index=False)

    # Cleanup our crop folder (this is ours, not used by Camelot/Tabula atexit)
    _safe_rmtree(temp_dir)


    print(f"\nDone. Index: {idx_path}")
    print(f"CSV folder: {tables_dir}\n")


if __name__ == "__main__":
    main()
