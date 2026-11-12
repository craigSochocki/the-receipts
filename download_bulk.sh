#!/usr/bin/env bash
# Stage the FEC bulk files the rebuild needs under data/raw/.
#
# Usage: ./download_bulk.sh
#   Downloads weball + cm + pas2 for every even cycle 1980-2026, plus the
#   independent-expenditure CSVs for 2022/2024/2026, then extracts them into
#   the layout src/rebuild.py expects. About 315 MB down, ~2 GB on disk.
#   Idempotent: curl resumes partial downloads (-C -), unzip -o overwrites.
#   Then run: python3 src/rebuild.py
#
#   Skips oppexp on purpose: those files are operating expenditures, not
#   independent expenditures — no script reads them and no figure uses them
#   (see research/bulk-inventory.md, "CRITICAL CORRECTION"). Set
#   INCLUDE_OPPEXP=1 to fetch them anyway (another ~573 MB down).
#
#   Overrides (for testing): CYCLES="1980 2026" SKIP_IE=1 ./download_bulk.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW="$ROOT/data/raw"
BASE="https://www.fec.gov/files/bulk-downloads"
CYCLES="${CYCLES:-$(seq 1980 2 2026)}"
IE_CYCLES="2022 2024 2026"

mkdir -p "$RAW/weball" "$RAW/cm" "$RAW/pas2" "$RAW/ie"

dl() { # dl <url> <dest>
  curl -L --fail --retry 3 --retry-delay 5 -C - -o "$2" "$1"
}

for cy in $CYCLES; do
  yy=$(printf %02d $((cy % 100)))
  dl "$BASE/$cy/weball$yy.zip" "$RAW/weball/weball$yy.zip"
  dl "$BASE/$cy/cm$yy.zip" "$RAW/cm/cm$yy.zip"
  dl "$BASE/$cy/pas2$yy.zip" "$RAW/pas2/pas2$yy.zip"
  if [ "${INCLUDE_OPPEXP:-0}" = "1" ] && [ "$cy" -ge 2004 ]; then
    mkdir -p "$RAW/oppexp"
    dl "$BASE/$cy/oppexp$yy.zip" "$RAW/oppexp/oppexp$yy.zip"
  fi
done

if [ "${SKIP_IE:-0}" != "1" ]; then
  for cy in $IE_CYCLES; do
    mkdir -p "$RAW/ie/$cy"
    dl "$BASE/$cy/independent_expenditure_$cy.csv" "$RAW/ie/$cy/independent_expenditure_$cy.csv"
  done
fi

# Extract. cm/pas2 zips all contain a generically-named file (cm.txt /
# itpas2.txt), so extracting them flat would overwrite every cycle but the
# last — they go into per-cycle folders. weball extracts flat.
for f in "$RAW"/weball/*.zip; do unzip -o -q "$f" -d "$RAW/weball/"; done
for cy in $CYCLES; do
  yy=$(printf %02d $((cy % 100)))
  mkdir -p "$RAW/cm/$cy" "$RAW/pas2/$cy"
  unzip -o -q -j "$RAW/cm/cm$yy.zip" cm.txt -d "$RAW/cm/$cy"
  unzip -o -q -j "$RAW/pas2/pas2$yy.zip" itpas2.txt -d "$RAW/pas2/$cy"
  if [ "${INCLUDE_OPPEXP:-0}" = "1" ] && [ "$cy" -ge 2004 ]; then
    mkdir -p "$RAW/oppexp/$cy"
    unzip -o -q -j "$RAW/oppexp/oppexp$yy.zip" oppexp.txt -d "$RAW/oppexp/$cy"
  fi
done

echo "Done. Staged under $RAW."
echo "Verify with: python3 src/rebuild.py"
