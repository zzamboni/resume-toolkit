#!/usr/bin/env python3

from pathlib import Path
import bibtexparser
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, UTC
import logging
from collections import defaultdict
import re
import html
import json
import os
import copy
import subprocess

#logging.getLogger("bibtexparser").setLevel(logging.ERROR)

BIB_DIR = Path(os.environ.get("PUBS_BIB_DIR", "."))
OUT_FILE = Path(os.environ.get("PUBS_HTML", "dist/publications.html"))
TEMPLATE_DIR = Path("templates")
PUBS_OUT_DIR = Path(os.environ.get("PUBS_OUT_DIR", "")) if os.environ.get("PUBS_OUT_DIR") else None
PUBS_BIB_FILENAME = os.environ.get("PUBS_BIB_FILENAME", "publications.bib")
PUBS_RESUME_JSON = os.environ.get("PUBS_RESUME_JSON", "")

EXPORT_SELECTED = False
SELECTED_KEYWORD = "selected"
SELECTED_OUT_FILE = Path("site/selected-publications.json")

DEFAULT_SECTION_ORDER = [
    "book",
    "editorial",
    "thesis",
    "refereed",
    "techreport",
    "presentations",
    "invited",
    "patent",
    "other",
]

DEFAULT_SECTION_TITLES = {
    "book": "Books",
    "editorial": "Editorial Activities",
    "thesis": "Theses",
    "refereed": "Refereed Papers",
    "techreport": "Technical Reports",
    "presentations": "Presentations",
    "invited": "Invited Talks and Articles",
    "patent": "Patents",
    "other": "Other Publications",
}

FA_ICON_SCRIPT = Path("scripts/render_fa_icon.mjs")
_ICON_CACHE = {}


def extract_entry_types(bibtex_source: str) -> dict[str, str]:
    entry_types = {}
    for match in re.finditer(r"@([A-Za-z][A-Za-z0-9_-]*)\s*\{\s*([^,\s]+)\s*,", bibtex_source):
        entry_type = match.group(1).lower()
        entry_key = match.group(2).strip()
        if entry_key:
            entry_types[entry_key] = entry_type
    return entry_types


def normalize_bibtex_for_parser(bibtex_source: str) -> str:
    # bibtexparser rejects @patent even though downstream Typst/pergamon supports it.
    # Parse it as techreport here, then restore ENTRYTYPE afterwards for rendering/output.
    return re.sub(r"@patent(\s*\{)", r"@techreport\1", bibtex_source, flags=re.IGNORECASE)


def extract_raw_bib_entries(bibtex_source: str) -> dict[str, str]:
    raw_entries = {}
    entry_start_re = re.compile(r"@([A-Za-z][A-Za-z0-9_-]*)\s*\{")
    pos = 0

    while True:
        match = entry_start_re.search(bibtex_source, pos)
        if not match:
            break

        brace_start = match.end() - 1
        key_start = match.end()
        key_end = bibtex_source.find(",", key_start)
        if key_end == -1:
            pos = match.end()
            continue

        entry_key = bibtex_source[key_start:key_end].strip()
        if not entry_key:
            pos = match.end()
            continue

        depth = 0
        end = None
        for idx in range(brace_start, len(bibtex_source)):
            ch = bibtex_source[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break

        if end is None:
            pos = match.end()
            continue

        raw_entries[entry_key] = bibtex_source[match.start():end].strip()
        pos = end

    return raw_entries


def load_icon_svg(icon_name: str) -> str:
    if not icon_name:
        return ""
    if icon_name in _ICON_CACHE:
        return _ICON_CACHE[icon_name]
    if not FA_ICON_SCRIPT.exists():
        _ICON_CACHE[icon_name] = ""
        return ""
    try:
        result = subprocess.run(
            ["node", str(FA_ICON_SCRIPT), icon_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        _ICON_CACHE[icon_name] = ""
        return ""

    svg = result.stdout.strip() if result.returncode == 0 else ""
    _ICON_CACHE[icon_name] = svg
    return svg

def parse_legacy_links(env_var: str):
    raw = os.environ.get(env_var, "")
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logging.warning("Invalid %s JSON payload; ignoring.", env_var)
        return []

    if isinstance(data, dict):
        return [{"label": str(k), "url": str(v)} for k, v in data.items()]

    if isinstance(data, list):
        links = []
        for item in data:
            if isinstance(item, dict) and "label" in item and "url" in item:
                links.append({"label": str(item["label"]), "url": str(item["url"])})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                links.append({"label": str(item[0]), "url": str(item[1])})
        return links

    return []



def parse_floating_links(env_var: str):
    raw = os.environ.get(env_var, "")
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logging.warning("Invalid %s JSON payload; ignoring.", env_var)
        return []

    if not isinstance(data, list):
        return []

    links = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("url")
        icon = item.get("icon")
        if name and url and icon:
            links.append(
                {
                    "name": str(name),
                    "url": str(url),
                    "icon": str(icon),
                    "icon_svg": load_icon_svg(str(icon)),
                }
            )
    return links


def load_resume_name() -> str:
    if not PUBS_RESUME_JSON:
        return "Publications"
    path = Path(PUBS_RESUME_JSON)
    if not path.exists():
        return "Publications"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data.get("basics", {}).get("name", "")
        return str(name).strip() or "Publications"
    except Exception:
        return "Publications"


def load_publications_label() -> str:
    if not PUBS_RESUME_JSON:
        return "Publications"
    path = Path(PUBS_RESUME_JSON)
    if not path.exists():
        return "Publications"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        label = (
            data.get("meta", {})
            .get("themeOptions", {})
            .get("sectionLabels", {})
            .get("publications")
        )
        if isinstance(label, str) and label.strip():
            return label.strip()
    except Exception:
        return "Publications"
    return "Publications"


def load_publications_options() -> dict:
    if not PUBS_RESUME_JSON:
        return {}
    path = Path(PUBS_RESUME_JSON)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        return {}
    options = meta.get("publicationsOptions", {})
    return options if isinstance(options, dict) else {}


def load_generated_publications_entry() -> dict:
    if not PUBS_RESUME_JSON:
        return {}
    path = Path(PUBS_RESUME_JSON)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    publications = data.get("publications")
    if not isinstance(publications, list):
        return {}
    entries = [pub for pub in publications if isinstance(pub, dict) and "bibfiles" in pub]
    if len(entries) > 1:
        raise SystemExit(
            "Multiple publications entries define bibfiles; only one generated-publications entry is allowed"
        )
    return entries[0] if entries else {}


def resolve_sectioning_config(publications_options: dict) -> tuple[bool, list[str], dict[str, str]]:
    pub_sections = publications_options.get("pubSections", False)

    if pub_sections is False:
        return False, ["all"], {"all": "Publications"}

    if isinstance(pub_sections, list):
        section_order = [str(s) for s in pub_sections if isinstance(s, str) and s.strip()]
        if not section_order:
            return False, ["all"], {"all": "Publications"}
    else:
        section_order = list(DEFAULT_SECTION_ORDER)

    custom_titles = publications_options.get("pubSectionTitles", {})
    if not isinstance(custom_titles, dict):
        custom_titles = {}

    section_titles = {}
    for section in section_order:
        title = custom_titles.get(section)
        if isinstance(title, str) and title.strip():
            section_titles[section] = title
        else:
            section_titles[section] = DEFAULT_SECTION_TITLES.get(section, section)

    return True, section_order, section_titles


# Minimal accent mapping (extend as needed)
LATEX_ACCENTS = {
    r"\\'a": "á",
    r"\\'e": "é",
    r"\\'i": "í",
    r"\\'o": "ó",
    r"\\'u": "ú",
    r"\\`a": "à",
    r"\\`e": "è",
    r"\\`i": "ì",
    r"\\`o": "ò",
    r"\\`u": "ù",
    r'\\"a': "ä",
    r'\\"e': "ë",
    r'\\"i': "ï",
    r'\\"o': "ö",
    r'\\"u': "ü",
    r"\\~n": "ñ",
    r"\\c{c}": "ç",
    r'\&': "&",
    '--': "–",
    r'\ ': " ",
    r'``': "“",
    r"''": "”",
}

def latex_to_html(s):
    if not s:
        return ""

    # Replace simple LaTeX accents
    for latex, char in LATEX_ACCENTS.items():
        s = s.replace(latex, char)
    
    # Convert \emph{} → <em>
    s = re.sub(r'\\emph\{([^{}]+)\}', r'<em>\1</em>', s)

    # Convert \textbf{} → <strong>
    s = re.sub(r'\\textbf\{([^{}]+)\}', r'<strong>\1</strong>', s)

    # Convert \href{...}{...} → <a href="...">...</a>
    s = re.sub(
        r'\\href\{([^{}]+)\}\{([^{}]+)\}',
        r'<a href="\1">\2</a>',
        s
    )

    # Convert \url{...} → <a href="...">...</a>
    s = re.sub(
        r'\\url\{([^{}]+)\}',
        r'<a href="\1">\1</a>',
        s
    )
    
    # Remove outer braces that are just grouping
    s = re.sub(r'\{(.*?)\}', r'\1', s)

    # Escape any remaining HTML characters
    # s = html.escape(s, quote=False)

    # But preserve the HTML we just injected
    s = s.replace("&lt;em&gt;", "<em>").replace("&lt;/em&gt;", "</em>")
    s = s.replace("&lt;strong&gt;", "<strong>").replace("&lt;/strong&gt;", "</strong>")
    s = s.replace("&lt;a (href=.*?)&gt;", r"<a \1>").replace("&lt;/a&gt;", "</a>")

    return s

def clean_bib_entry(entry):
    cleaned = {}
    for k, v in entry.items():
        if k.startswith("_"):
            continue
        if v is None:
            continue
        if isinstance(v, (str, int, float)):
            cleaned[k] = str(v)
    return cleaned

def write_combined_bib(raw_entries, raw_entry_text_by_key, sections, section_order, section_titles, sectioning_enabled):
    if not PUBS_OUT_DIR:
        return
    PUBS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_path = PUBS_OUT_DIR / PUBS_BIB_FILENAME
    chunks = []
    if sectioning_enabled:
        for section_key in section_order:
            section_entries = sections.get(section_key, [])
            if not section_entries:
                continue
            section_title = section_titles.get(section_key, section_key)
            chunks.append(f"% ====== {section_title} ======\n")
            for e in section_entries:
                key = e.get("key") or e.get("ID")
                if not key:
                    continue
                raw_entry_text = raw_entry_text_by_key.get(str(key))
                if raw_entry_text:
                    chunks.append(raw_entry_text)
                    chunks.append("")
            chunks.append("")
    else:
        for e in sections.get("all", []):
            key = e.get("key") or e.get("ID")
            if not key:
                continue
            raw_entry_text = raw_entry_text_by_key.get(str(key))
            if raw_entry_text:
                chunks.append(raw_entry_text)
                chunks.append("")
    combined_path.write_text("\n".join(chunks).strip() + "\n")

def group_by_section(entries, section_order, sectioning_enabled):
    grouped = defaultdict(list)
    for e in entries:
        section = e.get("_section")
        if sectioning_enabled:
            if section in section_order:
                grouped[section].append(e)
        else:
            if section == "all":
                grouped["all"].append(e)

    def sort_key(entry):
        year = entry.get("year")
        if year:
            return (int(year), "")
        date = entry.get("date") or ""
        return (0, str(date))

    if not sectioning_enabled:
        return {"all": sorted(grouped.get("all", []), key=sort_key, reverse=True)}

    # Ensure empty sections still exist, and sort each section by year (desc)
    return {
        s: sorted(grouped.get(s, []), key=sort_key, reverse=True)
        for s in section_order
    }

def load_bibtex():
    entries = []
    raw_entry_text_by_key = {}
    for bibfile in sorted(BIB_DIR.glob("*.bib")):
        bibtex_source = bibfile.read_text(encoding="utf-8")
        entry_types = extract_entry_types(bibtex_source)
        raw_entry_text_by_key.update(extract_raw_bib_entries(bibtex_source))
        normalized_source = normalize_bibtex_for_parser(bibtex_source)
        db = bibtexparser.loads(normalized_source)
        for e in db.entries:
            entry_key = e.get("ID") or e.get("key")
            original_type = entry_types.get(str(entry_key).strip(), "")
            if original_type:
                e["ENTRYTYPE"] = original_type
            e["_source"] = bibfile.stem
            entries.append(e)
            # print(f"Entry: {e}\n")
    return entries, raw_entry_text_by_key

def entry_to_jsonresume_publication(e):
    # JSON Resume "publications" shape: name, publisher, releaseDate, url, summary
    # We'll keep this conservative and robust across entry types.
    publisher = e.get("journal") or e.get("booktitle") or e.get("publisher") or ""
    year = e.get("year", 0)
    release_date = f"{year}-01-01" if year else ""

    # Title is already HTML-ish if you used latex_to_html; CV usually wants plain text.
    # If you kept raw fields (e.g. _title_raw), prefer that; otherwise strip tags lightly.
    name = e.get("title", "")
    name = name.replace("<em>", "").replace("</em>", "").replace("<strong>", "").replace("</strong>", "")

    summary_bits = []
    if e.get("authors"):
        summary_bits.append(e["authors"])
    if e.get("editor"):
        summary_bits.append(f"Editors: {e['editor']}")
    if e.get("note"):
        summary_bits.append(e["note"])

    return {
        "name": name,
        "publisher": publisher,
        "releaseDate": release_date,
        "url": e.get("url", ""),
        "summary": " — ".join([b for b in summary_bits if b]),
    }

def resolve_entry_filters() -> tuple[set[str], set[str]]:
    publication = load_generated_publications_entry()
    raw_keys = publication.get("bibentries", []) if isinstance(publication, dict) else []
    raw_keywords = publication.get("bibkeywords", []) if isinstance(publication, dict) else []

    selected_keys = {
        str(key).strip()
        for key in raw_keys
        if isinstance(key, str) and key.strip()
    }
    selected_keywords = {
        str(keyword).strip().lower()
        for keyword in raw_keywords
        if isinstance(keyword, str) and keyword.strip()
    }
    return selected_keys, selected_keywords


def filter_bib_entries(raw_entries, raw_entry_text_by_key):
    selected_keys, selected_keywords = resolve_entry_filters()
    if not selected_keys and not selected_keywords:
        return raw_entries, raw_entry_text_by_key

    filtered_entries = []
    filtered_raw_entry_text_by_key = {}
    for entry in raw_entries:
        entry_key = str(entry.get("key") or entry.get("ID") or "").strip()
        entry_keywords = {
            keyword.strip().lower()
            for keyword in str(entry.get("keywords", "")).split(",")
            if keyword.strip()
        }
        include = False
        if entry_key and entry_key in selected_keys:
            include = True
        if selected_keywords and entry_keywords.intersection(selected_keywords):
            include = True
        if include:
            filtered_entries.append(entry)
            if entry_key and entry_key in raw_entry_text_by_key:
                filtered_raw_entry_text_by_key[entry_key] = raw_entry_text_by_key[entry_key]
    return filtered_entries, filtered_raw_entry_text_by_key


def normalize(raw_entries, section_order, sectioning_enabled):
    entries = copy.deepcopy(raw_entries)
    for e in entries:
        # Ensure we have the bibtex key for anchoring
        # bibtexparser may use 'key' or 'ID' depending on version
        if "key" not in e and "ID" in e:
            e["key"] = e["ID"]
        
        # Year
        e["year"] = int(e.get("year", 0))

        # Authors
        e["authors"] = e.get("author", "").replace(" and ", ", ")

        FIELDS_TO_CLEAN = [
            "title",
            "journal",
            "booktitle",
            "publisher",
            "type",
            "issuetitle",
            "institution",
            "note",
            "howpublished"
        ]

        for field in FIELDS_TO_CLEAN:
            if field in e:
                # Preserve raw field before cleanup
                e[f"_{field}_raw"] = e[field]
                e[field] = latex_to_html(e[field])

        # Normalize DOI and generate its URL
        doi = e.get("doi")
        if doi:
            doi = doi.lower().replace("https://doi.org/", "").strip()
            e["_doi_url"] = f"https://doi.org/{doi}"
        else:
            e["_doi_url"] = None

        # Keywords → normalized set
        raw = e.get("keywords", "")
        e["_keywords"] = {
            k.strip().lower()
            for k in raw.split(",")
            if k.strip()
        }

        if not sectioning_enabled:
            e["_section"] = "all"
        else:
            # Determine section (first match wins). If none matches, skip entry.
            section = None
            for s in section_order:
                if s in e["_keywords"]:
                    section = s
                    break
            e["_section"] = section

    # Sort entries inside sections by year desc
    return sorted(entries, key=lambda e: e["year"], reverse=True)

def main():
    publications_options = load_publications_options()
    sectioning_enabled, section_order, section_titles = resolve_sectioning_config(publications_options)

    raw_entries, raw_entry_text_by_key = load_bibtex()
    raw_entries, raw_entry_text_by_key = filter_bib_entries(raw_entries, raw_entry_text_by_key)
    entries = normalize(raw_entries, section_order, sectioning_enabled)
    sections = group_by_section(entries, section_order, sectioning_enabled)
    write_combined_bib(raw_entries, raw_entry_text_by_key, sections, section_order, section_titles, sectioning_enabled)

    non_empty_sections = [
        s for s in section_order
        if sections.get(s)
    ] if sectioning_enabled else []

    selected_entries = [
        e for e in entries
        if SELECTED_KEYWORD in e.get("_keywords", set())
    ]

    if EXPORT_SELECTED:
        selected_payload = [entry_to_jsonresume_publication(e) for e in selected_entries]

        SELECTED_OUT_FILE.parent.mkdir(exist_ok=True)
        SELECTED_OUT_FILE.write_text(json.dumps(selected_payload, ensure_ascii=False, indent=2))
    
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tpl = env.get_template("publications.html.j2")

    dev_reload = os.environ.get("DEV_RELOAD", "") == "1"
    
    html = tpl.render(
        sections=sections,
        section_order=section_order,
        section_titles=section_titles,
        sectioning_enabled=sectioning_enabled,
        publications_label=load_publications_label(),
        toc_sections=non_empty_sections,
        generated=datetime.now(UTC).strftime("%Y-%m-%d"),
        dev_reload=dev_reload,
        floating_links=parse_floating_links("PUBS_LINKS"),
        resume_name=load_resume_name(),
    )

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(html)

if __name__ == "__main__":
    main()
