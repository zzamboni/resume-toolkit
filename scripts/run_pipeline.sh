#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
toolkit_root="${VITA_TOOLKIT_ROOT:-$(cd "$script_dir/.." && pwd)}"
workdir="${VITA_WORKDIR:-$PWD}"
assets_source_dir="${VITA_ASSETS_DIR:-$workdir/assets}"
if [[ ! -d "$assets_source_dir" ]]; then
  assets_source_dir="$toolkit_root/assets"
fi

usage() {
  cat <<'USAGE'
Usage: scripts/run_pipeline.sh --json <file> [--bib <file> ...] [--pubs-url <url>] --out <dir>

Required:
  --json <file>   JSON Resume input (relative to working dir or absolute path)
  --out <dir>     Output base directory (relative to working dir or absolute path)

Optional:
  --bib <file>      BibTeX input (repeatable). If omitted, uses meta.publicationsOptions.bibfiles from the JSON resume
  --pubs-url <url>  Online publications URL used in generated publications PDF footer

Example:
  scripts/run_pipeline.sh --json resume.json --bib publications.bib --pubs-url https://example.org/vita/publications --out build/out
USAGE
}

resolve_path() {
  local p="$1"
  if [[ "$p" = /* ]]; then
    printf '%s\n' "$p"
  else
    printf '%s\n' "$workdir/$p"
  fi
}

calc_hash() {
  {
    for entry in "$@"; do
      case "$entry" in
        STR:*)
          printf 'STR\n%s\n' "${entry#STR:}"
          ;;
        FILE:*)
          local f="${entry#FILE:}"
          if [[ -f "$f" ]]; then
            printf 'FILE\n%s\n' "$f"
            sha256sum "$f"
          else
            printf 'MISSING_FILE\n%s\n' "$f"
          fi
          ;;
        DIR:*)
          local d="${entry#DIR:}"
          if [[ -d "$d" ]]; then
            printf 'DIR\n%s\n' "$d"
            while IFS= read -r -d '' p; do
              printf 'PATH\n%s\n' "$p"
              sha256sum "$p"
            done < <(find "$d" -type f -print0 | sort -z)
          else
            printf 'MISSING_DIR\n%s\n' "$d"
          fi
          ;;
      esac
    done
  } | sha256sum | awk '{print $1}'
}

needs_rebuild() {
  local out_file="$1"
  local stamp_file="$2"
  local new_hash="$3"
  [[ ! -f "$out_file" || ! -f "$stamp_file" || "$(cat "$stamp_file" 2>/dev/null || true)" != "$new_hash" ]]
}

mark_built() {
  local stamp_file="$1"
  local new_hash="$2"
  printf '%s\n' "$new_hash" > "$stamp_file"
}

json_file=""
output_dir=""
pubs_url=""
bib_files=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      json_file="$2"
      shift 2
      ;;
    --bib)
      bib_files+=("$2")
      shift 2
      ;;
    --out)
      output_dir="$2"
      shift 2
      ;;
    --pubs-url)
      pubs_url="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$json_file" ]]; then
  usage
  exit 1
fi

if [[ -z "$output_dir" ]]; then
    output_dir="build/$(basename $json_file .json)"
fi


json_file="$(resolve_path "$json_file")"
out_base="$(resolve_path "$output_dir")"
json_name="$(basename "$json_file")"
json_stem="${json_name%.*}"

cv_typ_name="${json_stem}.typ"
cv_pdf_name="${json_stem}.pdf"
pubs_base_name="${json_stem}-pubs"
pubs_bib_name="${pubs_base_name}.bib"
pubs_typ_name="${pubs_base_name}.typ"
pubs_pdf_name="${pubs_base_name}.pdf"

if [[ ! -f "$json_file" ]]; then
  echo "JSON file not found: $json_file" >&2
  exit 1
fi

json_dir="$(cd "$(dirname "$json_file")" && pwd)"
pub_sections_mode="$(jq -r '
  .meta.publicationsOptions.pubSections as $s
  | if ($s == false) or ($s == null) then "none"
    elif $s == true then "default"
    elif ($s | type) == "array" then "custom"
    else "none"
    end
' "$json_file")"

default_pub_sections=(book editorial thesis refereed techreport presentations invited patent other)
pub_sections=()
if [[ "$pub_sections_mode" == "custom" ]]; then
  mapfile -t pub_sections < <(jq -r '.meta.publicationsOptions.pubSections[]? | select(type == "string") | select(length > 0)' "$json_file")
  if [[ ${#pub_sections[@]} -eq 0 ]]; then
    pub_sections_mode="none"
  fi
fi
if [[ "$pub_sections_mode" == "default" ]]; then
  pub_sections=("${default_pub_sections[@]}")
fi

declare -A pub_section_titles=(
  [book]="Books"
  [editorial]="Editorial Activities"
  [thesis]="Theses"
  [refereed]="Refereed Papers"
  [techreport]="Tech Reports"
  [presentations]="Presentations at Conferences and Workshops"
  [invited]="Invited Talks and Articles"
  [patent]="Patents"
  [other]="Other Publications"
)
while IFS=$'\t' read -r k v; do
  [[ -n "${k:-}" && -n "${v:-}" ]] || continue
  pub_section_titles["$k"]="$v"
done < <(jq -r '
  .meta.publicationsOptions.pubSectionTitles // {}
  | to_entries[]
  | select((.key | type) == "string")
  | select((.value | type) == "string")
  | [.key, .value] | @tsv
' "$json_file")

using_json_bibfiles=0
if [[ ${#bib_files[@]} -eq 0 ]]; then
  while IFS= read -r bib; do
    [[ -n "$bib" ]] || continue
    bib_files+=("$bib")
  done < <(
    jq -r '
      [.meta.publicationsOptions.bibfiles[]? | select(type == "string") | select(length > 0)]
      | unique
      | .[]
    ' "$json_file"
  )
  if [[ ${#bib_files[@]} -gt 0 ]]; then
    using_json_bibfiles=1
  fi
fi

for i in "${!bib_files[@]}"; do
  if [[ "$using_json_bibfiles" == "1" && "${bib_files[$i]}" != /* ]]; then
    bib_files[$i]="$json_dir/${bib_files[$i]}"
  else
    bib_files[$i]="$(resolve_path "${bib_files[$i]}")"
  fi
  if [[ ! -f "${bib_files[$i]}" ]]; then
    echo "BibTeX file not found: ${bib_files[$i]}" >&2
    exit 1
  fi
done

resume_name="$(
  python - "$json_file" <<'PY'
import json
import sys
from pathlib import Path

def esc(s: str) -> str:
    rep = {
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
    return "".join(rep.get(ch, ch) for ch in s)

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
name = data.get("basics", {}).get("name", "Publications")
print(esc(str(name)))
PY
)"

out_vita="$out_base/vita"
out_pubs="$out_vita/publications"
inline_bib_name="${json_stem}-vita.bib"
inline_bib_path="$out_vita/$inline_bib_name"
inline_bib_for_typst=""
inline_publications_requested="$(jq -r '
  .meta.publicationsOptions.inline_in_pdf as $i
  | ($i == true) or (($i | type) == "object")
' "$json_file")"
mkdir -p "$out_vita"

state_dir="$out_base/.pipeline-state/$json_stem"
mkdir -p "$state_dir"

# Sync profile assets for Typst CV

mkdir -p "$out_vita/assets/profile"
if compgen -G "$toolkit_root/assets/profile/*" >/dev/null; then
  cp -a "$toolkit_root/assets/profile"/* "$out_vita/assets/profile/"
fi

profile_image=$(jq -r '.basics.image // ""' $json_file)

cv_html="$out_vita/index.html"
cv_html_hash="$(calc_hash \
  "FILE:$json_file" \
  "FILE:$profile_image" \
  "FILE:$toolkit_root/scripts/render_cv.sh" \
  "STR:cv_html_target=$cv_html")"
if needs_rebuild "$cv_html" "$state_dir/cv-html.sha" "$cv_html_hash"; then
  echo "→ Building CV HTML"
  "$toolkit_root/scripts/render_cv.sh" "" "$json_file" "$cv_html"
  mark_built "$state_dir/cv-html.sha" "$cv_html_hash"
else
  echo "→ CV HTML up to date"
fi

# Optional dev autoreload snippet injection (enabled by DEV_RELOAD=1)
if [[ "${DEV_RELOAD:-0}" == "1" ]] && [[ -f "$cv_html" ]] && ! grep -q "__reload" "$cv_html"; then
  python "$toolkit_root/scripts/inject_dev_reload.py" "$cv_html"
fi

if [[ ${#bib_files[@]} -gt 0 ]]; then
  mkdir -p "$out_pubs"

  pubs_tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$pubs_tmp_dir"' EXIT

  sorted_bibs=("${bib_files[@]}")
  if [[ ${#sorted_bibs[@]} -gt 0 ]]; then
    IFS=$'\n' sorted_bibs=($(printf '%s\n' "${sorted_bibs[@]}" | sort))
    unset IFS
  fi

  for bib in "${sorted_bibs[@]}"; do
    cp "$bib" "$pubs_tmp_dir/"
  done

  pubs_links_json="$(printf '[{\"name\":\"PDF\",\"url\":\"/vita/publications/%s\",\"icon\":\"file-pdf\"},{\"name\":\"BibTeX\",\"url\":\"/vita/publications/%s\",\"icon\":\"tex\"}]' "$pubs_pdf_name" "$pubs_bib_name")"

  pubs_html="$out_pubs/index.html"
  agg_bib="$out_pubs/$pubs_bib_name"
  resume_name=$(jq -r '.basics.name // ""' $json_file)
  pubs_html_hash_args=(
    "FILE:$toolkit_root/scripts/build_publications.py"
    "FILE:$toolkit_root/templates/publications.html.j2"
    "FILE:$json_file"
    "STR:resume_name=$resume_name"
    "STR:pubs_links=$pubs_links_json"
    "STR:pubs_bib_name=$pubs_bib_name"
  )
  for bib in "${sorted_bibs[@]}"; do
    pubs_html_hash_args+=("FILE:$bib")
  done
  pubs_html_hash="$(calc_hash "${pubs_html_hash_args[@]}")"
  if needs_rebuild "$pubs_html" "$state_dir/pubs-html.sha" "$pubs_html_hash" || needs_rebuild "$agg_bib" "$state_dir/pubs-html.sha" "$pubs_html_hash"; then
    echo "→ Building publications HTML + BibTeX"
    (
      cd "$toolkit_root"
      PUBS_BIB_DIR="$pubs_tmp_dir" \
      PUBS_HTML="$pubs_html" \
      PUBS_OUT_DIR="$out_pubs" \
      PUBS_BIB_FILENAME="$pubs_bib_name" \
      PUBS_RESUME_JSON="$json_file" \
      PUBS_LINKS="$pubs_links_json" \
      python scripts/build_publications.py
      # Optional dev autoreload snippet injection (enabled by DEV_RELOAD=1)
      if [[ "${DEV_RELOAD:-0}" == "1" ]] && [[ -f "$pubs_html" ]] && ! grep -q "__reload" "$pubs_html"; then
        python "$toolkit_root/scripts/inject_dev_reload.py" "$pubs_html"
      fi
    )
    mark_built "$state_dir/pubs-html.sha" "$pubs_html_hash"
  else
    echo "→ Publications HTML + BibTeX up to date"
  fi

  if [[ ! -f "$agg_bib" ]]; then
    echo "Aggregated bib not found: $agg_bib" >&2
    exit 1
  fi

  if [[ "$inline_publications_requested" == "true" ]]; then
    cp "$agg_bib" "$inline_bib_path"
    inline_bib_for_typst="$inline_bib_name"
  fi

  pubs_typ="$out_pubs/$pubs_typ_name"
  python "$toolkit_root/scripts/render_typst_publications.py" \
    "$json_file" \
    "$pubs_bib_name" \
    "$pubs_typ" \
    "$pubs_url"

  pubs_pdf="$out_pubs/$pubs_pdf_name"
  pubs_pdf_hash="$(calc_hash \
    "FILE:$toolkit_root/scripts/run_pipeline.sh" \
    "FILE:$toolkit_root/scripts/render_typst_publications.py" \
    "FILE:$json_file" \
    "FILE:$agg_bib" \
    "STR:resume_name=$resume_name" \
    "STR:pubs_typ_name=$pubs_typ_name" \
    "STR:pubs_pdf_name=$pubs_pdf_name" \
    "STR:resume_name=$resume_name" \
    "STR:pubs_url=$pubs_url")"
  if needs_rebuild "$pubs_pdf" "$state_dir/pubs-pdf.sha" "$pubs_pdf_hash"; then
    echo "→ Building publications PDF"
    (
      cd "$out_pubs"
      typst compile "$pubs_typ_name" "$pubs_pdf_name"
    )
    mark_built "$state_dir/pubs-pdf.sha" "$pubs_pdf_hash"
  else
    echo "→ Publications PDF up to date"
  fi
else
  rm -rf "$out_pubs"
  rm -f "$inline_bib_path"
fi

# Render + compile CV PDF via Typst
cv_typ="$out_vita/$cv_typ_name"
cv_pdf="$out_vita/$cv_pdf_name"
cv_typ_hash_args=(
  "FILE:$json_file"
  "FILE:$toolkit_root/scripts/render_typst_cv.py"
  "DIR:$out_vita/assets/profile"
  "DIR:$toolkit_root/assets/profile"
  "DIR:$assets_source_dir/logos"
  "STR:cv_typ_target=$cv_typ"
  "STR:inline_publications_requested=$inline_publications_requested"
  "STR:inline_bib_for_typst=$inline_bib_for_typst"
)
if [[ -n "$inline_bib_for_typst" ]]; then
  cv_typ_hash_args+=("FILE:$inline_bib_path")
fi
cv_typ_hash="$(calc_hash "${cv_typ_hash_args[@]}")"
if needs_rebuild "$cv_typ" "$state_dir/cv-typ.sha" "$cv_typ_hash"; then
  echo "→ Building Typst source"
  VITA_ASSETS_DIR="$assets_source_dir" \
  VITA_INLINE_PUBLICATIONS_BIB="$inline_bib_for_typst" \
  python "$toolkit_root/scripts/render_typst_cv.py" "$json_file" "$cv_typ"
  mark_built "$state_dir/cv-typ.sha" "$cv_typ_hash"
else
  echo "→ Typst source up to date"
fi

cv_pdf_hash="$(calc_hash \
  "FILE:$cv_typ" \
  "DIR:$out_vita/assets/profile" \
  "DIR:$out_vita/assets/logos" \
  "STR:cv_pdf_target=$cv_pdf")"
if needs_rebuild "$cv_pdf" "$state_dir/cv-pdf.sha" "$cv_pdf_hash"; then
  echo "→ Building CV PDF"
  typst compile "$cv_typ" "$cv_pdf"
  mark_built "$state_dir/cv-pdf.sha" "$cv_pdf_hash"
else
  echo "→ CV PDF up to date"
fi

echo "Done. Output in: $out_vita"
