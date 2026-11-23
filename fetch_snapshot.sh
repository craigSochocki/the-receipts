#!/usr/bin/env bash
# Stage pinned FEC snapshots (GitHub Releases) under data/raw/, verifying
# every checksum.
#
# Usage: ./fetch_snapshot.sh            every snapshot data/source/baseline.json pins
#        ./fetch_snapshot.sh <tag>      one snapshot: fec-bulk-<date> or fec-candidates-<date>
#        SNAPSHOT_DIR=<dir with the release assets> ./fetch_snapshot.sh <tag>   (offline)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW="$ROOT/data/raw"
REPO="${RECEIPTS_REPO:-craigSochocki/the-receipts}"

pinned_tags() {
  python3 -c "import json,sys; b=json.load(open(sys.argv[1])); print(' '.join(b[k] for k in ('_snapshot', '_candidates_snapshot') if k in b))" \
    "$ROOT/data/source/baseline.json"
}

stage() {
  local tag="$1" set marker
  case "$tag" in
    fec-bulk-*)       set=bulk;       marker="$RAW/SNAPSHOT";    dirs="weball cm pas2 ie" ;;
    fec-candidates-*) set=candidates; marker="$RAW/cn/SNAPSHOT"; dirs="cn" ;;
    *) echo "unknown snapshot tag: $tag" >&2; exit 1 ;;
  esac
  if [ -f "$marker" ] && [ "$(cat "$marker")" = "$tag" ]; then
    echo "data/raw already holds $tag — nothing to do."
    return
  fi

  local tmp
  tmp="$(mktemp -d)"
  for f in "$tag.tar" SHA256SUMS PROVENANCE.tsv; do
    if [ -n "${SNAPSHOT_DIR:-}" ]; then
      cp "$SNAPSHOT_DIR/$f" "$tmp/$f"
    else
      curl -L --fail --retry 3 --retry-delay 5 -o "$tmp/$f" \
        "https://github.com/$REPO/releases/download/$tag/$f"
    fi
  done

  for d in $dirs; do rm -rf "${RAW:?}/$d"; done
  rm -f "$marker" "$(dirname "$marker")/PROVENANCE.tsv"
  mkdir -p "$RAW"
  tar -xf "$tmp/$tag.tar" -C "$RAW"
  (cd "$RAW" && sha256sum -c --quiet "$tmp/SHA256SUMS")
  SET="$set" SKIP_DOWNLOAD=1 "$ROOT/download_bulk.sh" > /dev/null
  cp "$tmp/PROVENANCE.tsv" "$(dirname "$marker")/PROVENANCE.tsv"
  echo "$tag" > "$marker"
  rm -rf "$tmp"
  echo "Staged $tag (checksums verified)."
}

for tag in ${1:-$(pinned_tags)}; do
  stage "$tag"
done
