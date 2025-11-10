import argparse
import csv
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import requests

# ------- logging -------
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ------- normalization helpers -------
def norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def norm_punct(s: str) -> str:
    s = norm(s)
    s = re.sub(r"[^\w\s&]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def get_year_from_issued(item: dict) -> str:
    issued = item.get("issued", {})
    parts = issued.get("date-parts") or []
    if parts and parts[0] and len(parts[0]) >= 1:
        return str(parts[0][0])
    return ""

# ------- journal abbreviation map (extend as you go) -------
JOURNAL_MAP = {
    "sci rep": "Scientific Reports",
    "chem commun": "Chemical Communications",
    "chem. commun.": "Chemical Communications",
    "dalton trans": "Dalton Transactions",
    "phys chem chem phys": "Physical Chemistry Chemical Physics",
    "phys. chem. chem. phys.": "Physical Chemistry Chemical Physics",
    "appl phys lett": "Applied Physics Letters",
    "appl. phys. lett.": "Applied Physics Letters",
    "appl surf sci": "Applied Surface Science",
    "appl. surf. sci.": "Applied Surface Science",
    "acs nano": "ACS Nano",
    "acs mater au": "ACS Materials Au",
    "acs appl electron mater": "ACS Applied Electronic Materials",
    "acs appl. electron. mater.": "ACS Applied Electronic Materials",
    "chem rev": "Chemical Reviews",
    "chem. rev.": "Chemical Reviews",
    "j photochem photobiol c photochem rev": "Journal of Photochemistry and Photobiology C: Photochemistry Reviews",
    "j. photochem. photobiol. c photochem. rev.": "Journal of Photochemistry and Photobiology C: Photochemistry Reviews",
    "j mater chem c": "Journal of Materials Chemistry C",
    "j. mater. chem. c": "Journal of Materials Chemistry C",
    "j nanophotonics": "Journal of Nanophotonics",

    # Vacuum Science & Technology (existing + new)
    "j vac sci technol a": "Journal of Vacuum Science & Technology A",
    "j. vac. sci. technol. a": "Journal of Vacuum Science & Technology A",
    "vac sci technol a": "Journal of Vacuum Science & Technology A",
    "vac. sci. technol. a": "Journal of Vacuum Science & Technology A",

    "j vac sci technol b microelectron nanometer struct process meas phenom": "Journal of Vacuum Science & Technology B",
    "j. vac. sci. technol. b microelectron nanometer struct process meas phenom": "Journal of Vacuum Science & Technology B",
    "j vac sci technol b": "Journal of Vacuum Science & Technology B",
    "j. vac. sci. technol. b": "Journal of Vacuum Science & Technology B",
    "vac sci technol b": "Journal of Vacuum Science & Technology B",
    "vac. sci. technol. b": "Journal of Vacuum Science & Technology B",
    "j vac sci technol b microelectron process phenom": "Journal of Vacuum Science & Technology B",
    "j. vac. sci. technol., b: microelectron. process. phenom.": "Journal of Vacuum Science & Technology B",
    "journal of vacuum science & technology b microelectronics and nanometer structures processing measurement and phenomena": "Journal of Vacuum Science & Technology B",

    "j chem phys": "The Journal of Chemical Physics",
    "j. chem. phys.": "The Journal of Chemical Physics",
    "j appl phys": "Journal of Applied Physics",
    "j. appl. phys.": "Journal of Applied Physics",
    "j phys chem c": "The Journal of Physical Chemistry C",
    "j. phys. chem. c": "The Journal of Physical Chemistry C",
    "j phys chem lett": "The Journal of Physical Chemistry Letters",
    "j. phys. chem. lett.": "The Journal of Physical Chemistry Letters",
    "laser photonics rev": "Laser & Photonics Reviews",
    "laser photonics rev.": "Laser & Photonics Reviews",
    "rsc adv": "RSC Advances",
    "rsc adv.": "RSC Advances",
    "nat methods": "Nature Methods",
    "j fluoresc": "Journal of Fluorescence",
    "j clinmicrobiol": "Journal of Clinical Microbiology",
    "mater sci semicond process": "Materials Science in Semiconductor Processing",
    "mater. sci. semicond. process.": "Materials Science in Semiconductor Processing",
    "mater sci eng r rep": "Materials Science and Engineering: R: Reports",
    "mater sci eng r rep.": "Materials Science and Engineering: R: Reports",
    "recl trav chim pays-bas": "Recueil des Travaux Chimiques des Pays-Bas",

    # IOP “J. Phys. D”
    "j phys d appl phys": "Journal of Physics D: Applied Physics",
    "j. phys. d: appl. phys.": "Journal of Physics D: Applied Physics",

    # ACS / chemistry core (additions)
    "chem mater": "Chemistry of Materials",
    "chem. mater.": "Chemistry of Materials",
    "acs appl mater interfaces": "ACS Applied Materials & Interfaces",
    "acs appl. mater. interfaces": "ACS Applied Materials & Interfaces",

    # ECS journals + meetings
    "ecs j solid state sci technol": "ECS Journal of Solid State Science and Technology",
    "ecs j. solid state sci. technol.": "ECS Journal of Solid State Science and Technology",
    "j ecs j solid state sci technol": "ECS Journal of Solid State Science and Technology",
    "ecs meeting abstracts": "ECS Meeting Abstracts",

    # MRS proceedings
    "mrs proc": "MRS Proceedings",
    "mrs proc.": "MRS Proceedings",
    "materials research society symposium proceedings": "MRS Proceedings",

    # Dalton / RSC legacy
    "chem soc dalton trans": "Journal of the Chemical Society, Dalton Transactions",
    "chem. soc., dalton trans.": "Journal of the Chemical Society, Dalton Transactions",

    # Electronic Materials Letters
    "electron mater lett": "Electronic Materials Letters",
    "electron. mater. lett.": "Electronic Materials Letters",
}

JOURNAL_MAP.update({
    # --- extra aliases from the new refs ---
    "surf sci rep": "Surface Science Reports",
    "surf. sci. rep.": "Surface Science Reports",
    "chem vapor depos": "Chemical Vapor Deposition",
    "chem. vapor depos.": "Chemical Vapor Deposition",
    "chem vap depos": "Chemical Vapor Deposition",
    "annu rev chem biomol eng": "Annual Review of Chemical and Biomolecular Engineering",
    "annu. rev. chem. biomol. eng.": "Annual Review of Chemical and Biomolecular Engineering",
    "annual review of chemical and biomolecular engineering": "Annual Review of Chemical and Biomolecular Engineering",
    "japan j appl phys": "Japanese Journal of Applied Physics",
    "jpn j appl phys": "Japanese Journal of Applied Physics",
    "jpn. j. appl. phys.": "Japanese Journal of Applied Physics",
    "phys rev lett": "Physical Review Letters",
    "phys. rev. lett.": "Physical Review Letters",
    "solid state commun": "Solid State Communications",
    "solid state commun.": "Solid State Communications",
    "prog surf sci": "Progress in Surface Science",
    "prog. surf. sci.": "Progress in Surface Science",
    "mater sci eng a": "Materials Science and Engineering: A",
    "mater. sci. eng. a": "Materials Science and Engineering: A",
    "nano lett": "Nano Letters",
    "nano lett.": "Nano Letters",
    "nat mater": "Nature Materials",
    "nat. mater.": "Nature Materials",
    "electrochem solid-state lett": "Electrochemical and Solid-State Letters",
    "electrochem. solid-state lett.": "Electrochemical and Solid-State Letters",
    "electrochem solid state lett": "Electrochemical and Solid-State Letters",
    "j thermal anal calorim": "Journal of Thermal Analysis and Calorimetry",
    "j therm anal calorim": "Journal of Thermal Analysis and Calorimetry",
    "j. therm. anal. calorim.": "Journal of Thermal Analysis and Calorimetry",
    "j. ther. anal. calorimetry": "Journal of Thermal Analysis and Calorimetry",
    "j korean phys soc": "Journal of the Korean Physical Society",
    "j. korean phys. soc.": "Journal of the Korean Physical Society",
    "nanotechnology": "Nanotechnology",
    # helpful variants
    "j phys d": "Journal of Physics D: Applied Physics",
    "j. phys. d": "Journal of Physics D: Applied Physics",
    "j phys d: appl phys": "Journal of Physics D: Applied Physics",
    "acs appl mater interfaces": "ACS Applied Materials & Interfaces",
    "acs appl. mater. interf.": "ACS Applied Materials & Interfaces",
    "chem mater.": "Chemistry of Materials",
    "acs appl electron materials": "ACS Applied Electronic Materials",
    "j vac sci technol": "Journal of Vacuum Science & Technology",
    "j. vac. sci. technol.": "Journal of Vacuum Science & Technology",
})

JOURNAL_MAP.update({
    # New (from your refs)
    "adv funct mater": "Advanced Functional Materials",
    "adv. funct. mater.": "Advanced Functional Materials",

    "plasma processes polym": "Plasma Processes and Polymers",
    "plasma processes polym.": "Plasma Processes and Polymers",

    "ieee trans nanotechnol": "IEEE Transactions on Nanotechnology",
    "ieee trans. nanotechnol.": "IEEE Transactions on Nanotechnology",

    "korean j chem eng": "Korean Journal of Chemical Engineering",
    "korean j. chem. eng.": "Korean Journal of Chemical Engineering",

    "phys plasmas": "Physics of Plasmas",
    "phys. plasmas": "Physics of Plasmas",

    "acc chem res": "Accounts of Chemical Research",
    "acc. chem. res.": "Accounts of Chemical Research",

    "acs sustainable chem eng": "ACS Sustainable Chemistry & Engineering",
    "acs sustainable chem. eng.": "ACS Sustainable Chemistry & Engineering",
})


def expand_journal(j: str) -> str:
    jn = norm_punct(j)
    return JOURNAL_MAP.get(jn, j)

JVST_A_ALIASES = {
    "journal of vacuum science & technology a",
    "journal of vacuum science & technology a: vacuum, surfaces, and films",
    "j vac sci technol a",
}
JVST_B_ALIASES = {
    "journal of vacuum science & technology b",
    "journal of vacuum science & technology b: microelectronics and nanometer structures processing measurement and phenomena",
    "j vac sci technol b",
}

def is_jvst_ab(jname: str) -> bool:
    j = norm_punct(expand_journal(jname))
    return j in {norm_punct(x) for x in JVST_A_ALIASES | JVST_B_ALIASES}


# ------- TXT parsing (robust) -------

# Detect starts like:
#   [12] ...   |   12. ...   |   12) ...   |   12- ...   |   12Smith ... (no space)
# BUT NOT plain "12 " (digits + space) which often starts a continuation like "324 (1992)."
_START_RE = re.compile(
    r"""^\s*
        (?:\[(?P<b>\d+)\]            # [n]
         |
         (?P<d>\d+)                  # n
         (?=                         # lookahead: don't consume
             [\.\)\-]                # punctuation after the number
             |                       # OR
             \s*[A-Z]                # optional space(s) then an Uppercase letter (author)
         )
        )
    """,
    re.VERBOSE
)


def _match_ref_start(line: str) -> Optional[int]:
    """
    Return the numeric index if the line starts a new reference, else None.
    Supports: [n]  |  n.  |  n)  |  n-
    """
    m = _START_RE.match(line)
    if not m:
        return None
    return int(m.group("b") or m.group("d"))

def _strip_any_index_prefix(line: str) -> Tuple[Optional[int], str]:
    """
    Strip leading index prefix and return (idx, rest_of_line).
    """
    m = _START_RE.match(line)
    if m:
        idx = int(m.group("b") or m.group("d"))
        return idx, line[m.end():].strip()
    return None, line.strip()

def join_wrapped_refs(txt_path: Path) -> List[str]:
    """
    Combine wrapped lines into one string per reference.
    Works for both:
      - [n] Reference lines (possibly wrapped)
      - n. / n) / n- Reference lines (possibly wrapped)
    """
    lines = [ln.rstrip() for ln in txt_path.read_text(encoding="utf-8").splitlines()]

    refs: List[str] = []
    cur_idx: Optional[int] = None
    cur_text: List[str] = []

    def _flush():
        nonlocal cur_idx, cur_text
        if cur_idx is not None:
            # Join with spaces, normalize internal whitespace
            joined = " ".join(part.strip() for part in cur_text if part.strip())
            # Rebuild a canonical "[n] " prefix so the downstream parser can stay unchanged
            refs.append(f"[{cur_idx}] {joined}".strip())
        cur_idx, cur_text = None, []

    for raw in lines:
        if not raw.strip():
            continue

        maybe_idx = _match_ref_start(raw)

        if maybe_idx is not None:
            # Guard against false positives like "324 (1992)." being split off:
            is_sequential = (cur_idx is None and maybe_idx == 1) or (cur_idx is not None and maybe_idx == cur_idx + 1)

            if not is_sequential:
                # Not sequential → treat as a continuation line (likely page/year)
                cur_text.append(raw.strip())
                continue

            # Starting a new, sequential reference
            _flush()
            cur_idx = maybe_idx
            _, rest = _strip_any_index_prefix(raw)
            cur_text.append(rest)
        else:
            # Continuation of current reference (page/article/year tails, etc.)
            if cur_idx is None:
                cur_idx = 1
            cur_text.append(raw.strip())

    _flush()
    return refs

def strip_bracket_index(line: str) -> Tuple[Optional[int], str]:
    m = re.match(r"\s*\[(\d+)\]\s*(.*)", line.strip())
    if m:
        return int(m.group(1)), m.group(2)
    return None, line.strip()

def extract_year(s: str) -> Optional[str]:
    m = re.search(r"\b(19|20)\d{2}\b", s)
    return m.group(0) if m else None

def extract_volume_after_year(s: str, year: Optional[str]) -> Optional[str]:
    if not year: return None
    idx = s.find(year)
    if idx == -1: return None
    tail = s[idx + len(year):]
    # commonly "... year, VOL, PAGE"
    m = re.search(r",\s*([0-9]+(?:\s*\(\s*\d+(?:\s*[–-]\s*\d+)?\s*\))?)\s*,", tail)
    if m: return m.group(1)
    m = re.search(r"[,;]\s*([0-9]+(?:\s*\(\s*\d+(?:\s*[–-]\s*\d+)?\s*\))?)\b", tail)
    if m: return m.group(1)
    return None

def extract_page_or_artnum(s: str) -> Optional[str]:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 2:
        token = parts[-1].rstrip(".").replace(" ", "").replace("\u00a0", "")
        token = token.replace("-", "")
        if re.search(r"[0-9]{1,}", token):
            return token
    return None

def extract_journal(s: str, year: Optional[str]) -> Optional[str]:
    if not year: return None
    pos = s.find(year)
    if pos == -1: return None
    left = s[:pos].rstrip()
    cpos = left.rfind(",")
    if cpos == -1: return None
    j = left[cpos+1:].strip().rstrip(".")
    return j if j else None

def extract_author_lastnames(s: str, max_authors: int = 5) -> List[str]:
    year = extract_year(s) or ""
    j = extract_journal(s, year) or ""
    stop = s.find(j) if j else (s.find(year) if year else len(s))
    author_segment = s[:max(0, stop)]
    parts = [p.strip() for p in re.split(r",|;| and ", author_segment) if p.strip()]
    lastnames = []
    for p in parts[:max_authors]:
        ws = re.findall(r"[A-Za-z][A-Za-z\-']+", p)
        if ws:
            lastnames.append(ws[-1])
    return lastnames[:max_authors]

NON_JOURNAL_HINTS = [
    r"\bIEDM\b", r"\bInternational\s+Electron\s+Devices\s+Meeting\b",
    r"\bSymposium\b", r"\bConference\b", r"\bProceedings\b", r"\bIOP\s+Conf\.\s+Ser\b",
    r"\bUS\s*Pat", r"\bPatent\b",
    r"http[s]?://", r"\bto be published\b", r"\bpp\.\s*\d+",

    # NEW: book/handbook/chapter cues & common publishers
    r"\b in \s+[A-Z][^,]+?\(",          # “..., “Title,” in Book Title (Publisher, City, Year)”
    r"\bHandbook\b",
    r"\bed\.|\bedition\b",
    r"\b(Wiley|Elsevier|Springer|CRC|Cambridge\s+Univ\.?\s*Press|Oxford\s+Univ\.?\s*Press)\b",
]
NON_JOURNAL_RE = re.compile("|".join(NON_JOURNAL_HINTS), re.IGNORECASE)

def is_non_journal_ref(text: str) -> bool:
    return bool(NON_JOURNAL_RE.search(text))


# With quoted title:
J_REF_WITH_TITLE = re.compile(
    r"""^\s*(?:\[\d+\]\s*)?                 # optional [n]
        (?P<authors>.+?),\s*               # authors (comma-separated)
        [“"](?P<title>.+?)[”"]\s*,\s*      # “Title,” or "Title,"
        (?P<journal>.+?)\s*(?:,|\s)\s*     # journal, then comma OR just whitespace
        (?P<volume>\d+(?:\s*\(\s*\d+(?:\s*[–-]\s*\d+)?\s*\))?)   # volume or volume(issue/range)
        (?:\s*(?:,|\s)\s*(?P<page>[^\s,(]+))?   # optional page/article token (comma OR space)
        \s*\(\s*(?P<year>\d{4})\s*\)\.?    # (YEAR)
        """,
    re.VERBOSE
)

# Without title:
J_REF_NO_TITLE = re.compile(
    r"""^\s*(?:\[\d+\]\s*)?                 # optional [n]
        (?P<authors>.+?),\s*               # authors
        (?P<journal>.+?)\s*(?:,|\s)\s*     # journal, then comma OR just whitespace
        (?P<volume>\d+(?:\s*\(\s*\d+(?:\s*[–-]\s*\d+)?\s*\))?)   # volume or volume(issue)
        (?:\s*(?:,|\s)\s*(?P<page>[^\s,(]+))?   # optional page/article token
        \s*\(\s*(?P<year>\d{4})\s*\)\.?    # (YEAR)
        """,
    re.VERBOSE
)

def parse_single_ref(line: str, fallback_idx: int) -> dict:
    idx, body = strip_bracket_index(line)

    # Quietly tag non-journal items and skip strict parsing
    if is_non_journal_ref(body):
        y = extract_year(body) or ""
        return {
            "idx": idx or fallback_idx,
            "raw_ref": line,
            "authors": extract_author_lastnames(body, max_authors=5),
            "journal": "",  # unknown / non-journal
            "year": y,
            "volume": "",
            "page_or_article": "",
        }

    m = J_REF_WITH_TITLE.search(body) or J_REF_NO_TITLE.search(body)
    if m:
        j = (m.groupdict().get("journal") or "").strip().rstrip(".")
        v = (m.groupdict().get("volume") or "").strip()
        p = (m.groupdict().get("page") or "" ).strip()
        y = (m.groupdict().get("year") or "" ).strip()
        auths = extract_author_lastnames(body, max_authors=5)
        return {
            "idx": idx or fallback_idx,
            "raw_ref": line,
            "authors": auths,
            "journal": j,
            "year": y,
            "volume": v,
            "page_or_article": p
        }

    # --- fallback heuristics ---
    y = extract_year(body) or ""
    v = extract_volume_after_year(body, y) or ""
    p = extract_page_or_artnum(body) or ""
    j = extract_journal(body, y) or ""
    auths = extract_author_lastnames(body, max_authors=5)
    log(f"[warn] regex parse failed for idx={idx or fallback_idx}: {body}")
    return {
        "idx": idx or fallback_idx,
        "raw_ref": line,
        "authors": auths,
        "journal": j,
        "year": y,
        "volume": v,
        "page_or_article": p
    }


def parse_refs_from_txt(txt_path: Path) -> List[dict]:
    joined = join_wrapped_refs(txt_path)
    joined = [ln for ln in joined if re.search(r"\b(19|20)\d{2}\b", ln)]
    recs = [parse_single_ref(ln, i) for i, ln in enumerate(joined, 1)]
    # Normalize zero/pseudo indices to a sequential order if any 0 slipped in
    for i, r in enumerate(recs, 1):
        if not isinstance(r["idx"], int) or r["idx"] <= 0:
            r["idx"] = i
    recs.sort(key=lambda r: int(r["idx"]))
    return recs


# ------- Crossref querying -------
def pick_page_or_article_filter(token: str, journal: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (page_filter, article_number_filter). For JVST A/B we avoid page filter on first pass.
    """
    if not token:
        return (None, None)
    t = token.strip()
    has_alpha = bool(re.search(r"[A-Za-z]", t))
    starts_zero = t.startswith("0")
    only_digits_flag = bool(re.fullmatch(r"\d+", t))

    # JVST: often inconsistent storage -> prefer *no* page filter initially
    if is_jvst_ab(journal):
        # still return both so later passes can choose to use them
        p = f"page:{t}" if only_digits_flag or starts_zero else None
        a = f"article-number:{t}" if (has_alpha or starts_zero or len(t) >= 5) else None
        return (p, a)

    # Non-JVST heuristic
    if has_alpha or starts_zero:
        return (None, f"article-number:{t}")
    if only_digits_flag and len(t) >= 1:
        return (f"page:{t}", None)
    return (f"page:{t}", f"article-number:{t}")


def alternate_page_tokens(token: str) -> List[str]:
    """
    Return plausible page tokens to try.
    For JVST-style article numbers, Crossref may drop leading zeros.
    e.g., '032603' -> ['032603', '32603'].
    """
    if not token:
        return []
    t = token.strip()
    alts = [t]
    if t.startswith("0") and t.lstrip("0"):
        alts.append(t.lstrip("0"))
    return list(dict.fromkeys(alts))  # de-dup

# ---- modify crossref_query: build requests in passes and suppress page filter for JVST on first pass ----
def crossref_query(journal: str, year: str, volume: str, page_or_art: str,
                   authors: List[str], mailto: str, rows: int = 7,
                   raw_biblio: Optional[str] = None) -> List[dict]:
    headers = {"User-Agent": f"txt-ref-resolver/1.0 (mailto:{mailto})"} if mailto else {}

    def _request(params):
        try:
            r = requests.get("https://api.crossref.org/works", params=params, headers=headers, timeout=20)
            r.raise_for_status()
            return r.json().get("message", {}).get("items", []) or []
        except Exception:
            return []

    # shared base
    base = {
        "rows": rows,
        "select": "DOI,title,container-title,issued,volume,page,author,article-number",
    }
    if journal:
        base["query.container-title"] = expand_journal(journal)

    # filters common to several passes
    def common_filters(use_volume=True):
        flt = []
        if year and re.fullmatch(r"\d{4}", year):
            flt += [f"from-pub-date:{year}-01-01", f"until-pub-date:{year}-12-31"]
        if use_volume and volume:
            # strip any issue part like "27(1)" → volume=27
            vol_only = re.match(r"\s*(\d+)", volume)
            flt.append(f"volume:{vol_only.group(1) if vol_only else volume}")
        return flt

    # Precompute page/article filters
    pfil, afil = pick_page_or_article_filter(page_or_art, journal)

    # -------- Pass 1: strict container + year + volume (NO page filter if JVST), with author
    params1 = dict(base)
    params1["filter"] = ",".join(common_filters(use_volume=True))
    if not is_jvst_ab(journal) and pfil:
        params1["filter"] += ("," + pfil)
    if not is_jvst_ab(journal) and afil:
        params1["filter"] += ("," + afil)
    if authors:
        params1["query.author"] = authors[0]
    # helpful biblio hint
    hint = " ".join([expand_journal(journal) if journal else "", volume or "", page_or_art or "", year or ""]).strip()
    if hint:
        params1["query.bibliographic"] = hint

    items = _request(params1)
    if items:
        return items

    # -------- Pass 2: drop author
    params2 = dict(params1)
    params2.pop("query.author", None)
    items = _request(params2)
    if items:
        return items

    # -------- Pass 3 (JVST emphasis): container + year + volume, *no page/article filter at all*
    params3 = dict(base)
    params3["filter"] = ",".join(common_filters(use_volume=True))
    items = _request(params3)
    if items:
        return items

    # -------- Pass 4: full raw bibliographic string
    if raw_biblio and raw_biblio.strip():
        params4 = dict(base)
        params4["query.bibliographic"] = raw_biblio
        if year and re.fullmatch(r"\d{4}", year):
            params4["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
        items = _request(params4)
        if items:
            return items

    # -------- Pass 5: compact biblio (authors/journal/year/volume/page)
    parts = [", ".join(authors[:3]) if authors else "", journal, year, volume, page_or_art]
    compact = ", ".join([p for p in parts if p]).strip(", ")
    if compact:
        params5 = dict(base)
        params5["query.bibliographic"] = compact
        if year and re.fullmatch(r"\d{4}", year):
            params5["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
        items = _request(params5)
        if items:
            return items


    return []


# ------- scoring -------
def same_journal(want_j: str, got_container_list: List[str]) -> bool:
    if not want_j or not got_container_list:
        return False
    want = norm_punct(expand_journal(want_j))
    for c in got_container_list:
        got = norm_punct(c)
        # require equality or strong containment in *either* direction
        if want == got or want in got or got in want:
            return True
    return False

def looks_like_wrong_venue(item: dict) -> bool:
    """Block obvious mismatches that often slip through Crossref fallback."""
    ct = " ".join(item.get("container-title") or []).lower()
    bad = [
        "meeting abstracts",          # ECS Meeting Abstracts etc.
        "proceedings",                # generic proceedings
        "neuroscience applied",       # random journals that popped up in logs
        "micromachines",
        "annals of oncology",
    ]
    return any(b in ct for b in bad)


def score_candidate(item: dict, want: dict) -> int:
    score = 0
    # Year
    cy = get_year_from_issued(item)
    if want["year"] and cy == want["year"]:
        score += 20
    # Journal
    cj_list = item.get("container-title") or []
    if same_journal(want["journal"], cj_list):
        score += 35
    # Volume
    cv = (item.get("volume") or "").strip()
    # Compare only leading numeric for volume if want has issue like "27(1)"
    want_vol_num = re.match(r"\s*(\d+)", want["volume"] or "")
    want_vol_num = want_vol_num.group(1) if want_vol_num else (want["volume"] or "")
    if cv and want_vol_num and cv == want_vol_num:
        score += 15
    # Page / article-number
    wp = want["page_or_article"]
    if wp:
        ip = (item.get("page") or "").replace(" ", "")
        ia = (item.get("article-number") or "")
        if ip and re.search(rf"\b{re.escape(wp)}\b", ip):
            score += 20
        if ia and only_digits(ia) == only_digits(wp):
            score += 20
    # Authors (up to 3)
    want_auths = [norm_punct(a) for a in (want["authors"] or []) if a]
    item_auths = [norm_punct(a.get("family","")) for a in (item.get("author") or []) if a.get("family")]
    matches = sum(1 for x in want_auths[:3] if x and x in item_auths)
    score += min(10, matches * 5)
    return score

# ------- resume helpers -------
def last_processed_idx(out_csv: Path) -> int:
    """
    Return the max idx found in an existing output CSV.
    If the file doesn't exist or has no rows, returns 0.
    """
    if not out_csv.exists():
        return 0
    max_idx = 0
    try:
        with out_csv.open("r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    max_idx = max(max_idx, int(row.get("idx", "0")))
                except Exception:
                    continue
    except Exception:
        pass
    return max_idx

# ------- main resolve loop (streaming append) -------
def resolve_and_write(
    refs: List[dict],
    out_csv: Path,
    mailto: str,
    min_score: int,
    rows: int,
    pause: float,
    start_after_idx: int = 0,
    limit: Optional[int] = None,
):
    # Decide write mode and whether to emit header
    write_header = not out_csv.exists() or start_after_idx == 0
    mode = "w" if write_header else "a"

    processed = 0
    total_remaining = sum(1 for r in refs if int(r["idx"]) > start_after_idx)
    if limit is not None:
        total_remaining = min(total_remaining, limit)

    with out_csv.open(mode, encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "idx","raw_ref","best_doi","best_title","best_container_title",
                "best_year","best_volume","best_page","best_article_number","score","decision"
            ])

        for rec in refs:
            idx = int(rec["idx"])
            if idx <= start_after_idx:
                continue
            if limit is not None and processed >= limit:
                break

            want = {
                "authors": rec["authors"],
                "journal": rec["journal"],
                "year": rec["year"],
                "volume": rec["volume"],
                "page_or_article": rec["page_or_article"],
            }

            items = crossref_query(
                rec["journal"], rec["year"], rec["volume"], rec["page_or_article"],
                rec["authors"], mailto, rows=rows, raw_biblio=rec["raw_ref"]
            )

            best, best_score = None, -1
            for it in items:
                sc = score_candidate(it, want)
                if sc > best_score:
                    best, best_score = it, sc

            # ---- hard checks BEFORE extracting fields ----
            if best:
                # strict journal match if we have a journal
                if want["journal"]:
                    cj_list = best.get("container-title") or []
                    if not same_journal(want["journal"], cj_list):
                        best, best_score = None, -1
                # obvious venue mismatches
                if best and looks_like_wrong_venue(best):
                    best, best_score = None, -1

            # Now populate output fields only if best survived
            doi = title = cont = byear = bvol = bpage = bart = ""
            if best:
                doi = (best.get("DOI") or "").lower().strip()
                tl = best.get("title") or []
                title = tl[0].strip() if tl else ""
                cl = best.get("container-title") or []
                cont = cl[0].strip() if cl else ""
                byear = get_year_from_issued(best)
                bvol = (best.get("volume") or "").strip()
                bpage = (best.get("page") or "").strip()
                bart = (best.get("article-number") or "").strip()

            decision = "accepted" if (best and best_score >= min_score) else ("low_confidence" if best else "no_match")

            # Write row immediately (so an interrupt still keeps progress)
            w.writerow([idx, rec["raw_ref"], doi, title, cont, byear, bvol, bpage, bart, best_score if best else "", decision])
            processed += 1

            if processed % 10 == 0 or processed == total_remaining:
                log(f"[{processed}/{total_remaining}] idx={idx} score={best_score} decision={decision} → {doi}")

            time.sleep(pause)

# ------- CLI -------
def main():
    ap = argparse.ArgumentParser(description="Resolve DOIs from a TXT list of title-less references via Crossref (simple resume).")
    ap.add_argument("--txt", required=True, help="TXT file: references may be wrapped and numbered as [n] or n./n)/n-")
    ap.add_argument("--out", default="resolved_refs.csv", help="Output CSV")
    ap.add_argument("--mailto", default="", help="Email for Crossref User-Agent (recommended)")
    ap.add_argument("--min-score", type=int, default=50, help="Min score to accept a match (raise to be stricter)")
    ap.add_argument("--rows", type=int, default=20, help="Crossref candidates to fetch per ref")
    ap.add_argument("--pause", type=float, default=0.25, help="Seconds to sleep between Crossref requests")
    ap.add_argument("--limit", type=int, default=None, help="Process only first N refs from the resume point")
    ap.add_argument("--resume", action="store_true", help="Read existing --out CSV and continue from the next idx")
    ap.add_argument("--start-idx", type=int, default=None, help="Override: start after this idx (ignores --resume)")
    args = ap.parse_args()

    txt_path = Path(args.txt).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    refs = parse_refs_from_txt(txt_path)
    if not refs:
        log("No references parsed from TXT.")
        return

    log(f"Parsed {len(refs)} references from TXT (min idx={refs[0]['idx']} max idx={refs[-1]['idx']})")

    if args.start_idx is not None:
        start_after = int(args.start_idx)
        log(f"Starting after idx={start_after} (via --start-idx)")
    elif args.resume:
        start_after = last_processed_idx(out_path)
        log(f"Resuming after idx={start_after} (found in {out_path})")
    else:
        start_after = 0
        log("Fresh run: writing new CSV (header will be written)")

    resolve_and_write(
        refs=refs,
        out_csv=out_path,
        mailto=args.mailto,
        min_score=args.min_score,
        rows=args.rows,
        pause=args.pause,
        start_after_idx=start_after,
        limit=args.limit,
    )

    log(f"Done. Wrote/updated: {out_path}")

if __name__ == "__main__":
    main()
