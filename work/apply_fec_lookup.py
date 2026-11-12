#!/usr/bin/env python3
"""Apply the FEC-ID enrichment to the roster built by build_roster.py.

`build_roster.py` writes `roster_intermediate.json` with FEC candidate IDs
only where the source roster already had them. The remaining IDs come from
two recorded sources, applied here in order:

1. `fec_lookup_results.json` — the OpenFEC API lookup (`fec_lookup.py`).
   Entries with status `found` set the ID and `_fec_source` to
   `fec-api-<current cycle>`; entries with status `found-manual` are the
   seven IDs the API could not match on its own (name variants: legal names
   like Margaret Flanagan / James Morris Kingston / Jacob Johnson /
   Robert J. Harvie, DFL party labels) and were matched by hand — they set
   `_fec_source` to `fec-api-<current cycle>-manual`. Entries with any
   other status (`not_found`, `ambiguous`, `http_error`, `error`) leave
   the row untouched: no ID is ever guessed.
2. `manual_roster_notes.json` — the seven note appends recorded alongside
   the enrichment (the `found-manual` rows' filing-name/party notes, plus
   Alan Armstrong's "no FEC candidate ID found" note). Appended to the
   row's `notes` field, once (re-running is a no-op: an append already
   present is skipped).

Outputs (both `json.dump(..., indent=1)`, same as the scripts that wrote
the committed files):
- `roster_intermediate.json` — enriched, in place (this is the file the
  committed roster was built from: `build_roster.py` output + these
  enrichments, nothing else).
- `roster.json` — the same rows minus every `_`-prefixed key (`_bioguide`,
  `_fec_source`, `_nickname`, `_official`). This is what `pull_money.py`
  and `compute_opposition.py` read.

Idempotent: re-running applies nothing twice (IDs are set, not appended;
note appends already present are skipped).
"""
import json

from config import load_config

CFG = load_config()
ROOT = CFG['_root']
WORK = str(ROOT / CFG['paths']['work'])
CURRENT = CFG['cycles']['current']

rows = json.load(open(ROOT / CFG['paths']['roster_intermediate']))
by_key = {r['person_key']: r for r in rows}

# ---------- 1. FEC lookup results ----------
results = json.load(open(ROOT / CFG['paths']['fec_lookup_results']))
n_found = n_manual = n_skipped = 0
for pk, res in results.items():
    row = by_key.get(pk)
    if row is None:
        raise SystemExit(f'fec_lookup_results.json has unknown person_key {pk}')
    status = res['status']
    if status == 'found':
        row['fec_candidate_ids'] = [res['value']]
        row['_fec_source'] = f'fec-api-{CURRENT}'
        n_found += 1
    elif status == 'found-manual':
        row['fec_candidate_ids'] = [res['value']]
        row['_fec_source'] = f'fec-api-{CURRENT}-manual'
        n_manual += 1
    else:
        # not_found / ambiguous / http_error / error: no ID, leave the row.
        n_skipped += 1
print(f'fec lookup results: {n_found} found, {n_manual} found-manual, '
      f'{n_skipped} skipped (no ID)')

# ---------- 2. Manual note appends ----------
notes = json.load(open(ROOT / CFG['paths']['manual_roster_notes']))
n_notes = n_already = 0
for pk, append in notes.items():
    row = by_key.get(pk)
    if row is None:
        raise SystemExit(f'manual_roster_notes.json has unknown person_key {pk}')
    cur = row.get('notes') or ''
    if cur.endswith(append):
        n_already += 1
        continue
    row['notes'] = cur + append
    n_notes += 1
print(f'manual note appends: {n_notes} applied, {n_already} already present')

# ---------- Outputs ----------
with open(ROOT / CFG['paths']['roster_intermediate'], 'w') as f:
    json.dump(rows, f, indent=1)
print(f'wrote {CFG["paths"]["roster_intermediate"]} ({len(rows)} rows)')

# roster.json: the same rows minus every `_`-prefixed key (`_bioguide`,
# `_fec_source`, `_nickname`, `_official`), with `fec_candidate_ids`
# moved last, sorted case-insensitively by (last_name, first_name), and
# dumped with ensure_ascii=False (literal non-ASCII, e.g. Barragán).
# All four choices reproduce the committed roster.json byte-for-byte;
# they are load-bearing, not cosmetic — see the byte-identity check in
# rebuild verification.
stripped = []
for r in rows:
    d = {k: v for k, v in r.items() if not k.startswith('_')}
    d['fec_candidate_ids'] = d.pop('fec_candidate_ids')
    stripped.append(d)
stripped.sort(key=lambda r: (r['last_name'].lower(), r['first_name'].lower()))
with open(ROOT / CFG['paths']['roster'], 'w') as f:
    json.dump(stripped, f, indent=1, ensure_ascii=False)
print(f'wrote {CFG["paths"]["roster"]} ({len(stripped)} rows, _-fields removed)')
