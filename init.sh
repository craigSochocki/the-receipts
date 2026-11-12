#!/usr/bin/env bash
# First-time setup for The Receipts.
#
# Usage: ./init.sh [--skip-download] [--skip-rebuild] [--skip-site]
#   1. Creates .venv (if missing) and installs the dependencies from
#      requirements.txt (PyYAML + pandas). Everything after this runs
#      with .venv/bin/python.
#   2. Stages the FEC bulk files via ./download_bulk.sh (~315 MB down,
#      ~2 GB on disk; skips oppexp, which no script reads).
#   3. Runs the full rebuild — must reproduce the committed dataset
#      byte-identically, all 93 audits passing.
#   4. Regenerates + verifies the static site (docs/index.html).
#   Idempotent: safe to re-run; downloads resume, the venv is reused.
#   Preview the site: python3 -m http.server --directory docs 8000
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SKIP_DOWNLOAD=0; SKIP_REBUILD=0; SKIP_SITE=0
for arg in "$@"; do
  case "$arg" in
    --skip-download) SKIP_DOWNLOAD=1 ;;
    --skip-rebuild) SKIP_REBUILD=1 ;;
    --skip-site) SKIP_SITE=1 ;;
    *) echo "Unknown option: $arg" >&2
       echo "Usage: ./init.sh [--skip-download] [--skip-rebuild] [--skip-site]" >&2
       exit 2 ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required tool: $1" >&2; exit 1; }; }
need python3; need curl; need unzip

echo "=== 1/4 environment (.venv + PyYAML) ==="
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv || { echo "python3 -m venv failed — install the python3-venv package, then re-run." >&2; exit 1; }
fi
.venv/bin/pip install -q -r requirements.txt

if ! command -v node >/dev/null 2>&1; then
  echo "Note: node not found — the site verifier will skip the runtime smoke test."
fi

if [ "$SKIP_DOWNLOAD" = 0 ]; then
  echo "=== 2/4 bulk data (./download_bulk.sh) ==="
  ./download_bulk.sh
fi

if [ "$SKIP_REBUILD" = 0 ]; then
  echo "=== 3/4 rebuild (src/rebuild.py) ==="
  .venv/bin/python src/rebuild.py
fi

if [ "$SKIP_SITE" = 0 ]; then
  echo "=== 4/4 static site (src/site/) ==="
  .venv/bin/python src/site/build_site.py
  .venv/bin/python src/site/verify_site.py
fi

echo
echo "Setup complete."
echo "Preview the site: python3 -m http.server --directory docs 8000"
