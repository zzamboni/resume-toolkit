#!/usr/bin/env python3

import json
import sys
from pathlib import Path

from render_typst_cv import (
    escape_typst,
    format_footer_url,
    generate_metadata,
    get_pdf_theme_url,
    get_standalone_publications_label,
    get_section_style_options,
    render_pergamon_bibliography,
    render_pergamon_setup,
    render_section_heading,
)


def generate_typst_publications(
    resume_data: dict,
    bib_filename: str,
    bib_source_path: Path | None = None,
    pubs_url: str = "",
) -> str:
    resume_name = str(resume_data.get("basics", {}).get("name", "Publications")).strip() or "Publications"
    publications_label = get_standalone_publications_label(resume_data)
    pubs_url = pubs_url or get_pdf_theme_url(resume_data, "pubs_url")
    pubs_url_resolved, pubs_url_display = format_footer_url(pubs_url) if pubs_url else ("", "")

    style_config = {
        "ref-style": "ieee",
        "ref-full": True
    }

    output = """// Publications list generated from BibTeX
// Using brilliant-cv template for document layout

#import "@preview/brilliant-cv:3.1.2": *

/// Add the title of a section
///
/// NOTE: If the language is non-Latin, the title highlight will not be sliced.
///
/// This is a copy of the function from the brilliant-cv package, but making it sticky
/// to prevent orphan headings.
///
/// - title (str): The title of the section.
/// - highlighted (bool): Whether the first n letters will be highlighted in accent color.
/// - letters (int): The number of first letters of the title to highlight.
/// - metadata (array): (optional) the metadata read from the TOML file.
/// - awesome-colors (array): (optional) the awesome colors of the CV.
/// -> content
#let cv-section(
  title,
  highlighted: true,
  letters: 3,
  metadata: none,
  awesome-colors: none,
  awesomeColors: _awesome-colors,
) = context {
  let metadata = if metadata != none { metadata } else { cv-metadata.get() }
  let awesome-colors = if awesome-colors != none {
    awesome-colors
  } else {
    awesomeColors
  }

  let lang = metadata.language
  let non-latin = _is-non-latin(lang)
  let before-section-skip = _get-layout-value(metadata, "before_section_skip", 1pt)
  let accent-color = _set-accent-color(awesome-colors, metadata)
  let highlighted-text = title.slice(0, letters)
  let normal-text = title.slice(letters)

  let section-title-style(str, color: black) = {
    text(size: 16pt, weight: "bold", fill: color, str)
  }

  v(before-section-skip)
  block(
    sticky: true,
    [#if non-latin {
      section-title-style(title, color: accent-color)
    } else {
      if highlighted {
        section-title-style(highlighted-text, color: accent-color)
        section-title-style(normal-text, color: black)
      } else {
        section-title-style(title, color: black)
      }
    }
    #h(2pt)
    #box(width: 1fr, line(stroke: 0.9pt, length: 100%))]
  )
}

"""
    output += render_pergamon_setup(bib_filename, style_config)
    output += generate_metadata(resume_data)
    output += "\n"
    output += "#let metadata_pub = metadata + (\n"
    output += "  personal: metadata.personal + (\n"
    output += "    info: (),\n"
    output += "  ),\n"
    output += "  layout: metadata.layout + (\n"
    output += "    header: metadata.layout.header + (\n"
    output += "      display_profile_photo: false,\n"
    output += "    ),\n"
    output += "  ),\n"
    output += "  lang: metadata.lang + (\n"
    output += "    en: metadata.lang.en + (\n"
    output += f'      cv_footer: [ {escape_typst(publications_label)} - #datetime.today().display()'
    if pubs_url:
        output += f' #"\\n" #link("{escape_typst(pubs_url)}")[{escape_typst(pubs_url_display)}]'
    output += " ],\n"
    output += '      header_quote: "",\n'
    output += "    ),\n"
    output += "  ),\n"
    output += ")\n\n"
    output += "#show: cv.with(\n"
    output += "  metadata_pub,\n"
    output += ")\n\n"
    output += render_section_heading(escape_typst(publications_label), get_section_style_options(resume_data))
    output += render_pergamon_bibliography(
        resume_data,
        style_config,
        include_titles=False,
        bib_file_path=bib_source_path,
    )
    return output


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: render_typst_publications.py <jsonresume-file> <bib-filename> [output-file] [pubs-url]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    bib_filename = sys.argv[2]
    output_file = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    pubs_url = sys.argv[4] if len(sys.argv) > 4 else ""

    if not input_file.exists():
        print(f"Error: Input file {input_file} not found")
        sys.exit(1)

    with input_file.open("r", encoding="utf-8") as f:
        resume_data = json.load(f)

    bib_source_path = Path(bib_filename)
    if not bib_source_path.is_absolute() and output_file is not None:
        bib_source_path = output_file.parent / bib_source_path

    typst_content = generate_typst_publications(
        resume_data,
        bib_filename,
        bib_source_path=bib_source_path,
        pubs_url=pubs_url,
    )

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(typst_content, encoding="utf-8")
    else:
        print(typst_content)


if __name__ == "__main__":
    main()
