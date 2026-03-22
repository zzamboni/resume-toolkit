#!/usr/bin/env python3
"""
Convert JSONResume format to Typst CV using brilliant-cv template.

This script reads a JSONResume JSON file and generates a CV using the
brilliant-cv Typst template.

Generic JSON Resume to Typst converter.

(c) 2026 Diego Zamboni
"""

import copy
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

def convert_markdown_to_typst(text: str) -> str:
    """Convert Markdown formatting to Typst markup."""
    if not text:
        return ""

    def replace_link(match):
        link_text = match.group(1)
        url = match.group(2)
        link_text_processed = convert_markdown_inline(link_text)
        return f'#link("{url}")[{link_text_processed}]'

    text = re.sub(r'\[(.+?)\]\(([^)]+)\)', replace_link, text)
    text = convert_markdown_inline(text)
    return text


def convert_markdown_inline(text: str) -> str:
    """Convert inline Markdown formatting (bold, italic) to Typst."""
    if not text:
        return ""
    text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
    text = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'_\1_', text)
    return text


def escape_typst(text: str) -> str:
    """Escape special Typst characters."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace("#", "\\#")
    text = text.replace("<", "\\<")
    text = text.replace(">", "\\>")
    text = text.replace("@", "\\@")
    text = text.replace('"', '\\"')
    return text


def process_text(text: str) -> str:
    """Process text: convert markdown to Typst."""
    if not text:
        return ""
    return convert_markdown_to_typst(text)


PROJECT_SECTION_PREFIX = "projects:"

DEFAULT_SECTIONS = [
    "work",
    "volunteer",
    "education",
    "projects",
    "awards",
    "certificates",
    "publications",
    "skills",
    "languages",
    "interests",
    "references",
]

DEFAULT_PUBLICATION_SECTIONS = [
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

DEFAULT_PUBLICATION_SECTION_TITLES = {
    "book": "Books",
    "editorial": "Editorial Activities",
    "thesis": "Theses",
    "refereed": "Refereed Papers",
    "techreport": "Technical Reports",
    "presentations": "Presentations at Conferences and Workshops",
    "invited": "Invited Talks and Articles",
    "patent": "Patents",
    "other": "Other Publications",
}


def normalize_label(label: str) -> str:
    if not label:
        return label
    return label[0].upper() + label[1:]


def get_theme_options(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    return resume_data.get("meta", {}).get("themeOptions", {}) if resume_data else {}


DEFAULT_PDF_THEME_LAYOUT: Dict[str, Any] = {
    "awesome_color": "skyblue",
    "before_section_skip": "1pt",
    "before_entry_skip": "1pt",
    "before_entry_description_skip": "1pt",
    "paper_size": "a4",
    "fonts": {
        "regular_fonts": ["Source Sans 3"],
        "header_font": "Roboto",
    },
    "header": {
        "header_align": "left",
        "display_profile_photo": True,
        "profile_photo_radius": "50%",
        "info_font_size": "10pt",
    },
    "entry": {
        "display_entry_society_first": True,
        "display_logo": True,
    },
    "footer": {
        "display_page_counter": False,
        "display_footer": True,
    },
}


def get_pdf_theme_options(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    meta = resume_data.get("meta", {}) if resume_data else {}
    if not isinstance(meta, dict):
        return {}
    options = meta.get("pdfthemeOptions", {})
    return options if isinstance(options, dict) else {}


def get_pdf_theme_layout_overrides(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    layout = get_pdf_theme_options(resume_data).get("layout", {})
    if not isinstance(layout, dict):
        return {}
    return layout


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def get_section_style_options(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    layout = get_pdf_theme_layout_overrides(resume_data)
    options: Dict[str, Any] = {}
    if "highlighted" in layout:
        options["highlighted"] = coerce_bool(layout["highlighted"])
    if "letters" in layout and isinstance(layout["letters"], (int, float, str)):
        options["letters"] = layout["letters"]
    return options


def show_summary_title(resume_data: Dict[str, Any]) -> bool:
    return coerce_bool(get_pdf_theme_layout_overrides(resume_data).get("summary_title", False))


def deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def typst_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{escape_typst(value)}"'
    if isinstance(value, list):
        items = ", ".join(typst_value(item) for item in value)
        return f"({items},)" if items else "()"
    if isinstance(value, dict):
        items = ",\n".join(f"      {key}: {typst_value(val)}" for key, val in value.items())
        if not items:
            return "()"
        return "(\n" + items + "\n    )"
    return f'"{escape_typst(str(value))}"'


def render_section_heading(label: str, section_style: Optional[Dict[str, Any]] = None) -> str:
    args = [f'"{label}"']
    if section_style:
        if "highlighted" in section_style:
            args.append(f'highlighted: {"true" if section_style["highlighted"] else "false"}')
        if "letters" in section_style:
            args.append(f'letters: {section_style["letters"]}')
    return f'#cv-section({", ".join(args)})\n\n'


def ordered_project_groups(projects: List[Dict[str, Any]]) -> List[tuple]:
    groups = []
    by_key: Dict[Any, List[Dict[str, Any]]] = {}
    for project in projects:
        key = project.get("type")
        if key not in by_key:
            by_key[key] = []
            groups.append((key, by_key[key]))
        by_key[key].append(project)
    return groups


def format_date(date_str: Optional[str]) -> str:
    """Format date string for display."""
    if not date_str:
        return "Present"
    try:
        date = datetime.fromisoformat(date_str)
        return date.strftime("%b %Y")
    except:
        return date_str


def format_date_range(start: Optional[str], end: Optional[str]) -> str:
    """Format date range."""
    start_fmt = format_date(start)
    end_fmt = format_date(end) if end else "Present"
    if start_fmt == end_fmt:
        return f"{start_fmt}"
    else:
        return f"{start_fmt} - {end_fmt}"


def download_image(url: str, base_output_dir: Path, output_dir: Path) -> Optional[str]:
    """Download an image from URL and return local path."""
    if not url:
        return None

    try:
        url_parts = url.split("/")
        if "images.credly.com" in url:
            unique_id = url_parts[-2] if len(url_parts) >= 2 else url_parts[-1]
            filename = f"{unique_id}.png"
        else:
            filename = url_parts[-1]
            if not filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                filename += '.png'

        output_dir_full = base_output_dir / output_dir
        output_dir_full.mkdir(parents=True, exist_ok=True)
        local_path = output_dir_full / filename

        if not local_path.exists():
            print(f"Downloading {url}...")
            urllib.request.urlretrieve(url, local_path)

        return str(output_dir / filename)
    except Exception as e:
        print(f"Warning: Failed to download {url}: {e}")
        return None


def resolve_image_reference(image_ref: str, base_output_dir: Path, output_dir: Path) -> Optional[str]:
    """Resolve a local image path or download a remote one."""
    if not image_ref:
        return None

    parsed = urllib.parse.urlparse(image_ref)
    if parsed.scheme in ("http", "https", "data"):
        return download_image(image_ref, base_output_dir, output_dir)

    local_path = base_output_dir / image_ref
    if local_path.exists():
        return image_ref

    return download_image(image_ref, base_output_dir, output_dir)


def find_company_logo(name: str, base_output_dir: Path, assets_dir: Path,
                      source_assets_dir: Path) -> Optional[str]:
    """Find a local logo and ensure it exists under the output assets dir."""
    if not name:
        return None

    source_logos_dir = source_assets_dir / "logos"
    output_logos_dir = base_output_dir / assets_dir / "logos"
    for ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"):
        filename = f"{name}{ext}"
        candidate = source_logos_dir / filename
        if candidate.exists():
            output_logos_dir.mkdir(parents=True, exist_ok=True)
            dest = output_logos_dir / filename
            if dest.resolve() != candidate.resolve():
                shutil.copy2(candidate, dest)
            return str(assets_dir / "logos" / filename)
    return None

def _personal_info_line(label, value):
    return f'      {label}: "{value}"'

def _personal_info_custom(name, icon, text, url=None):
    return f'''      custom-{name}: (
        awesomeIcon: "{icon or name}",
        text: "{text}"''' + \
        (f',\n        link: "{url}"' if url else "") + "\n      )"


def normalize_location(value: Any) -> str:
    """Convert JSON Resume location values into a compact display string."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""

    parts = []
    address = value.get("address")
    city = value.get("city")
    region = value.get("region")
    postal_code = value.get("postalCode")
    country = value.get("country")
    country_code = value.get("countryCode")

    for part in (address, city, region, postal_code, country, country_code):
        if isinstance(part, str) and part.strip():
            if part not in parts:
                parts.append(part.strip())
    return ", ".join(parts)


def typst_list(items: List[str]) -> str:
    values = [f'"{escape_typst(item)}"' for item in items if isinstance(item, str) and item]
    if not values:
        return "()"
    return "(" + ", ".join(values) + ",)"


def parse_skill_level(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        level = int(value)
        return level if 1 <= level <= 5 else None
    if not isinstance(value, str):
        return None
    match = re.search(r"([1-5])(?:\s*/\s*5)?", value.strip())
    if not match:
        return None
    return int(match.group(1))

def generate_metadata(resume_data: Dict[str, Any]) -> str:
    """Generate brilliant-cv metadata dictionary."""
    basics = resume_data.get("basics", {})
    name = basics.get("name", "")
    name_parts = name.split()
    first_name = basics.get("first_name", name_parts[0] if (len(name_parts)>0) else "")
    last_name = basics.get("last_name", name_parts[1] if (len(name_parts)>1) else "")
    label = basics.get("label", "")
    email = basics.get("email", "")
    url = basics.get("url", "")
    phone = basics.get("phone", "")
    location = basics.get("location", {})

    location_text = normalize_location(location)

    # Build personal info for brilliant-cv
    personal_info = []
    if email:
        personal_info.append(_personal_info_line('email', email))
    if phone:
        personal_info.append(_personal_info_line('phone', escape_typst(phone)))
    if url:
        url_display = url.replace("https://", "").replace("http://", "")
        # personal_info.append(_personal_info_line('homepage', url_display))
        personal_info.append(_personal_info_custom('homepage', 'home', url_display, url))
    if location_text:
        personal_info.append(_personal_info_line('location', escape_typst(location_text)))

    # Add social profiles
    profiles = basics.get("profiles", [])
    for profile in profiles:
        network = profile.get("network", "").lower()
        username = profile.get("username", "")
        networkIcon = profile.get("networkIcon", None)
        url = profile.get("url", None)
        if username:
            if network in ["linkedin", "github"]:
                personal_info.append(_personal_info_line(network, username))
            else:
                personal_info.append(_personal_info_custom(network, networkIcon, username, url))
    personal_str = ",\n".join(personal_info)
    layout_overrides = dict(get_pdf_theme_layout_overrides(resume_data))
    layout_overrides.pop("highlighted", None)
    layout_overrides.pop("letters", None)
    pdf_theme_layout = deep_merge_dicts(DEFAULT_PDF_THEME_LAYOUT, layout_overrides)
    layout_str = typst_value(pdf_theme_layout)

    metadata = f'''#let metadata = (
  language: "en",
  name: "{escape_typst(name)}",
  tagline: "{escape_typst(label)}",

  personal: (
    first_name: "{escape_typst(first_name)}",
    last_name: "{escape_typst(last_name)}",
    info: (
{personal_str}
    )
  ),

  layout: {layout_str},

  inject: (
    inject_ai_prompt: false,
    inject_keywords: false,
    injected_keywords_list: []
  ),

  lang: (
    en: (
      education: "Education",
      professional: "Professional Experience",
      certificates: "Certifications",
      skills: "Skills",
      projects: "Projects",
      activities: "Professional Activities",
      languages: "Languages",
      date_in_present: "Present",
      cv_footer: [ Curriculum Vitae - #datetime.today().display() ],
      header_quote: "{escape_typst(label)}",
    ),
  ),
)
'''

    return metadata


def render_summary(basics: Dict[str, Any], label: str = "Summary",
                   show_title: bool = False,
                   section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render professional summary."""
    summary = basics.get("summary", "")
    if not summary:
        return ""

    paragraphs = [p.strip() for p in summary.split("\n\n") if p.strip()]

    output = render_section_heading(label, section_style) if show_title else ""
    for para in paragraphs:
        output += f"{process_text(para)}\n\n"

    return output


def render_experience(work: List[Dict[str, Any]], base_output_dir: Path, assets_dir: Path,
                      source_assets_dir: Path, label: str = "Work",
                      section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render work experience using brilliant-cv."""
    if not work:
        return ""

    output = render_section_heading(label, section_style)

    grouped_work: List[Dict[str, Any]] = []
    for job in work:
        company = job.get("name", "")
        if not grouped_work or grouped_work[-1]["company"] != company:
            grouped_work.append({"company": company, "jobs": []})
        grouped_work[-1]["jobs"].append(job)

    for group in grouped_work:
        jobs = group["jobs"]
        if len(jobs) == 1:
            job = jobs[0]
            company = job.get("name", "")
            position = job.get("position", "")
            start = job.get("startDate", "")
            end = job.get("endDate", "")
            location = normalize_location(job.get("location", ""))
            company_description = job.get("description", "")
            summary = job.get("summary", "")
            highlights = job.get("highlights", [])
            url = job.get("url", "")
            logo_path = find_company_logo(company, base_output_dir, assets_dir, source_assets_dir)

            date_range = format_date_range(start, end)

            # Build description
            desc_parts = []
            if company_description:
                desc_parts.append(process_text(company_description))
            if summary:
                desc_parts.append(process_text(summary))
            if highlights:
                for highlight in highlights:
                    desc_parts.append(f"- {process_text(highlight)}")

            description = "\n".join(desc_parts) if desc_parts else ""

            output += f'#cv-entry(\n'
            output += f'  title: [{escape_typst(position)}],\n'
            output += f'  society: ['
            if url:
                output += f'#link("{url}")[{escape_typst(company)}]'
            else:
                output += escape_typst(company)
            output += '],\n'
            output += f'  date: [{date_range}],\n'
            if logo_path:
                output += f'  logo: image("{logo_path}"),\n'
            if location:
                output += f'  location: [{escape_typst(location)}],\n'
            output += f'  description: [\n    {description}\n  ]\n'
            output += ')\n\n'
            continue

        company = group["company"]
        url = next((job.get("url", "") for job in jobs if job.get("url", "")), "")
        logo_path = find_company_logo(company, base_output_dir, assets_dir, source_assets_dir)
        locations = [
            normalize_location(job.get("location", ""))
            for job in jobs
            if normalize_location(job.get("location", ""))
        ]
        shared_location = locations[0] if locations else ""

        output += f'#cv-entry-start(\n'
        output += f'  society: ['
        if url:
            output += f'#link("{url}")[{escape_typst(company)}]'
        else:
            output += escape_typst(company)
        output += '],\n'
        if logo_path:
            output += f'  logo: image("{logo_path}"),\n'
        if shared_location:
            output += f'  location: [{escape_typst(shared_location)}],\n'
        output += ')\n#v(4pt)\n\n'

        for job in jobs:
            position = job.get("position", "")
            start = job.get("startDate", "")
            end = job.get("endDate", "")
            company_description = job.get("description", "")
            summary = job.get("summary", "")
            highlights = job.get("highlights", [])

            date_range = format_date_range(start, end)

            # Build description
            desc_parts = []
            if company_description:
                desc_parts.append(process_text(company_description))
            if summary:
                desc_parts.append(process_text(summary))
            if highlights:
                for highlight in highlights:
                    desc_parts.append(f"- {process_text(highlight)}")

            description = "\n".join(desc_parts) if desc_parts else ""

            output += f'#cv-entry-continued(\n'
            output += f'  title: [{escape_typst(position)}],\n'
            output += f'  date: [{date_range}],\n'
            output += f'  description: [\n    {description}\n  ]\n'
            output += ')\n\n'

    return output


def render_education(education: List[Dict[str, Any]], base_output_dir: Path, assets_dir: Path,
                     source_assets_dir: Path, label: str = "Education",
                     section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render education using brilliant-cv."""
    if not education:
        return ""

    output = render_section_heading(label, section_style)

    for edu in education:
        institution = edu.get("institution", "")
        area = edu.get("area", "")
        study_type = edu.get("studyType", "")
        start = edu.get("startDate", "")
        end = edu.get("endDate", "")
        location = normalize_location(edu.get("location", ""))
        summary = edu.get("summary", "")
        score = edu.get("score", "")
        courses = edu.get("courses", [])
        url = edu.get("url", "")
        logo_path = find_company_logo(institution, base_output_dir, assets_dir, source_assets_dir)

        date_range = format_date_range(start, end)

        title = study_type
        if area:
            title += f" in {area}"

        desc_items = []
        if isinstance(summary, str) and summary:
            desc_items.append(process_text(summary))
        elif isinstance(summary, list):
            for item in summary:
                if isinstance(item, str) and item:
                    desc_items.append(process_text(item))
        if courses:
            rendered_courses = " #h-bar() ".join(
                escape_typst(course) for course in courses if isinstance(course, str) and course
            )
            if rendered_courses:
                desc_items.append(f"Course: {rendered_courses}")
        if score:
            score_label = "GPA" if "/" in str(score) else "Score"
            desc_items.append(f"{score_label}: {escape_typst(str(score))}")

        output += f'#cv-entry(\n'
        output += f'  title: [{escape_typst(title)}],\n'
        output += f'  society: ['
        if url:
            output += f'#link("{url}")[{escape_typst(institution)}]'
        else:
            output += escape_typst(institution)
        output += '],\n'
        output += f'  date: [{date_range}],\n'
        if logo_path:
            output += f'  logo: image("{logo_path}"),\n'
        if location:
            output += f'  location: [{escape_typst(location)}],\n'
        if desc_items:
            output += '  description: list(\n'
            for item in desc_items:
                output += f'    [{item}],\n'
            output += '  )\n'
        else:
            output += '  description: []\n'
        output += ')\n\n'

    return output


def render_skills(skills: List[Dict[str, Any]], label: str = "Skills",
                  section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render skills using brilliant-cv."""
    if not skills:
        return ""

    output = render_section_heading(label, section_style)

    for skill_group in skills:
        name = skill_group.get("name", "")
        keywords = skill_group.get("keywords", [])
        level = skill_group.get("level")

        if not keywords and not (isinstance(level, str) and level.strip()) and parse_skill_level(level) is None:
            continue

        keywords_str = " #sym.dot.c ".join([escape_typst(kw) for kw in keywords])
        numeric_level = parse_skill_level(level)
        if numeric_level is not None:
            output += (
                f'#cv-skill-with-level(type: [{escape_typst(name)}], '
                f'level: {numeric_level}, info: [{keywords_str or escape_typst(str(level))}])\n#v(6pt)\n\n'
            )
        else:
            if isinstance(level, str) and level.strip():
                keywords_str = (
                    f"{keywords_str} #sym.dot.c {escape_typst(level.strip())}"
                    if keywords_str
                    else escape_typst(level.strip())
                )
            output += f'#cv-skill(type: [{escape_typst(name)}], info: [{keywords_str}])\n#v(6pt)\n\n'

    return output


def render_certificates(certificates: List[Dict[str, Any]], base_output_dir: Path, assets_dir: Path,
                        label: str = "Certificates",
                        section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render certificates using brilliant-cv."""
    if not certificates:
        return ""

    output = render_section_heading(label, section_style)
    rendered_certs = []

    for cert in certificates:
        name = cert.get("name", "")
        issuer = cert.get("issuer", "")
        date = cert.get("date", "")
        url = cert.get("url", "")
        image_url = cert.get("image", "")

        if "See full list" in name:
            if url:
                output += f'Full list available at #link("{url}")[Credly]\n\n'
            continue

        local_image = None
        if image_url:
            local_image = download_image(image_url, base_output_dir, assets_dir / "badges")

        date_fmt = format_date(date) if date else ""
        rendered_certs.append({
            "name": name,
            "issuer": issuer,
            "url": url,
            "date_fmt": date_fmt,
            "local_image": local_image,
        })

    use_grid = any(cert["local_image"] for cert in rendered_certs)

    for cert in rendered_certs:
        name = cert["name"]
        issuer = cert["issuer"]
        url = cert["url"]
        date_fmt = cert["date_fmt"]
        local_image = cert["local_image"]

        if use_grid:
            output += '#cv-entry(\n'
            output += '  metadata: metadata_alt,\n'
            output += '  title: ['
            if url:
                output += f'#link("{url}")[*{escape_typst(name)}*]'
            else:
                output += f'*{escape_typst(name)}*'
            output += '],\n'
            output += f'  society: [{escape_typst(issuer)}],\n'
            output += f'  date: [{date_fmt}],\n'
            if local_image:
                output += f'  logo: [#image("{local_image}")],\n'
            else:
                output += '  logo: [#box(width: 0.1em, height: 0.1em)[]],\n'
            output += '  location: [],\n'
            output += '  description: []\n'
            output += ')\n\n'
        else:
            output += '#cv-honor(\n'
            output += f'  date: [{date_fmt}],\n'
            output += '  title: ['
            if url:
                output += f'#link("{url}")[{escape_typst(name)}]'
            else:
                output += escape_typst(name)
            output += '],\n'
            if issuer:
                output += f'  issuer: [{escape_typst(issuer)}],\n'
            if url:
                output += f'  url: "{url}",\n'
            output += ')\n\n'

    return output


def render_awards(awards: List[Dict[str, Any]], label: str = "Awards",
                  section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render awards using brilliant-cv."""
    if not awards:
        return ""

    output = render_section_heading(label, section_style)

    for award in awards:
        title = award.get("title", "")
        date = award.get("date", "")
        awarder = award.get("awarder", "")
        summary = award.get("summary", "")
        url = award.get("url", "")

        date_fmt = format_date(date) if date else ""

        output += '#cv-honor(\n'
        output += f'  date: [{date_fmt}],\n'
        output += f'  title: [{process_text(title)}],\n'
        if awarder:
            output += f'  issuer: [{escape_typst(awarder)}],\n'
        if url:
            output += f'  url: "{url}",\n'
        output += ')\n#v(6pt)\n\n'

        if summary:
            output += f'{process_text(summary)}\n\n'

    return output


def render_projects(projects: List[Dict[str, Any]], label: str = "Projects",
                    section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render projects using brilliant-cv."""
    if not projects:
        return ""

    output = render_section_heading(label, section_style)

    for project in projects:
        name = project.get("name", "")
        description = project.get("description", "")
        entity = project.get("entity", "")
        start = project.get("startDate", "")
        end = project.get("endDate", "")
        highlights = project.get("highlights", [])
        keywords = project.get("keywords", [])
        url = project.get("url", "")
        roles = project.get("roles", [])
        location = normalize_location(project.get("location", ""))

        if not name:
            if description:
                output += f"_{process_text(description)}_\n\n"
            continue

        date_range = format_date_range(start, end) if start else ""

        desc_parts = []
        if description:
            desc_parts.append(process_text(description))
        if roles:
            for role in roles:
                desc_parts.append(f"- {process_text(role)}")
        if highlights:
            for highlight in highlights:
                desc_parts.append(f"- {process_text(highlight)}")

        full_description = "\n".join(desc_parts) if desc_parts else ""

        output += f'#cv-entry(\n'
        output += f'  metadata: metadata_alt,\n'
        output += f'  title: ['
        if url:
            output += f'#link("{url}")[{process_text(name)}]'
        else:
            output += process_text(name)
        output += '],\n'
        output += f'  society: [{process_text(entity)}],\n'
        output += f'  date: [{date_range}],\n'
        if location:
            output += f'  location: [{escape_typst(location)}],\n'
        else:
            output += f'  location: [],\n'
        if keywords:
            output += f'  tags: {typst_list([str(k) for k in keywords if isinstance(k, str) and k])},\n'
        output += f'  description: [\n    {full_description}\n  ]\n'
        output += ')\n\n'

    return output


def render_volunteer(volunteer: List[Dict[str, Any]], label: str = "Volunteer",
                     section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render volunteer activities using brilliant-cv."""
    if not volunteer:
        return ""

    output = render_section_heading(label, section_style)

    for vol in volunteer:
        org = vol.get("organization", "")
        position = vol.get("position", "")
        start = vol.get("startDate", "")
        end = vol.get("endDate", "")
        url = vol.get("url", "")
        summary = vol.get("summary", "")
        highlights = vol.get("highlights", [])

        date_range = format_date_range(start, end) if start else ""
        desc_parts = []
        if summary:
            desc_parts.append(process_text(summary))
        if highlights:
            for highlight in highlights:
                desc_parts.append(f"- {process_text(highlight)}")
        description = "\n".join(desc_parts)

        output += f'#cv-entry(\n'
        output += f'  title: [{escape_typst(position)}],\n'
        output += f'  society: ['
        if url:
            output += f'#link("{url}")[{escape_typst(org)}]'
        else:
            output += escape_typst(org)
        output += '],\n'
        output += f'  date: [{date_range}],\n'
        output += f'  location: [],\n'
        output += f'  description: [\n    {description}\n  ]\n'
        output += ')\n\n'

    return output


INLINE_PUBLICATIONS_DEFAULTS: Dict[str, Any] = {
    "ref-style": "ieee",
    "ref-full": True,
    "ref-sorting": "ydnt",
}


def get_publications_options(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    meta = resume_data.get("meta", {})
    if not isinstance(meta, dict):
        return {}
    options = meta.get("publicationsOptions", {})
    return options if isinstance(options, dict) else {}


def get_publications_label(resume_data: Dict[str, Any], fallback: str = "Publications") -> str:
    label = get_theme_options(resume_data).get("sectionLabels", {}).get("publications", fallback)
    if not isinstance(label, str) or not label.strip():
        return fallback
    return normalize_label(label.strip())


def get_standalone_publications_label(resume_data: Dict[str, Any], fallback: str = "Publications") -> str:
    options = get_publications_options(resume_data)
    label = options.get("full_standalone_list_title", fallback)
    if not isinstance(label, str) or not label.strip():
        return fallback
    return normalize_label(label.strip())


def get_generated_publications_entry(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    publications = resume_data.get("publications")
    if not isinstance(publications, list):
        return {}
    entries = [pub for pub in publications if isinstance(pub, dict) and "bibfiles" in pub]
    if len(entries) > 1:
        raise SystemExit(
            "Multiple publications entries define bibfiles; only one generated-publications entry is allowed"
        )
    return entries[0] if entries else {}


def resolve_publications_sectioning(resume_data: Dict[str, Any]) -> tuple[bool, List[str], Dict[str, str]]:
    options = get_publications_options(resume_data)
    pub_sections = options.get("pubSections", False)

    if pub_sections is False or pub_sections is None:
        return False, [], {}

    if isinstance(pub_sections, list):
        section_order = [str(s).strip() for s in pub_sections if isinstance(s, str) and s.strip()]
        if not section_order:
            return False, [], {}
    else:
        section_order = list(DEFAULT_PUBLICATION_SECTIONS)

    custom_titles = options.get("pubSectionTitles", {})
    if not isinstance(custom_titles, dict):
        custom_titles = {}

    section_titles: Dict[str, str] = {}
    for section in section_order:
        title = custom_titles.get(section)
        if isinstance(title, str) and title.strip():
            section_titles[section] = title.strip()
        else:
            section_titles[section] = DEFAULT_PUBLICATION_SECTION_TITLES.get(section, section)

    return True, section_order, section_titles


def get_inline_publications_config(resume_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return inline bibliography config from meta.publicationsOptions plus publications entry selectors."""
    inline = get_publications_options(resume_data).get("inline_in_pdf")
    publication = get_generated_publications_entry(resume_data)
    bibentries = publication.get("bibentries", []) if isinstance(publication, dict) else []
    normalized_bibentries = [entry for entry in bibentries if isinstance(entry, str) and entry]

    if inline is True:
        merged = dict(INLINE_PUBLICATIONS_DEFAULTS)
    elif isinstance(inline, dict):
        merged = dict(INLINE_PUBLICATIONS_DEFAULTS)
        merged.update(inline)
    else:
        return None

    merged["key-list"] = normalized_bibentries
    return merged


def to_typst_value(value: Any) -> str:
    """Serialize a Python value into a Typst literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if len(value)>0:
            # The trailing comma before the closing parenthesis is to avoid
            # single-element string lists being converted to a list of characters.
            return "(" + ", ".join(to_typst_value(v) for v in value) + ",)"
        else:
            return "()"
    return f'"{escape_typst(str(value))}"'


def pergamon_style_expr(style_name: Any) -> str:
    style_key = str(style_name or "ieee").strip().lower()
    if style_key in {"ieee", "numeric", "numbered"}:
        return "format-citation-numeric()"
    if style_key in {"apa", "authoryear", "author-year", "author-date"}:
        return "format-citation-authoryear()"
    if style_key in {"alphabetic", "alpha"}:
        return "format-citation-alphabetic()"
    return "format-citation-numeric()"


def render_pergamon_setup(bib_path: str, config: Dict[str, Any]) -> str:
    ref_full = bool(config.get("ref-full", True))
    key_list = config.get("key-list", [])
    if not isinstance(key_list, list):
        key_list = []
    key_list = [str(key) for key in key_list if isinstance(key, str) and key]

    return (
        '#import "@preview/pergamon:0.7.2": *\n\n'
        "#let has-keyword(keywords, wanted) = {\n"
        "  if keywords == none { false } else {\n"
        "    keywords\n"
        '      .split(",")\n'
        "      .map(s => s.trim())\n"
        "      .contains(wanted)\n"
        "  }\n"
        "}\n\n"
        f"#let publications-style = {pergamon_style_expr(config.get('ref-style'))}\n"
        f"#let publications-ref-full = {to_typst_value(ref_full)}\n"
        f"#let publications-key-list = {to_typst_value(key_list)}\n"
        "#let publications-include(reference) = {\n"
        "  if publications-ref-full {\n"
        "    true\n"
        "  } else {\n"
        "    publications-key-list.contains(reference.entry_key)\n"
        "  }\n"
        "}\n\n"
        f'#add-bib-resource(read("{escape_typst(bib_path)}"))\n\n'
    )


def iter_bib_entries(bibtex_source: str) -> List[tuple[str, str]]:
    entries: List[tuple[str, str]] = []
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

        entries.append((entry_key, bibtex_source[match.start():end]))
        pos = end

    return entries


def extract_bib_field(raw_entry: str, field_name: str) -> Optional[str]:
    field_re = re.compile(rf"(^|,)\s*{re.escape(field_name)}\s*=", flags=re.IGNORECASE | re.MULTILINE)
    match = field_re.search(raw_entry)
    if not match:
        return None

    idx = match.end()
    while idx < len(raw_entry) and raw_entry[idx].isspace():
        idx += 1
    if idx >= len(raw_entry):
        return None

    opener = raw_entry[idx]
    if opener == "{":
        depth = 1
        idx += 1
        start = idx
        while idx < len(raw_entry) and depth > 0:
            ch = raw_entry[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return raw_entry[start:idx]
            idx += 1
        return None

    if opener == '"':
        idx += 1
        start = idx
        while idx < len(raw_entry):
            ch = raw_entry[idx]
            if ch == '"' and raw_entry[idx - 1] != "\\":
                return raw_entry[start:idx]
            idx += 1
        return None

    start = idx
    while idx < len(raw_entry) and raw_entry[idx] not in ",\n\r":
        idx += 1
    value = raw_entry[start:idx].strip()
    return value or None


def get_nonempty_publication_sections(
    bib_file_path: Optional[Path],
    section_order: List[str],
    config: Dict[str, Any],
) -> List[str]:
    if bib_file_path is None or not bib_file_path.exists():
        return section_order

    try:
        bibtex_source = bib_file_path.read_text(encoding="utf-8")
    except OSError:
        return section_order

    ref_full = bool(config.get("ref-full", True))
    key_list = config.get("key-list", [])
    allowed_keys = {str(key) for key in key_list if isinstance(key, str) and key} if not ref_full else None
    seen_sections = set()

    for entry_key, raw_entry in iter_bib_entries(bibtex_source):
        if allowed_keys is not None and entry_key not in allowed_keys:
            continue
        keywords_raw = extract_bib_field(raw_entry, "keywords")
        if not keywords_raw:
            continue
        keywords = {part.strip().lower() for part in keywords_raw.split(",") if part.strip()}
        for section in section_order:
            if section.lower() in keywords:
                seen_sections.add(section)

    return [section for section in section_order if section in seen_sections]


def render_pergamon_bibliography(
    resume_data: Dict[str, Any],
    config: Dict[str, Any],
    include_titles: bool = True,
    bib_file_path: Optional[Path] = None,
) -> str:
    sectioning_enabled, section_order, section_titles = resolve_publications_sectioning(resume_data)
    bibliography_title = get_publications_label(resume_data)
    sorting = str(config.get("ref-sorting", "ydnt") or "ydnt").strip() or "ydnt"
    blocks: List[str] = []

    def block(title_expr: str, filter_expr: str) -> str:
        return (
            "  #print-bibliography(\n"
            "    format-reference: format-reference(reference-label: publications-style.reference-label),\n"
            f"    title: {title_expr},\n"
            "    label-generator: publications-style.label-generator,\n"
            f'    sorting: "{escape_typst(sorting)}",\n'
            "    show-all: true,\n"
            "    resume-after: auto,\n"
            f"    filter: reference => publications-include(reference){filter_expr}\n"
            "  )\n"
        )

    if not sectioning_enabled:
        title_expr = f'"{escape_typst(bibliography_title)}"' if include_titles else "none"
        blocks.append(block(title_expr, ""))
        return "#refsection(format-citation: publications-style.format-citation)[\n" + "".join(blocks) + "]\n\n"

    section_order = get_nonempty_publication_sections(bib_file_path, section_order, config)
    for section in section_order:
        title_expr = f'"{escape_typst(section_titles.get(section, section))}"'
        blocks.append(
            block(
                title_expr,
                f' and has-keyword(reference.fields.at("keywords", default: none), "{escape_typst(section)}")',
            )
        )
    if not blocks:
        return ""
    return "#refsection(format-citation: publications-style.format-citation)[\n" + "".join(blocks) + "]\n\n"


def render_publications(
    resume_data: Dict[str, Any],
    publications: List[Dict[str, Any]],
    label: str = "Publications",
    inline_publications_config: Optional[Dict[str, Any]] = None,
    inline_bib_path: Optional[str] = None,
    inline_bib_file_path: Optional[Path] = None,
    section_style: Optional[Dict[str, Any]] = None,
) -> str:
    """Render publications using brilliant-cv."""
    if not publications:
        return ""

    output = render_section_heading(label, section_style)

    if inline_bib_path and inline_publications_config is not None:
        output += render_pergamon_bibliography(
            resume_data,
            inline_publications_config,
            include_titles=False,
            bib_file_path=inline_bib_file_path,
        )
        return output

    for pub in publications:
        name = pub.get("name", "")
        publisher = pub.get("publisher", "")
        release_date = pub.get("releaseDate", "")
        url = pub.get("url", "")
        summary = pub.get("summary", "")

        date_fmt = format_date(release_date) if release_date else ""

        output += '#cv-entry(\n'
        output += f'  title: ['
        if url:
            output += f'#link("{url}")[{process_text(name)}]'
        else:
            output += process_text(name)
        output += '],\n'
        output += f'  society: [{escape_typst(publisher)}],\n'
        output += f'  date: [{date_fmt}],\n'
        output += f'  location: [],\n'
        output += f'  description: [{process_text(summary)}]\n'
        output += ')\n\n'

    return output


def render_languages(languages: List[Dict[str, Any]], label: str = "Languages",
                     section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render languages using brilliant-cv."""
    if not languages:
        return ""

    output = render_section_heading(label, section_style)

    for lang in languages:
        language = lang.get("language", "")
        fluency = lang.get("fluency", "")

        if language and fluency:
            output += f'#cv-skill(type: [{escape_typst(language)}], info: [{escape_typst(fluency)}])\n\n'
        elif language:
            output += f'#cv-skill(type: [{escape_typst(language)}], info: [])\n\n'
        elif fluency:
            output += f'#cv-skill(type: [Language], info: [{escape_typst(fluency)}])\n\n'

    return output


def render_interests(interests: List[Dict[str, Any]], label: str = "Interests",
                     section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render interests using brilliant-cv."""
    if not interests:
        return ""

    output = render_section_heading(label, section_style)

    for interest in interests:
        name = interest.get("name", "")
        keywords = interest.get("keywords", [])
        keywords_str = " #sym.dot.c ".join([escape_typst(kw) for kw in keywords])
        if keywords_str:
            output += f'#cv-skill(type: [{escape_typst(name)}], info: [{keywords_str}])\n\n'
        else:
            output += f'#cv-skill(type: [{escape_typst(name)}], info: [])\n\n'

    return output


def render_references(references: List[Dict[str, Any]], label: str = "References",
                      section_style: Optional[Dict[str, Any]] = None) -> str:
    """Render references as Typst quotes."""
    if not references:
        return ""

    output = render_section_heading(label, section_style)
    output += f'\n#set quote(block: true)\n'
    
    for ref in references:
        name = ref.get("name", "")
        reference = ref.get("reference", "")
        if not (name or reference):
            continue
        if name:
            output += f'#quote(attribution: [{escape_typst(name)}])[\n'
        else:
            output += '#quote[\n'
        if reference:
            output += f'{process_text(reference)}\n'
        output += ']\n\n'

    return output


def render_sections(resume_data: Dict[str, Any], base_output_dir: Path, assets_dir: Path,
                    source_assets_dir: Path, inline_publications_bib: Optional[str] = None,
                    inline_publications_bib_file_path: Optional[Path] = None) -> str:
    """Render resume sections in the desired order."""
    theme_options = get_theme_options(resume_data)
    sections = theme_options.get("sections")
    sections_is_default = not isinstance(sections, list) or not sections
    if sections_is_default:
        sections = DEFAULT_SECTIONS

    section_labels = theme_options.get("sectionLabels", {})
    projects_by_type = bool(theme_options.get("projectsByType"))
    projects = resume_data.get("projects", [])
    inline_publications_config = get_inline_publications_config(resume_data)
    section_style = get_section_style_options(resume_data)
    has_project_overrides = (not sections_is_default) and any(
        isinstance(section, str) and (section == "projects" or section.startswith(PROJECT_SECTION_PREFIX))
        for section in sections
    )

    def label_for(key: str, fallback: str) -> str:
        return normalize_label(section_labels.get(key, fallback))

    output = ""
    for section in sections:
        if section == "work":
            output += render_experience(
                resume_data.get("work", []),
                base_output_dir,
                assets_dir,
                source_assets_dir,
                label=label_for("work", "Work"),
                section_style=section_style,
            )
            continue
        if section == "volunteer":
            output += render_volunteer(
                resume_data.get("volunteer", []),
                label=label_for("volunteer", "Volunteer"),
                section_style=section_style,
            )
            continue
        if section == "education":
            output += render_education(
                resume_data.get("education", []),
                base_output_dir,
                assets_dir,
                source_assets_dir,
                label=label_for("education", "Education"),
                section_style=section_style,
            )
            continue
        if section == "projects":
            if projects_by_type and sections_is_default:
                for type_key, items in ordered_project_groups(projects):
                    if not items:
                        continue
                    if type_key is None:
                        output += render_projects(items, label_for("projects", "Projects"), section_style=section_style)
                    else:
                        label_key = f"{PROJECT_SECTION_PREFIX}{type_key}"
                        output += render_projects(items, label_for(label_key, str(type_key)), section_style=section_style)
                continue

            if projects_by_type and has_project_overrides:
                typeless = [p for p in projects if not p.get("type")]
                if typeless:
                    output += render_projects(typeless, label_for("projects", "Projects"), section_style=section_style)
                continue

            output += render_projects(projects, label_for("projects", "Projects"), section_style=section_style)
            continue
        if isinstance(section, str) and section.startswith(PROJECT_SECTION_PREFIX):
            if not projects_by_type:
                continue
            type_key = section[len(PROJECT_SECTION_PREFIX):].strip()
            if not type_key:
                continue
            items = [p for p in projects if p.get("type") == type_key]
            if not items:
                continue
            output += render_projects(items, label_for(section, type_key), section_style=section_style)
            continue
        if section == "awards":
            output += render_awards(
                resume_data.get("awards", []),
                label=label_for("awards", "Awards"),
                section_style=section_style,
            )
            continue
        if section == "certificates":
            output += render_certificates(
                resume_data.get("certificates", []),
                base_output_dir,
                assets_dir,
                label=label_for("certificates", "Certificates"),
                section_style=section_style,
            )
            continue
        if section == "publications":
            output += render_publications(
                resume_data,
                resume_data.get("publications", []),
                label=label_for("publications", "Publications"),
                inline_publications_config=inline_publications_config,
                inline_bib_path=inline_publications_bib,
                inline_bib_file_path=inline_publications_bib_file_path,
                section_style=section_style,
            )
            continue
        if section == "skills":
            output += render_skills(
                resume_data.get("skills", []),
                label=label_for("skills", "Skills"),
                section_style=section_style,
            )
            continue
        if section == "languages":
            output += render_languages(
                resume_data.get("languages", []),
                label=label_for("languages", "Languages"),
                section_style=section_style,
            )
            continue
        if section == "interests":
            output += render_interests(
                resume_data.get("interests", []),
                label=label_for("interests", "Interests"),
                section_style=section_style,
            )
            continue
        if section == "references":
            output += render_references(
                resume_data.get("references", []),
                label=label_for("references", "References"),
                section_style=section_style,
            )
            continue

    return output

def generate_typst_cv(
    resume_data: Dict[str, Any],
    base_output_dir: Path,
    assets_dir: Path,
    source_assets_dir: Path,
    inline_publications_bib: Optional[str] = None,
) -> str:
    """Generate Typst CV using brilliant-cv template."""

    basics = resume_data.get("basics", {})
    image_url = basics.get("image", "")

    # Download profile photo
    photo_path = None
    if image_url:
        photo_path = resolve_image_reference(image_url, base_output_dir, assets_dir / "profile")
    inline_publications_config = get_inline_publications_config(resume_data)
    inline_publications_bib_file_path: Optional[Path] = None
    if inline_publications_bib:
        bib_path = Path(inline_publications_bib)
        if not bib_path.is_absolute():
            bib_path = base_output_dir / bib_path
        inline_publications_bib_file_path = bib_path

    # Start with imports and metadata
    output = """// Professional CV generated from JSONResume
// Using brilliant-cv template

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
  // New parameter names (recommended)
  awesome-colors: none,
  // Old parameter names (deprecated, for backward compatibility)
  awesomeColors: _awesome-colors,
) = context {
  let metadata = if metadata != none { metadata } else { cv-metadata.get() }
  // Backward compatibility logic (remove this block when deprecating)
  let awesome-colors = if awesome-colors != none {
    awesome-colors
  } else {
    // TODO: Add deprecation warning in future version
    // Currently Typst doesn't have a standard warning mechanism for user functions
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

    if inline_publications_bib and inline_publications_config is not None:
        output += render_pergamon_setup(inline_publications_bib, inline_publications_config)
        output += "\n"

    # Add metadata
    output += generate_metadata(resume_data)
    output += '''
#let metadata_alt = metadata + (
  layout: metadata.layout + (
    entry: metadata.layout.entry + (
      display_entry_society_first: false,
    )
  )
)
'''
    output += "\n"

    # Apply brilliant-cv template
    if photo_path:
        output += f'''#show: cv.with(
  metadata,
  profile-photo: image("{photo_path}"),
)

'''
    else:
        output += '''#show: cv.with(
  metadata,
)

'''

    # Add content sections
    output += render_summary(
        basics,
        show_title=show_summary_title(resume_data),
        section_style=get_section_style_options(resume_data),
    )
    output += render_sections(
        resume_data,
        base_output_dir,
        assets_dir,
        source_assets_dir,
        inline_publications_bib=inline_publications_bib,
        inline_publications_bib_file_path=inline_publications_bib_file_path,
    )

    return output


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: render_typst_cv.py <jsonresume-file> [output-file]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not input_file.exists():
        print(f"Error: Input file {input_file} not found")
        sys.exit(1)

    with open(input_file, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)

    assets_dir = Path("assets")
    source_assets_dir = Path(os.environ.get("VITA_ASSETS_DIR", "assets"))
    inline_publications_bib = os.environ.get("VITA_INLINE_PUBLICATIONS_BIB", "").strip() or None

    if output_file:
        base_output_dir = output_file.parent
    else:
        base_output_dir = Path.cwd()

    assets_dir_full = base_output_dir / assets_dir

    typst_content = generate_typst_cv(
        resume_data,
        base_output_dir,
        assets_dir,
        source_assets_dir,
        inline_publications_bib=inline_publications_bib,
    )

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(typst_content)
        print(f"Generated Typst CV: {output_file}")
    else:
        print(typst_content)


if __name__ == "__main__":
    main()
