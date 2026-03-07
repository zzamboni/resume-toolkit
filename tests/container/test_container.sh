#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-${VITA_PIPELINE_IMAGE:-zzamboni/resume-toolkit:latest}}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURES_DIR="$ROOT_DIR/tests/container/fixtures"
TMP_DIR="$(mktemp -d)"
CACHE_DIR="$TMP_DIR/cache"
WORK_DIR="$TMP_DIR/work"

cleanup() {
    local exit_code=$?
    if [[ "$exit_code" -ne 0 ]]; then
        echo "Test failed; preserving temporary directory for debugging: $TMP_DIR" >&2
        return
    fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

assert_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "error: expected file not found: $path" >&2
    exit 1
  }
}

assert_contains() {
  local path="$1"
  local pattern="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -q "$pattern" "$path" || {
      echo "error: expected pattern '$pattern' not found in $path" >&2
      exit 1
    }
  else
    grep -Eq "$pattern" "$path" || {
      echo "error: expected pattern '$pattern' not found in $path" >&2
      exit 1
    }
  fi
}

require_cmd docker
require_cmd bash

mkdir -p "$CACHE_DIR" "$WORK_DIR/fixtures"
cp "$FIXTURES_DIR/resume.json" "$WORK_DIR/fixtures/resume.json"
cp "$FIXTURES_DIR/resume-with-bibfiles.json" "$WORK_DIR/fixtures/resume-with-bibfiles.json"
cp "$FIXTURES_DIR/resume-inline-publications.json" "$WORK_DIR/fixtures/resume-inline-publications.json"
cp "$FIXTURES_DIR/resume-inline-publications-config.json" "$WORK_DIR/fixtures/resume-inline-publications-config.json"
cp "$FIXTURES_DIR/publications.bib" "$WORK_DIR/fixtures/publications.bib"

run_wrapper() {
  (
    cd "$WORK_DIR"
    export VITA_PIPELINE_IMAGE="$IMAGE"
    "$ROOT_DIR/build-resume.sh" --no-it "$@"
  )
}

echo "==> Test 1: task listing"
run_wrapper tasks >"$TMP_DIR/tasks.out"
assert_contains "$TMP_DIR/tasks.out" "^build($|[[:space:]])"
assert_contains "$TMP_DIR/tasks.out" "^fetch-logos($|[[:space:]])"
assert_contains "$TMP_DIR/tasks.out" "^update-certs($|[[:space:]])"

echo "==> Test 2: pipeline build with publications"
run_wrapper build fixtures/resume.json fixtures/publications.bib --out build/out >/dev/null

assert_file "$WORK_DIR/build/out/vita/index.html"
assert_file "$WORK_DIR/build/out/vita/resume.typ"
assert_file "$WORK_DIR/build/out/vita/resume.pdf"
assert_file "$WORK_DIR/build/out/vita/publications/index.html"
assert_file "$WORK_DIR/build/out/vita/publications/resume-pubs.pdf"
assert_file "$WORK_DIR/build/out/vita/publications/resume-pubs.bib"
assert_contains "$WORK_DIR/build/out/vita/index.html" "Example Person"
assert_contains "$WORK_DIR/build/out/vita/publications/index.html" "Example Person"

echo "==> Test 3: logo fetch dry-run wiring"
run_wrapper fetch-logos fixtures/resume.json --dry-run --token dummy >/dev/null

echo "==> Test 4: publications from JSON bibfiles"
run_wrapper build fixtures/resume-with-bibfiles.json --out build/out-from-json >/dev/null
assert_file "$WORK_DIR/build/out-from-json/vita/publications/index.html"
assert_file "$WORK_DIR/build/out-from-json/vita/publications/resume-with-bibfiles-pubs.pdf"
assert_file "$WORK_DIR/build/out-from-json/vita/publications/resume-with-bibfiles-pubs.bib"
assert_contains "$WORK_DIR/build/out-from-json/vita/publications/index.html" "Example Person"

echo "==> Test 5: inline publications in resume PDF"
run_wrapper build fixtures/resume-inline-publications.json --out build/out-inline >/dev/null
assert_file "$WORK_DIR/build/out-inline/vita/resume-inline-publications.typ"
assert_file "$WORK_DIR/build/out-inline/vita/resume-inline-publications-vita.bib"
assert_file "$WORK_DIR/build/out-inline/vita/publications/index.html"
assert_contains "$WORK_DIR/build/out-inline/vita/resume-inline-publications.typ" '#cv-publication\(bib: bibliography\("resume-inline-publications-vita\.bib"\), ref-style: "ieee", ref-full: true, key-list: \(\)\)'

echo "==> Test 6: inline publications with custom bibliography options"
run_wrapper build fixtures/resume-inline-publications-config.json --out build/out-inline-config >/dev/null
assert_file "$WORK_DIR/build/out-inline-config/vita/resume-inline-publications-config.typ"
assert_file "$WORK_DIR/build/out-inline-config/vita/resume-inline-publications-config-vita.bib"
assert_contains "$WORK_DIR/build/out-inline-config/vita/resume-inline-publications-config.typ" '#cv-publication\(bib: bibliography\("resume-inline-publications-config-vita\.bib"\), ref-style: "apa", ref-full: false, key-list: \("example2024paper",\)\)'

echo "All container tests passed."
