#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_FILE="${ROOT_DIR}/runtime-versions.json"
DOCKERFILE="${ROOT_DIR}/Dockerfile"
NODE_RELEASES_URL="https://nodejs.org/download/release/index.json"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

if [[ ! -f "$VERSIONS_FILE" ]]; then
  echo "error: runtime versions file not found at $VERSIONS_FILE" >&2
  exit 1
fi

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "error: Dockerfile not found at $DOCKERFILE" >&2
  exit 1
fi

current_major="$(jq -r '.node_major' "$VERSIONS_FILE")"
if [[ -z "$current_major" || "$current_major" == "null" ]]; then
  echo "error: could not determine current node_major from $VERSIONS_FILE" >&2
  exit 1
fi

latest_major="$(
  curl --proto '=https' --tlsv1.2 -fsSL "$NODE_RELEASES_URL" \
    | jq -r '
        [
          .[]
          | select(.lts != false)
          | .version
          | ltrimstr("v")
          | split(".")[0]
          | tonumber
        ]
        | max
        | tostring
      '
)"

if [[ -z "$latest_major" || "$latest_major" == "null" ]]; then
  echo "error: could not determine latest Node.js LTS major" >&2
  exit 1
fi

if [[ "$latest_major" == "$current_major" ]]; then
  echo "Node.js is already pinned to the latest LTS major: $current_major"
  exit 0
fi

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

jq --arg value "$latest_major" '.node_major = $value' "$VERSIONS_FILE" > "$tmp_file"
mv "$tmp_file" "$VERSIONS_FILE"

sed -i "s/^FROM node:[0-9][0-9]*-alpine AS base/FROM node:${latest_major}-alpine AS base/" "$DOCKERFILE"

echo "Updated Node.js LTS major: ${current_major} -> ${latest_major}"

