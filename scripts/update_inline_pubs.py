#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import bibtexparser

from build_publications import (
    entry_to_jsonresume_publication,
    extract_entry_types,
    latex_to_html,
    normalize_bibtex_for_parser,
)

FIELDS_TO_CLEAN = [
    "title",
    "journal",
    "booktitle",
    "publisher",
    "type",
    "issuetitle",
    "institution",
    "note",
    "howpublished",
]


def load_resume(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def get_generated_publications_entry(resume: dict[str, Any]) -> dict[str, Any] | None:
    publications = resume.get("publications")
    if not isinstance(publications, list):
        return None
    entries = [pub for pub in publications if isinstance(pub, dict) and "bibfiles" in pub]
    if len(entries) > 1:
        raise SystemExit(
            "Multiple publications entries define bibfiles; only one generated-publications entry is allowed"
        )
    return entries[0] if entries else None


def resolve_bib_files(cli_bibs: list[str], resume: dict[str, Any], json_path: Path) -> list[Path]:
    bibs = list(cli_bibs)
    if not bibs:
        publication = get_generated_publications_entry(resume)
        if publication is None:
            raise SystemExit(
                "No bibfiles provided and no generated-publications entry found in publications[]"
            )
        bib_list = publication.get("bibfiles", [])
        if isinstance(bib_list, list):
            bibs = [item for item in bib_list if isinstance(item, str) and item]

    resolved: list[Path] = []
    for bib in bibs:
        path = Path(bib)
        if not path.is_absolute():
            path = (json_path.parent / path).resolve()
        if not path.is_file():
            raise SystemExit(f"BibTeX file not found: {path}")
        resolved.append(path)
    return resolved


def get_entry_filters(resume: dict[str, Any]) -> tuple[set[str], set[str]]:
    publication = get_generated_publications_entry(resume) or {}
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


def load_bib_entries(bib_files: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for bibfile in bib_files:
        bibtex_source = bibfile.read_text(encoding="utf-8")
        entry_types = extract_entry_types(bibtex_source)
        db = bibtexparser.loads(normalize_bibtex_for_parser(bibtex_source))
        for entry in db.entries:
            entry_key = str(entry.get("ID") or entry.get("key") or "").strip()
            if entry_key:
                entry["key"] = entry_key
                entry["ID"] = entry_key
            original_type = entry_types.get(entry_key)
            if original_type:
                entry["ENTRYTYPE"] = original_type
            raw_keywords = str(entry.get("keywords", ""))
            entry["_keywords"] = {
                keyword.strip().lower()
                for keyword in raw_keywords.split(",")
                if keyword.strip()
            }
            year = entry.get("year")
            try:
                entry["year"] = int(year)
            except Exception:
                entry["year"] = 0
            entry["authors"] = str(entry.get("author", "")).replace(" and ", ", ")
            for field in FIELDS_TO_CLEAN:
                if field in entry:
                    entry[field] = latex_to_html(str(entry[field]))
            entries.append(entry)
    return sorted(entries, key=lambda e: e.get("year", 0), reverse=True)


def filter_entries(entries: list[dict[str, Any]], selected_keys: set[str], selected_keywords: set[str]) -> list[dict[str, Any]]:
    if not selected_keys and not selected_keywords:
        return entries

    filtered: list[dict[str, Any]] = []
    for entry in entries:
        entry_key = str(entry.get("key") or entry.get("ID") or "").strip()
        keywords = entry.get("_keywords", set())
        include = False
        if entry_key and entry_key in selected_keys:
            include = True
        if selected_keywords and isinstance(keywords, set) and keywords.intersection(selected_keywords):
            include = True
        if include:
            filtered.append(entry)
    return filtered


def update_publications(resume: dict[str, Any], generated_entry: dict[str, Any] | None, selected_entries: list[dict[str, Any]]) -> dict[str, Any]:
    generated_publications = [entry_to_jsonresume_publication(entry) for entry in selected_entries]
    publications = []
    if generated_entry is not None:
        publications.append(generated_entry)
    publications.extend(generated_publications)
    resume["publications"] = publications
    return resume


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace inline publications in a JSON Resume file from selected BibTeX entries."
    )
    parser.add_argument("--json", required=True, help="Path to JSON Resume file to update.")
    parser.add_argument(
        "--bib",
        action="append",
        default=[],
        help="BibTeX input (repeatable). If omitted, uses bibfiles from the generated-publications entry.",
    )
    args = parser.parse_args()

    json_path = Path(args.json).resolve()
    if not json_path.is_file():
        raise SystemExit(f"JSON file not found: {json_path}")

    resume = load_resume(json_path)
    generated_entry = get_generated_publications_entry(resume)
    bib_files = resolve_bib_files(args.bib, resume, json_path)
    selected_keys, selected_keywords = get_entry_filters(resume)
    entries = load_bib_entries(bib_files)
    selected_entries = filter_entries(entries, selected_keys, selected_keywords)

    updated = update_publications(resume, generated_entry, selected_entries)
    json_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Updated inline publications: {len(selected_entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
