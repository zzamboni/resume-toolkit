#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE="${ROOT_DIR}/Dockerfile"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "error: Dockerfile not found at $DOCKERFILE" >&2
  exit 1
fi

current_version="$(sed -n 's/^ARG TYPST_VERSION=\(.*\)$/\1/p' "$DOCKERFILE" | head -n 1)"
if [[ -z "$current_version" ]]; then
  echo "error: could not determine current TYPST_VERSION from Dockerfile" >&2
  exit 1
fi

latest_version="$(
  curl --proto '=https' --tlsv1.2 -fsSL https://api.github.com/repos/typst/typst/releases/latest \
    | jq -r '.tag_name | ltrimstr("v")'
)"

if [[ -z "$latest_version" || "$latest_version" == "null" ]]; then
  echo "error: could not determine latest Typst release" >&2
  exit 1
fi

if [[ "$latest_version" == "$current_version" ]]; then
  echo "Typst is already pinned to the latest version: $current_version"
  exit 0
fi

sed -i "s/^ARG TYPST_VERSION=.*/ARG TYPST_VERSION=${latest_version}/" "$DOCKERFILE"
echo "Updated TYPST_VERSION: ${current_version} -> ${latest_version}"
