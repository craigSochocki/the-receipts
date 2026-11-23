#!/usr/bin/env bash
# Stage a PINNED FEC bulk snapshot under data/raw/.
#
# Usage: ./fetch_snapshot.sh [tag]
#   tag defaults to the snapshot the committed baseline was recorded from
#   (`_snapshot` in data/source/baseline.json), e.g. fec-bulk-2026-11-22.
#
# Why: the FEC updates its bulk files in place, so a live download
# (./download_bulk.sh) is a different input every day. Snapshots are
# immutable GitHub Releases made by the "FEC snapshot" workflow
# (.github/workflows/fec-snapshot.yml): the raw files exactly as the FEC
# served them, a SHA256SUMS, and a PROVENANCE.tsv (URL + Last-Modified).
# This script downloads one, verifies EVERY checksum, extracts it into
# the layout src/rebuild.py expects, and writes data/raw/SNAPSHOT so the
# rebuild can prove which inputs it ran on.
#
# Offline: SNAPSHOT_DIR=/path/with/the/three/release/assets ./fetch_snapshot.sh
#
# To accept a NEWER snapshot: ./fetch_snapshot.sh <new tag>, then
# `python3 src/rebuild.py --rebaseline`, then review the baseline diff.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW="$ROOT/data/raw"
REPO="${RECEIPTS_REPO:-craigSochocki/the-receipts}"
TAG="${1:-$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['_snapshot'])" "$ROOT/data/source/baseline.json")}"
URL="https://github.com/$REPO/releases/download/$TAG"
DATE="${TAG#fec-bulk-}"

if [ -f "$RAW/SNAPSHOT" ] && [ "$(cat "$RAW/SNAPSHOT")" = "$TAG" ]; then
  echo "data/raw already holds $TAG — nothing to do."
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for f in "fec-bulk-$DATE.tar" SHA256SUMS PROVENANCE.tsv; do
  if [ -n "${SNAPSHOT_DIR:-}" ]; then
    cp "$SNAPSHOT_DIR/$f" "$TMP/$f"   # already-downloaded release assets
  else
    curl -L --fail --retry 3 --retry-delay 5 -o "$TMP/$f" "$URL/$f"
  fi
done

# Start clean: a half-staged or live-downloaded data/raw must never be
# mistaken for the snapshot.
rm -rf "$RAW/weball" "$RAW/cm" "$RAW/pas2" "$RAW/ie" "$RAW/SNAPSHOT"
mkdir -p "$RAW"
tar -xf "$TMP/fec-bulk-$DATE.tar" -C "$RAW"
(cd "$RAW" && sha256sum -c --quiet "$TMP/SHA256SUMS")
cp "$TMP/SHA256SUMS" "$TMP/PROVENANCE.tsv" "$RAW/"

SKIP_DOWNLOAD=1 "$ROOT/download_bulk.sh" > /dev/null
echo "$TAG" > "$RAW/SNAPSHOT"
echo "Staged $TAG under $RAW (checksums verified)."
echo "Rebuild with: python3 src/rebuild.py"
