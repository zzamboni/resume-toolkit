#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_FILE="${ROOT_DIR}/typst-package-versions.json"
PACKAGES_API_BASE="https://api.github.com/repos/typst/packages/contents/packages/preview"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

latest_package_version() {
  local package_name="$1"
  curl --proto '=https' --tlsv1.2 -fsSL "${PACKAGES_API_BASE}/${package_name}" \
    | jq -r '.[].name' \
    | sort -V \
    | tail -n 1
}

require_cmd curl
require_cmd jq
require_cmd sort

if [[ ! -f "$VERSIONS_FILE" ]]; then
  echo "error: typst package versions file not found at $VERSIONS_FILE" >&2
  exit 1
fi

mapfile -t package_names < <(jq -r 'keys[]' "$VERSIONS_FILE")

if [[ "${#package_names[@]}" -eq 0 ]]; then
  echo "No Typst packages configured in $VERSIONS_FILE"
  exit 0
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

cp "$VERSIONS_FILE" "$tmp_file"

updated=0
for package_name in "${package_names[@]}"; do
  current_version="$(jq -r --arg name "$package_name" '.[$name]' "$tmp_file")"
  latest_version="$(latest_package_version "$package_name")"

  if [[ -z "$latest_version" || "$latest_version" == "null" ]]; then
    echo "error: could not determine latest version for Typst package '$package_name'" >&2
    exit 1
  fi

  if [[ "$latest_version" == "$current_version" ]]; then
    echo "${package_name} is already pinned to the latest version: ${current_version}"
    continue
  fi

  jq --arg name "$package_name" --arg version "$latest_version" '.[$name] = $version' \
    "$tmp_file" > "${tmp_file}.new"
  mv "${tmp_file}.new" "$tmp_file"
  echo "Updated ${package_name}: ${current_version} -> ${latest_version}"
  updated=1
done

if [[ "$updated" == "0" ]]; then
  echo "All Typst package versions are already up to date"
  exit 0
fi

mv "$tmp_file" "$VERSIONS_FILE"
