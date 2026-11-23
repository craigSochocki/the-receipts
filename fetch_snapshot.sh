#!/usr/bin/env bash
# Stage a pinned FEC bulk snapshot (a fec-bulk-<date> GitHub Release)
# under data/raw/, verifying every checksum.
#
# Usage: ./fetch_snapshot.sh [tag]     default: the baseline's snapshot
#        SNAPSHOT_DIR=<dir with the release assets> ./fetch_snapshot.sh   (offline)
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
    cp "$SNAPSHOT_DIR/$f" "$TMP/$f"
  else
    curl -L --fail --retry 3 --retry-delay 5 -o "$TMP/$f" "$URL/$f"
  fi
done

rm -rf "$RAW/weball" "$RAW/cm" "$RAW/pas2" "$RAW/ie" "$RAW/SNAPSHOT"
mkdir -p "$RAW"
tar -xf "$TMP/fec-bulk-$DATE.tar" -C "$RAW"
(cd "$RAW" && sha256sum -c --quiet "$TMP/SHA256SUMS")
cp "$TMP/SHA256SUMS" "$TMP/PROVENANCE.tsv" "$RAW/"

SKIP_DOWNLOAD=1 "$ROOT/download_bulk.sh" > /dev/null
echo "$TAG" > "$RAW/SNAPSHOT"
echo "Staged $TAG under $RAW (checksums verified)."
echo "Rebuild with: python3 src/rebuild.py"
