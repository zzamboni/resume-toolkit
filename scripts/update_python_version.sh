#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_FILE="${ROOT_DIR}/runtime-versions.json"
MISE_TOML="${ROOT_DIR}/mise.toml"
PYTHON_RELEASES_URL="https://peps.python.org/api/python-releases.json"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq
require_cmd sort

if [[ ! -f "$VERSIONS_FILE" ]]; then
  echo "error: runtime versions file not found at $VERSIONS_FILE" >&2
  exit 1
fi

if [[ ! -f "$MISE_TOML" ]]; then
  echo "error: mise.toml not found at $MISE_TOML" >&2
  exit 1
fi

current_version="$(jq -r '.python_version' "$VERSIONS_FILE")"
if [[ -z "$current_version" || "$current_version" == "null" ]]; then
  echo "error: could not determine current python_version from $VERSIONS_FILE" >&2
  exit 1
fi

releases_json="$(curl --proto '=https' --tlsv1.2 -fsSL "$PYTHON_RELEASES_URL")"

latest_branch="$(
  printf '%s\n' "$releases_json" \
    | jq -r '
        .metadata
        | to_entries
        | map(select(.key | test("^3\\.[0-9]+$")))
        | map(select(.value.status == "bugfix" or .value.status == "security"))
        | max_by(.key | split(".")[1] | tonumber)
        | .key
      '
)"

if [[ -z "$latest_branch" || "$latest_branch" == "null" ]]; then
  echo "error: could not determine latest supported Python 3 branch" >&2
  exit 1
fi

latest_version="$(
  printf '%s\n' "$releases_json" \
    | jq -r --arg branch "$latest_branch" '
        .releases[$branch]
        | map(select(.state == "actual"))
        | map(.stage | split(" ")[0])
        | map(select(test("^[0-9]+\\.[0-9]+\\.[0-9]+$")))
        | .[]
      ' \
    | sort -V \
    | tail -n 1
)"

if [[ -z "$latest_version" || "$latest_version" == "null" ]]; then
  echo "error: could not determine latest supported Python release for branch ${latest_branch}" >&2
  exit 1
fi

if [[ "$latest_version" == "$current_version" ]]; then
  echo "Python is already pinned to the latest supported version: $current_version"
  exit 0
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

jq --arg value "$latest_version" '.python_version = $value' "$VERSIONS_FILE" > "$tmp_file"
mv "$tmp_file" "$VERSIONS_FILE"

sed -i "s/^python = \".*\"$/python = \"${latest_version}\"/" "$MISE_TOML"

echo "Updated Python version: ${current_version} -> ${latest_version}"
