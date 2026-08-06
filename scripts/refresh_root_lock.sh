#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ ! -f package.json ]]; then
  echo "package.json not found in $ROOT_DIR" >&2
  exit 1
fi

echo "Refreshing root package-lock.json"
npm install --package-lock-only --ignore-scripts
