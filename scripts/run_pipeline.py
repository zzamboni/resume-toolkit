#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_PUB_SECTIONS = [
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

DEFAULT_PUB_SECTION_TITLES = {
    "book": "Books",
    "editorial": "Editorial Activities",
    "thesis": "Theses",
    "refereed": "Refereed Papers",
    "techreport": "Tech Reports",
    "presentations": "Presentations at Conferences and Workshops",
    "invited": "Invited Talks and Articles",
    "patent": "Patents",
    "other": "Other Publications",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scripts/run_pipeline.py",
        description=(
            "Build the resume pipeline from a JSON Resume file and optional BibTeX sources."
        ),
    )
    parser.add_argument(
        "--json",
        required=True,
        help="JSON Resume input (relative to working dir or absolute path)",
    )
    parser.add_argument(
        "--bib",
        action="append",
        default=[],
        help=(
            "BibTeX input (repeatable). If omitted, uses bibfiles from the "
            "generated-publications entry in the JSON resume"
        ),
    )
    parser.add_argument(
        "--out",
        help="Output base directory (relative to working dir or absolute path)",
    )
    parser.add_argument(
        "--pubs-url",
        default="",
        help="Online publications URL used in generated publications PDF footer",
    )
    parser.add_argument(
        "--no-fetch-logos",
        action="store_true",
        help="Disable automatic logo fetching when no source logo directory is found",
    )
    return parser.parse_args()


def resolve_path(p: str, workdir: Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return workdir / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def calc_hash(*entries: str) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        kind, value = entry.split(":", 1)
        if kind == "STR":
            digest.update(b"STR\n")
            digest.update(value.encode("utf-8"))
            digest.update(b"\n")
        elif kind == "FILE":
            path = Path(value)
            if path.is_file():
                digest.update(b"FILE\n")
                digest.update(str(path).encode("utf-8"))
                digest.update(b"\n")
                digest.update(sha256_file(path).encode("ascii"))
                digest.update(b"\n")
            else:
                digest.update(b"MISSING_FILE\n")
                digest.update(str(path).encode("utf-8"))
                digest.update(b"\n")
        elif kind == "DIR":
            path = Path(value)
            if path.is_dir():
                digest.update(b"DIR\n")
                digest.update(str(path).encode("utf-8"))
                digest.update(b"\n")
                for child in sorted(p for p in path.rglob("*") if p.is_file()):
                    digest.update(b"PATH\n")
                    digest.update(str(child).encode("utf-8"))
                    digest.update(b"\n")
                    digest.update(sha256_file(child).encode("ascii"))
                    digest.update(b"\n")
            else:
                digest.update(b"MISSING_DIR\n")
                digest.update(str(path).encode("utf-8"))
                digest.update(b"\n")
        else:
            raise ValueError(f"Unsupported hash entry type: {kind}")
    return digest.hexdigest()


def needs_rebuild(out_file: Path, stamp_file: Path, new_hash: str) -> bool:
    if not out_file.is_file() or not stamp_file.is_file():
        return True
    return stamp_file.read_text(encoding="utf-8").strip() != new_hash


def mark_built(stamp_file: Path, new_hash: str) -> None:
    stamp_file.write_text(f"{new_hash}\n", encoding="utf-8")


def esc_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "#": r"\#",
        "$": r"\$",
        "%": r"\%",
        "&": r"\&",
        "_": r"\_",
        "^": r"\^{}",
        "~": r"\~{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def normalize_resume(src: Path, dst: Path) -> dict:
    data = json.loads(src.read_text(encoding="utf-8"))
    resume_stem = src.stem
    publications_stem = f"{resume_stem}-pubs"

    publications = data.get("publications")
    if isinstance(publications, list):
        bib_entries = [
            pub for pub in publications if isinstance(pub, dict) and "bibfiles" in pub
        ]
        if len(bib_entries) > 1:
            raise SystemExit(
                "Multiple publications entries define bibfiles; only one "
                "generated-publications entry is allowed"
            )
        if bib_entries:
            entry = bib_entries[0]
            if not isinstance(entry.get("name"), str) or not entry.get("name", "").strip():
                entry["name"] = "Full list online"
            if not isinstance(entry.get("url"), str) or not entry.get("url", "").strip():
                entry["url"] = "publications/"

    theme_options = data.get("meta", {}).get("themeOptions", {})
    if isinstance(theme_options, dict):
        links = theme_options.get("links")
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue
                url = link.get("url")
                if isinstance(url, str):
                    link["url"] = (
                        url.replace("<resume>", resume_stem)
                        .replace("<publications>", publications_stem)
                    )

    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def publications_options(data: dict) -> dict:
    options = data.get("meta", {}).get("publicationsOptions", {})
    return options if isinstance(options, dict) else {}


def is_remote_reference(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "data"}


def prepare_local_profile_image(
    data: dict,
    normalized_json: Path,
    json_dir: Path,
    out_vita: Path,
) -> dict:
    basics = data.get("basics")
    if not isinstance(basics, dict):
        return data

    image_value = basics.get("image")
    if not isinstance(image_value, str) or not image_value.strip():
        return data
    if is_remote_reference(image_value):
        return data

    source_path = Path(image_value)
    if not source_path.is_absolute():
        source_path = (json_dir / source_path).resolve()
    if not source_path.is_file():
        return data

    dest_dir = out_vita / "assets" / "profile"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / source_path.name
    shutil.copy2(source_path, dest_path)

    basics["image"] = f"assets/profile/{source_path.name}"
    normalized_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def resolve_sectioning_config(publications_options_value: dict) -> tuple[str, list[str], dict[str, str]]:
    pub_sections_value = publications_options_value.get("pubSections", False)
    if pub_sections_value is False or pub_sections_value is None:
        mode = "none"
        sections: list[str] = []
    elif pub_sections_value is True:
        mode = "default"
        sections = list(DEFAULT_PUB_SECTIONS)
    elif isinstance(pub_sections_value, list):
        sections = [s for s in pub_sections_value if isinstance(s, str) and s]
        mode = "custom" if sections else "none"
    else:
        mode = "none"
        sections = []

    titles = dict(DEFAULT_PUB_SECTION_TITLES)
    override_titles = publications_options_value.get("pubSectionTitles", {})
    if isinstance(override_titles, dict):
        for key, value in override_titles.items():
            if isinstance(key, str) and isinstance(value, str):
                titles[key] = value
    return mode, sections, titles


def resolve_bib_files(
    cli_bibs: list[str],
    data: dict,
    json_dir: Path,
    workdir: Path,
) -> list[Path]:
    bib_files = list(cli_bibs)
    using_json_bibfiles = False
    if not bib_files:
        publications = data.get("publications")
        raw_bibs: list[str] = []
        if isinstance(publications, list):
            for publication in publications:
                if not isinstance(publication, dict) or "bibfiles" not in publication:
                    continue
                bib_list = publication.get("bibfiles")
                if isinstance(bib_list, list):
                    for item in bib_list:
                        if isinstance(item, str) and item:
                            raw_bibs.append(item)
        bib_files = sorted(set(raw_bibs))
        if bib_files:
            using_json_bibfiles = True

    resolved: list[Path] = []
    for bib in bib_files:
        path = Path(bib)
        if using_json_bibfiles and not path.is_absolute():
            path = json_dir / path
        else:
            path = resolve_path(bib, workdir)
        if not path.is_file():
            raise SystemExit(f"BibTeX file not found: {path}")
        resolved.append(path)
    return resolved


def build_publications_links(data: dict, pdf_name: str, bib_name: str) -> str:
    default_links = [
        {"name": "PDF", "url": pdf_name, "icon": "file-pdf"},
        {"name": "BibTeX", "url": bib_name, "icon": "tex"},
    ]
    links = publications_options(data).get("links")
    if links is None:
        result = default_links
    elif isinstance(links, list):
        result = []
        for item in links:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            url = item.get("url")
            icon = item.get("icon")
            if not all(isinstance(v, str) and v.strip() for v in (name, url, icon)):
                continue
            replaced_url = (
                url.replace("<publications>.pdf", pdf_name)
                .replace("<publications>.bib", bib_name)
                .replace("<publications>", Path(pdf_name).stem)
                .replace("<resume>", Path(pdf_name).stem.removesuffix("-pubs"))
            )
            result.append(
                {
                    "name": name.strip(),
                    "url": replaced_url.strip(),
                    "icon": icon.strip(),
                }
            )
    else:
        result = default_links
    return json.dumps(result, separators=(",", ":"))


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def ensure_profile_assets(toolkit_root: Path, out_vita: Path) -> None:
    src_dir = toolkit_root / "assets" / "profile"
    dst_dir = out_vita / "assets" / "profile"
    dst_dir.mkdir(parents=True, exist_ok=True)
    if not src_dir.is_dir():
        return
    for child in src_dir.iterdir():
        target = dst_dir / child.name
        if child.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def inject_reload_if_needed(toolkit_root: Path, html_path: Path) -> None:
    if os.environ.get("DEV_RELOAD", "0") != "1":
        return
    if not html_path.is_file():
        return
    if "__reload" in html_path.read_text(encoding="utf-8"):
        return
    run_command([sys.executable, str(toolkit_root / "scripts" / "inject_dev_reload.py"), str(html_path)])


def ensure_logo_assets(
    toolkit_root: Path,
    resume_json: Path,
    assets_source_dir: Path,
    workdir: Path,
    no_fetch_logos: bool,
) -> Path:
    logos_dir = assets_source_dir / "logos"
    if logos_dir.is_dir():
        return assets_source_dir
    if no_fetch_logos:
        return assets_source_dir

    token = os.environ.get("LOGODEV_TOKEN", "").strip()
    if not token:
        print(
            f"Warning: logo assets directory not found at {logos_dir} and LOGODEV_TOKEN is not set; "
            "skipping automatic logo download.",
            file=sys.stderr,
        )
        return assets_source_dir

    fetch_assets_dir = assets_source_dir
    if assets_source_dir == toolkit_root / "assets":
        fetch_assets_dir = workdir / "assets"

    print(f"→ Fetching logos into {fetch_assets_dir / 'logos'}")
    run_command(
        [
            sys.executable,
            str(toolkit_root / "scripts" / "fetch_company_logos.py"),
            str(resume_json),
            "--logos-dir",
            str(fetch_assets_dir / "logos"),
            "--token",
            token,
        ]
    )
    return fetch_assets_dir


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    toolkit_root = Path(os.environ.get("VITA_TOOLKIT_ROOT", script_dir.parent)).resolve()
    workdir = Path(os.environ.get("VITA_WORKDIR", os.getcwd())).resolve()
    assets_source_dir_env = os.environ.get("VITA_ASSETS_DIR")

    json_file = resolve_path(args.json, workdir).resolve()
    output_dir_value = args.out or f"build/{Path(args.json).stem}"
    out_base = resolve_path(output_dir_value, workdir).resolve()

    if not json_file.is_file():
        raise SystemExit(f"JSON file not found: {json_file}")

    json_name = json_file.name
    json_stem = json_file.stem
    json_dir = json_file.parent.resolve()
    if assets_source_dir_env:
        assets_source_dir = Path(assets_source_dir_env).resolve()
    else:
        workdir_assets = (workdir / "assets").resolve()
        json_local_assets = (json_dir / "assets").resolve()
        if workdir_assets.is_dir():
            assets_source_dir = workdir_assets
        elif json_local_assets.is_dir():
            assets_source_dir = json_local_assets
        else:
            assets_source_dir = toolkit_root / "assets"
    assets_source_dir = ensure_logo_assets(
        toolkit_root,
        json_file,
        assets_source_dir,
        workdir,
        args.no_fetch_logos,
    )

    cv_typ_name = f"{json_stem}.typ"
    cv_pdf_name = f"{json_stem}.pdf"
    pubs_base_name = f"{json_stem}-pubs"
    pubs_bib_name = f"{pubs_base_name}.bib"
    pubs_typ_name = f"{pubs_base_name}.typ"
    pubs_pdf_name = f"{pubs_base_name}.pdf"

    state_dir = out_base / ".pipeline-state" / json_stem
    state_dir.mkdir(parents=True, exist_ok=True)
    normalized_json = state_dir / f"{json_stem}.normalized.json"
    data = normalize_resume(json_file, normalized_json)
    resolve_sectioning_config(publications_options(data))

    bib_files = resolve_bib_files(args.bib, data, json_dir, workdir)
    resume_name = esc_latex(str(data.get("basics", {}).get("name", "Publications")))

    out_vita = out_base / "vita"
    out_pubs = out_vita / "publications"
    inline_bib_name = f"{json_stem}-vita.bib"
    inline_bib_path = out_vita / inline_bib_name
    inline_bib_for_typst = ""
    inline_value = publications_options(data).get("inline_in_pdf")
    inline_publications_requested = inline_value is True or isinstance(inline_value, dict)
    out_vita.mkdir(parents=True, exist_ok=True)
    data = prepare_local_profile_image(data, normalized_json, json_dir, out_vita)

    ensure_profile_assets(toolkit_root, out_vita)

    profile_image_value = data.get("basics", {}).get("image") or ""
    profile_image = Path(profile_image_value) if profile_image_value else None

    cv_html = out_vita / "index.html"
    cv_html_hash = calc_hash(
        f"FILE:{normalized_json}",
        f"FILE:{profile_image}" if profile_image else "FILE:",
        f"FILE:{toolkit_root / 'scripts' / 'render_cv.sh'}",
        f"STR:cv_html_target={cv_html}",
    )
    cv_html_stamp = state_dir / "cv-html.sha"
    if needs_rebuild(cv_html, cv_html_stamp, cv_html_hash):
        print("→ Building CV HTML")
        run_command(
            [
                str(toolkit_root / "scripts" / "render_cv.sh"),
                "",
                str(normalized_json),
                str(cv_html),
            ]
        )
        mark_built(cv_html_stamp, cv_html_hash)
    else:
        print("→ CV HTML up to date")
    inject_reload_if_needed(toolkit_root, cv_html)

    if bib_files:
        out_pubs.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as pubs_tmp_dir_raw:
            pubs_tmp_dir = Path(pubs_tmp_dir_raw)
            sorted_bibs = sorted(bib_files)
            for bib in sorted_bibs:
                shutil.copy2(bib, pubs_tmp_dir / bib.name)

            pubs_links_json = build_publications_links(data, pubs_pdf_name, pubs_bib_name)
            pubs_html = out_pubs / "index.html"
            agg_bib = out_pubs / pubs_bib_name

            pubs_html_hash_args = [
                f"FILE:{toolkit_root / 'scripts' / 'build_publications.py'}",
                f"FILE:{toolkit_root / 'templates' / 'publications.html.j2'}",
                f"FILE:{normalized_json}",
                f"STR:resume_name={data.get('basics', {}).get('name', '')}",
                f"STR:pubs_links={pubs_links_json}",
                f"STR:pubs_bib_name={pubs_bib_name}",
            ]
            pubs_html_hash_args.extend(f"FILE:{bib}" for bib in sorted_bibs)
            pubs_html_hash = calc_hash(*pubs_html_hash_args)
            pubs_html_stamp = state_dir / "pubs-html.sha"
            if needs_rebuild(pubs_html, pubs_html_stamp, pubs_html_hash) or needs_rebuild(
                agg_bib, pubs_html_stamp, pubs_html_hash
            ):
                print("→ Building publications HTML + BibTeX")
                env = os.environ.copy()
                env.update(
                    {
                        "PUBS_BIB_DIR": str(pubs_tmp_dir),
                        "PUBS_HTML": str(pubs_html),
                        "PUBS_OUT_DIR": str(out_pubs),
                        "PUBS_BIB_FILENAME": pubs_bib_name,
                        "PUBS_RESUME_JSON": str(normalized_json),
                        "PUBS_LINKS": pubs_links_json,
                    }
                )
                run_command(
                    [sys.executable, "scripts/build_publications.py"],
                    cwd=toolkit_root,
                    env=env,
                )
                inject_reload_if_needed(toolkit_root, pubs_html)
                mark_built(pubs_html_stamp, pubs_html_hash)
            else:
                print("→ Publications HTML + BibTeX up to date")

            if not agg_bib.is_file():
                raise SystemExit(f"Aggregated bib not found: {agg_bib}")

            if inline_publications_requested:
                shutil.copy2(agg_bib, inline_bib_path)
                inline_bib_for_typst = inline_bib_name

            pubs_typ = out_pubs / pubs_typ_name
            run_command(
                [
                    sys.executable,
                    str(toolkit_root / "scripts" / "render_typst_publications.py"),
                    str(normalized_json),
                    pubs_bib_name,
                    str(pubs_typ),
                    args.pubs_url,
                ]
            )

            pubs_pdf = out_pubs / pubs_pdf_name
            pubs_pdf_hash = calc_hash(
                f"FILE:{toolkit_root / 'scripts' / 'run_pipeline.py'}",
                f"FILE:{toolkit_root / 'scripts' / 'render_typst_publications.py'}",
                f"FILE:{normalized_json}",
                f"FILE:{agg_bib}",
                f"STR:resume_name={resume_name}",
                f"STR:pubs_typ_name={pubs_typ_name}",
                f"STR:pubs_pdf_name={pubs_pdf_name}",
                f"STR:resume_name={resume_name}",
                f"STR:pubs_url={args.pubs_url}",
            )
            pubs_pdf_stamp = state_dir / "pubs-pdf.sha"
            if needs_rebuild(pubs_pdf, pubs_pdf_stamp, pubs_pdf_hash):
                print("→ Building publications PDF")
                run_command(["typst", "compile", pubs_typ_name, pubs_pdf_name], cwd=out_pubs)
                mark_built(pubs_pdf_stamp, pubs_pdf_hash)
            else:
                print("→ Publications PDF up to date")
    else:
        shutil.rmtree(out_pubs, ignore_errors=True)
        inline_bib_path.unlink(missing_ok=True)

    cv_typ = out_vita / cv_typ_name
    cv_pdf = out_vita / cv_pdf_name
    cv_typ_hash_args = [
        f"FILE:{normalized_json}",
        f"FILE:{toolkit_root / 'scripts' / 'render_typst_cv.py'}",
        f"DIR:{out_vita / 'assets' / 'profile'}",
        f"DIR:{toolkit_root / 'assets' / 'profile'}",
        f"DIR:{assets_source_dir / 'logos'}",
        f"STR:cv_typ_target={cv_typ}",
        f"STR:inline_publications_requested={str(inline_publications_requested).lower()}",
        f"STR:inline_bib_for_typst={inline_bib_for_typst}",
    ]
    if inline_bib_for_typst:
        cv_typ_hash_args.append(f"FILE:{inline_bib_path}")
    cv_typ_hash = calc_hash(*cv_typ_hash_args)
    cv_typ_stamp = state_dir / "cv-typ.sha"
    if needs_rebuild(cv_typ, cv_typ_stamp, cv_typ_hash):
        print("→ Building Typst source")
        env = os.environ.copy()
        env.update(
            {
                "VITA_ASSETS_DIR": str(assets_source_dir),
                "VITA_INLINE_PUBLICATIONS_BIB": inline_bib_for_typst,
            }
        )
        run_command(
            [
                sys.executable,
                str(toolkit_root / "scripts" / "render_typst_cv.py"),
                str(normalized_json),
                str(cv_typ),
            ],
            env=env,
        )
        mark_built(cv_typ_stamp, cv_typ_hash)
    else:
        print("→ Typst source up to date")

    cv_pdf_hash = calc_hash(
        f"FILE:{cv_typ}",
        f"DIR:{out_vita / 'assets' / 'profile'}",
        f"DIR:{out_vita / 'assets' / 'logos'}",
        f"STR:cv_pdf_target={cv_pdf}",
    )
    cv_pdf_stamp = state_dir / "cv-pdf.sha"
    if needs_rebuild(cv_pdf, cv_pdf_stamp, cv_pdf_hash):
        print("→ Building CV PDF")
        run_command(["typst", "compile", str(cv_typ), str(cv_pdf)])
        mark_built(cv_pdf_stamp, cv_pdf_hash)
    else:
        print("→ CV PDF up to date")

    print(f"Done. Output in: {out_vita}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
