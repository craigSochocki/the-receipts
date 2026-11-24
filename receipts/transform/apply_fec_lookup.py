#!/usr/bin/env python3
"""Apply the FEC-ID enrichment to the roster built by build_roster.py.

`build_roster.py` writes `roster_intermediate.json` with FEC candidate IDs
only where the source roster already had them. The remaining IDs come from
two recorded sources, applied here in order:

1. `fec_lookup_results.json` — the OpenFEC API lookup (`fec_lookup.py`).
   Status `found` sets the ID and `_fec_source` to `fec-api-<current cycle>`;
   status `found-manual` marks an ID the API could not match on its own (a
   legal-name variant or a party label) that was matched by hand, and sets
   `_fec_source` to `fec-api-<current cycle>-manual`. Any other status
   (`not_found`, `ambiguous`, `http_error`, `error`) leaves the row
   untouched: no ID is ever guessed.
2. `manual_roster_notes.json` — note appends recorded alongside the
   enrichment, appended to the row's `notes` once (an append already
   present is skipped).

Writes `roster_intermediate.json` enriched in place, and `roster.json`: the
same rows without the `_`-prefixed working fields, which is what the store
reads. Re-running applies nothing twice.
"""

import json

from receipts.common.files import read_json
from receipts.common.settings import settings

SOURCE_BY_STATUS = {'found': 'fec-api-{cycle}', 'found-manual': 'fec-api-{cycle}-manual'}


def apply_lookup_results(rows, results, cycle):
    """Set each found ID on its roster row; (found, found by hand, skipped) counts."""
    by_key = {r['person_key']: r for r in rows}
    counts = {'found': 0, 'found-manual': 0, 'skipped': 0}
    for person_key, result in results.items():
        row = by_key.get(person_key)
        if row is None:
            raise SystemExit(f'fec_lookup_results.json has unknown person_key {person_key}')
        source = SOURCE_BY_STATUS.get(result['status'])
        if source is None:
            counts['skipped'] += 1
            continue
        row['fec_candidate_ids'] = [result['value']]
        row['_fec_source'] = source.format(cycle=cycle)
        counts[result['status']] += 1
    return counts


def apply_note_appends(rows, notes):
    """Append each recorded note once; (applied, already present) counts."""
    by_key = {r['person_key']: r for r in rows}
    applied = already = 0
    for person_key, append in notes.items():
        row = by_key.get(person_key)
        if row is None:
            raise SystemExit(f'manual_roster_notes.json has unknown person_key {person_key}')
        current = row.get('notes') or ''
        if current.endswith(append):
            already += 1
            continue
        row['notes'] = current + append
        applied += 1
    return applied, already


def public_roster(rows):
    """The roster the store reads: no `_` working fields, `fec_candidate_ids` last, by name.

    Field order, sort and ensure_ascii=False in write() reproduce the committed
    roster.json byte for byte.
    """
    public = []
    for row in rows:
        kept = {k: v for k, v in row.items() if not k.startswith('_')}
        kept['fec_candidate_ids'] = kept.pop('fec_candidate_ids')
        public.append(kept)
    return sorted(public, key=lambda r: (r['last_name'].lower(), r['first_name'].lower()))


def write(rows, public):
    paths = settings().paths
    with open(paths.roster_intermediate, 'w') as f:
        json.dump(rows, f, indent=1)
    print(f'wrote {settings().relative(paths.roster_intermediate)} ({len(rows)} rows)')
    with open(paths.roster, 'w') as f:
        json.dump(public, f, indent=1, ensure_ascii=False)
    print(f'wrote {settings().relative(paths.roster)} ({len(public)} rows, _-fields removed)')


def main():
    """Apply the recorded FEC lookup results and note appends to the roster."""
    paths = settings().paths
    rows = read_json(paths.roster_intermediate)
    counts = apply_lookup_results(
        rows, read_json(paths.fec_lookup_results), settings().cycles.current
    )
    print(
        f'fec lookup results: {counts["found"]} found, {counts["found-manual"]} found-manual, '
        f'{counts["skipped"]} skipped (no ID)'
    )
    applied, already = apply_note_appends(rows, read_json(paths.manual_roster_notes))
    print(f'manual note appends: {applied} applied, {already} already present')
    write(rows, public_roster(rows))


if __name__ == '__main__':
    main()
