#!/usr/bin/env bash
set -euo pipefail

IMAGE="${VITA_PIPELINE_IMAGE:-ghcr.io/zzamboni/resume-toolkit:latest}"
PORT="${VITA_SERVE_PORT:-8080}"
CACHE_DIR="${VITA_PIPELINE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/vita-pipeline}"
PULL_IMAGE=0

mkdir -p "$CACHE_DIR"

PORT_ARGS=()
ENV_ARGS=()
CMD=build
ARGS=("$@")

port_in_use() {
  local port="$1"
  (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
}

usage() {
  cat <<'USAGE'
Usage:
  build-resume.sh [--pull] [build] <resume.json> [bibfiles...] [--out <dir>] [--pubs-url <url>] [--cv-url <url>] [--watch] [--serve] [--no-fetch-logos] [--token LOGODEV_TOKEN]
  build-resume.sh [--pull] fetch-logos <resume.json> [--overwrite] [--dry-run] [--token LOGODEV_TOKEN]
  build-resume.sh [--pull] update-certs <username> <resume.json> [--include-expired] [--include-non-cert-badges] [--sort <date_desc|date_asc|name>]
  build-resume.sh [--pull] update-pub-numbers <resume.json> [--html <path>]
  build-resume.sh [--pull] update-inline-pubs <resume.json> [bibfiles...]
  build-resume.sh [--pull] version

Examples:
  build-resume.sh --pull resume.json pubs.bib --watch --serve
  build-resume.sh fetch-logos resume.json --overwrite --token pk_XXXXXXXXXXXXXXX
  build-resume.sh update-certs zzamboni resume.json
  build-resume.sh update-pub-numbers resume.json
  build-resume.sh update-inline-pubs resume.json
  build-resume.sh version
USAGE
}

# Harmonize with container entrypoint commands.
ENTRYPOINT_CMDS=(
  build pipeline shell bash
  tasks version help
  fetch-logos update-certs update-pub-numbers update-inline-pubs
)

is_entrypoint_cmd() {
  local candidate="$1"
  for c in "${ENTRYPOINT_CMDS[@]}"; do
    [[ "$candidate" == "$c" ]] && return 0
  done
  return 1
}

IT_ARG="-it"

case "${1:-}" in
  --no-it)
    IT_ARG=""
    shift
    ;;
esac

while [[ "${1:-}" == "--pull" ]]; do
  PULL_IMAGE=1
  shift
done

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  "")
    usage
    exit 1
    ;;
  *)
    if is_entrypoint_cmd "$1"; then
      CMD="$1"
      ARGS=("${@:2}")
    else
      # Default behavior remains build without explicit subcommand.
      CMD=build
      ARGS=("$@")
    fi
    ;;
esac

if [[ -n "${LOGODEV_TOKEN:-}" ]]; then
  ENV_ARGS+=(-e "LOGODEV_TOKEN=$LOGODEV_TOKEN")
fi

if [[ "$PULL_IMAGE" -eq 1 ]]; then
  before_image_id="$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || true)"
  if docker pull "$IMAGE" >/dev/null; then
    after_image_id="$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || true)"
    if [[ -n "$before_image_id" && -n "$after_image_id" && "$before_image_id" != "$after_image_id" ]]; then
      echo "→ Updated image: $IMAGE"
    elif [[ -z "$before_image_id" && -n "$after_image_id" ]]; then
      echo "→ Pulled image: $IMAGE"
    fi
  else
    echo "Warning: could not pull image $IMAGE; continuing with local copy." >&2
  fi
fi

for a in "${ARGS[@]}"; do
  if [[ "$a" == "--serve" ]]; then
    while port_in_use "$PORT"; do
      ((PORT++))
    done
    PORT_ARGS=(-p "${PORT}:${PORT}")
    break
  fi
done

exec docker run --rm $IT_ARG \
  --user "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  -v "$CACHE_DIR":/opt/vita-cache \
  -w /work \
  -e HOME=/tmp \
  -e VITA_WORKDIR=/work \
  -e VITA_SERVE_PORT="$PORT" \
  -e MISE_IDIOMATIC_VERSION_FILE=false \
  "${ENV_ARGS[@]}" \
  "${PORT_ARGS[@]}" \
  "$IMAGE" \
  "$CMD" "${ARGS[@]}"
