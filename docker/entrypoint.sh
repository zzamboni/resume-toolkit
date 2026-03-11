#!/usr/bin/env bash
set -euo pipefail

export VITA_TOOLKIT_ROOT="/opt/vita-toolkit"
export VITA_WORKDIR="${VITA_WORKDIR:-/work}"
export VITA_SERVE_PORT="${VITA_SERVE_PORT:-8080}"
export PATH="$VITA_TOOLKIT_ROOT/.venv/bin:$VITA_TOOLKIT_ROOT/node_modules/.bin:$PATH"

usage() {
  cat <<'USAGE'
Usage:
  vita-pipeline [build|pipeline] <resume.json> [bibfiles...] [--out <dir>] [--pubs-url <url>] [--watch] [--serve]
  vita-pipeline fetch-logos <resume.json> [--overwrite] [--dry-run] [--token <token>]
  vita-pipeline update-certs <username> <resume.json> [--include-expired] [--include-non-cert-badges] [--sort <date_desc|date_asc|name>]
  vita-pipeline update-pub-numbers <resume.json> [--html <path>]
  vita-pipeline tasks
  vita-pipeline version
  vita-pipeline shell
USAGE
}

show_tasks() {
  cat <<'TASKS'
build              Run CV + publications pipeline
fetch-logos        Fetch company/education logos from JSON resume into /work assets
update-certs       Update certificates from Credly
update-pub-numbers Update publication reference numbers in JSON resume
version            Show toolkit and runtime versions
TASKS
}

resolve_work_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$VITA_WORKDIR/$path"
  fi
}

run_pipeline() {
  local watch=0
  local serve=0
  local resume=""
  local out=""
  local pubs_url=""
  local -a bibs=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --watch) watch=1; shift ;;
      --serve) serve=1; watch=1; shift ;;
      --out) out="$2"; shift 2 ;;
      --pubs-url) pubs_url="$2"; shift 2 ;;
      -h|--help)
        usage
        return 0
        ;;
      --*)
        echo "Unknown option: $1" >&2
        usage
        return 1
        ;;
      *)
        if [[ -z "$resume" ]]; then
          resume="$1"
        else
          bibs+=("$1")
        fi
        shift
        ;;
    esac
  done

  if [[ -z "$resume" ]]; then
    echo "Missing resume JSON file" >&2
    usage
    return 1
  fi

  local -a pipeline_args=(--json "$resume")
  for bib in "${bibs[@]}"; do
    pipeline_args+=(--bib "$bib")
  done
  if [[ -n "$out" ]]; then
    pipeline_args+=(--out "$out")
  fi
  if [[ -n "$pubs_url" ]]; then
    pipeline_args+=(--pubs-url "$pubs_url")
  fi

  local out_base="$out"
  if [[ -z "$out_base" ]]; then
    out_base="build/$(basename "${resume%.json}")"
  fi

  cd "$VITA_WORKDIR"

  if [[ "$serve" == "1" ]]; then
    local server_pid=""
    mkdir -p "$out_base"
    echo "========================================================="
    echo "→ Serving $out_base at http://localhost:$VITA_SERVE_PORT"
    echo "========================================================="
    python3 -m http.server "$VITA_SERVE_PORT" --bind 0.0.0.0 --directory "$out_base" >/dev/null 2>&1 &
    server_pid=$!
    trap 'if [[ -n "${server_pid:-}" ]]; then kill "$server_pid" >/dev/null 2>&1 || true; fi' EXIT INT TERM
  fi

  if [[ "$watch" == "1" ]]; then
    if ! command -v watchexec >/dev/null 2>&1; then
      echo "watchexec not found in PATH" >&2
      return 1
    fi
    export DEV_RELOAD=1
    local resume_watch
    resume_watch="$(resolve_work_path "$resume")"
    local -a watch_args=(--watch "$resume_watch")
    local bib
    for bib in "${bibs[@]}"; do
      watch_args+=(--watch "$(resolve_work_path "$bib")")
    done
    (
      cd "$VITA_TOOLKIT_ROOT"
      exec watchexec --restart \
        "${watch_args[@]}" \
        -- ./scripts/run_pipeline.sh "${pipeline_args[@]}"
    )
  else
    (
      cd "$VITA_TOOLKIT_ROOT"
      exec ./scripts/run_pipeline.sh "${pipeline_args[@]}"
    )
  fi
}

run_fetch_logos() {
  local workdir="$VITA_WORKDIR"
  local resume="${1:-}"
  if [[ -z "$resume" ]]; then
    echo "Missing resume JSON file" >&2
    usage
    return 1
  fi
  shift

  local resume_path
  resume_path="$(resolve_work_path "$resume")"
  local logos_dir="$workdir/assets/logos"
  mkdir -p "$logos_dir"

  local -a args=("$resume_path" "--logos-dir" "$logos_dir")
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --overwrite|--dry-run)
        args+=("$1")
        shift
        ;;
      --token)
        args+=("$1" "$2")
        shift 2
        ;;
      -h|--help)
        usage
        return 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        return 1
        ;;
    esac
  done

  cd "$VITA_TOOLKIT_ROOT"
  exec python3 scripts/fetch_company_logos.py "${args[@]}"
}

run_update_certs() {
  local username="${1:-}"
  local resume="${2:-}"
  if [[ -z "$username" || -z "$resume" ]]; then
    echo "Missing username or resume JSON file" >&2
    usage
    return 1
  fi
  shift 2

  local resume_path
  resume_path="$(resolve_work_path "$resume")"
  local -a args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --include-expired|--include-non-cert-badges)
        args+=("$1")
        shift
        ;;
      --sort)
        args+=("$1" "$2")
        shift 2
        ;;
      -h|--help)
        usage
        return 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        return 1
        ;;
    esac
  done

  cd "$VITA_TOOLKIT_ROOT"
  exec python3 scripts/update-certs-from-credly.py "${args[@]}" "$username" "$resume_path"
}

run_update_pub_numbers() {
  local resume="${1:-}"
  if [[ -z "$resume" ]]; then
    echo "Missing resume JSON file" >&2
    usage
    return 1
  fi
  shift

  local resume_path
  resume_path="$(resolve_work_path "$resume")"
  local html=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --html)
        html="$(resolve_work_path "$2")"
        shift 2
        ;;
      -h|--help)
        usage
        return 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        return 1
        ;;
    esac
  done

  if [[ -z "$html" ]]; then
    local stem
    stem="$(basename "${resume_path}" .json)"
    html="$VITA_WORKDIR/build/$stem/vita/publications/index.html"
  fi

  cd "$VITA_TOOLKIT_ROOT"
  exec python3 scripts/update_pub_numbers.py --json "$resume_path" --html "$html"
}

if [[ $# -eq 0 ]]; then
  show_tasks
  exit 0
fi

case "$1" in
  build|pipeline)
    shift
    run_pipeline "$@"
    ;;
  fetch-logos)
    shift
    run_fetch_logos "$@"
    ;;
  update-certs)
    shift
    run_update_certs "$@"
    ;;
  update-pub-numbers)
    shift
    run_update_pub_numbers "$@"
    ;;
  tasks)
    show_tasks
    ;;
  shell|bash)
    cd "$VITA_TOOLKIT_ROOT"
    exec bash "${@:2}"
    ;;
  help|-h|--help)
    usage
    ;;
  version)
    toolkit_version="${VITA_TOOLKIT_VERSION:-}"
    if [[ -z "$toolkit_version" || "$toolkit_version" == "dev" || "$toolkit_version" == "unknown" ]]; then
      if [[ -f "$VITA_TOOLKIT_ROOT/VERSION" ]]; then
        toolkit_version="$(tr -d '[:space:]' < "$VITA_TOOLKIT_ROOT/VERSION")"
      else
        toolkit_version="unknown"
      fi
    fi
    echo "resume-toolkit ${toolkit_version}"
    echo "node $(node --version)"
    echo "python $(python3 --version | awk '{print $2}')"
    echo "typst $(typst --version | awk '{print $2}')"
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
