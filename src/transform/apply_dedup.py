#!/usr/bin/env python3
"""Apply the weball double-count dedup (methodology §8.15).

The FEC weball file repeats the identical `TTL_INDIV_CONTRIB` under both
a chamber-switcher's House and Senate candidate IDs in the same cycle —
one principal committee's summary reported under two IDs. The correction
record is `data/source/dedup-applied.json`: 90 (person, cycle) groups across 32
persons, $451,776,015.34 in total. Each entry records the judgment call
already made (which ID's copy to keep, which to drop, and why); this
script APPLIES those decisions as data. It does NOT re-derive them:
re-deriving would re-open the per-group judgment calls (election-result
`W` marker, chamber after the cycle, shared-committee designation,
first-House-ID fallback) that `research/verification-log.md` documents.

What it does, per dedup entry (person, cycle, kept_id, dropped_ids,
amount):
- In `money_per_cycle.json`: the dropped copy's `individual` is zeroed
  (`'0.00'`); the kept copy is left untouched. AIPAC/corporate values are
  never touched (pas2 is transaction-level; the per-ID amounts differ).
  Guard: the kept entry's `individual` must equal the recorded amount,
  and each dropped entry must currently hold the recorded amount (fresh
  pull) or already be `'0.00'` (already applied) — anything else fails
  loudly instead of silently mis-applying.
- In `money_pas2_weball.csv`: the person's
  `individual_contribution_total_career` is recomputed as the sum of the
  (deduped) per-cycle `individual` values. Guard: the recomputed value
  must differ from the current value by exactly the person's dedup total
  (fresh pull) or by $0.00 (already applied) — anything else fails.
- Writes `data/intermediate/dedup-notes.json`: {person_key: note}, the per-person
  correction note the merge appends to `data_notes` (space-separated,
  after the UDP note):
  `Individual total corrected Nov 12, 2026 (verification): FEC weball
  repeats the identical TTL_INDIV_CONTRIB under both House and Senate
  candidate IDs in <cycles>; counted once per cycle (dedup $<total>).
  AIPAC/corporate columns unaffected (transaction-level).`
  Cycles are sorted ascending, joined with `, `; the total is the sum of
  the person's dedup amounts, formatted without thousands separators.

Idempotent: re-running on already-deduped files changes nothing (the
dropped entries are already `'0.00'`, the pas2 totals already match).
Two $0.00 groups (Markey 1986, Stutzman 2018) are not in the record —
they change nothing — and the 158 groups with unequal same-cycle amounts
are genuinely different money and were never deduped.
"""
import csv, json
from collections import defaultdict
from decimal import Decimal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']

dedup = json.load(open(ROOT / CFG['paths']['dedup_applied']))
mpc = json.load(open(ROOT / CFG['paths']['money_per_cycle']))
with open(ROOT / CFG['paths']['money_pas2_weball'], newline='') as f:
    pas2_rows = list(csv.DictReader(f))
    pas2_fields = pas2_rows[0].keys() if pas2_rows else []
pas2 = {r['person_key']: r for r in pas2_rows}

by_person = defaultdict(list)
for e in dedup:
    by_person[e['person_key']].append(e)

notes = {}
n_zeroed = n_already = 0
for pk, entries in sorted(by_person.items()):
    if pk not in mpc:
        raise SystemExit(f'dedup-applied.json has unknown person_key {pk}')
    person_entries = mpc[pk]['per_cycle']
    by_cycle_id = {(e['cycle'], e['candidate_id']): e for e in person_entries}
    total = Decimal('0')
    cycles = set()
    for e in entries:
        cy = e['cycle']
        cycles.add(cy)
        amount = e['amount']
        total += Decimal(amount)
        kept = by_cycle_id.get((cy, e['kept_id']))
        if kept is None:
            raise SystemExit(f"{e['name']} {cy}: kept entry {e['kept_id']} not in money_per_cycle.json")
        if kept['individual'] != amount:
            raise SystemExit(f"{e['name']} {cy}: kept entry individual {kept['individual']} != recorded amount {amount}")
        for did in e['dropped_ids']:
            dropped = by_cycle_id.get((cy, did))
            if dropped is None:
                raise SystemExit(f"{e['name']} {cy}: dropped entry {did} not in money_per_cycle.json")
            if dropped['individual'] == amount:
                dropped['individual'] = '0.00'
                n_zeroed += 1
            elif dropped['individual'] == '0.00':
                n_already += 1  # already applied
            else:
                raise SystemExit(f"{e['name']} {cy}: dropped entry {did} individual "
                                 f"{dropped['individual']} != recorded amount {amount} or '0.00'")
    # Recompute the pas2 career individual from the deduped per-cycle values.
    recomputed = sum((Decimal(e['individual']) for e in person_entries), Decimal('0'))
    current = Decimal(pas2[pk]['individual_contribution_total_career'])
    diff = current - recomputed
    if diff != Decimal('0') and diff != total:
        raise SystemExit(f"{pk}: pas2 individual ${current} vs recomputed ${recomputed} "
                         f"(diff ${diff} != dedup total ${total})")
    pas2[pk]['individual_contribution_total_career'] = f'{recomputed:.2f}'
    cycles_str = ', '.join(str(c) for c in sorted(cycles))
    notes[pk] = (f'Individual total corrected Nov 12, 2026 (verification): FEC weball repeats '
                 f'the identical TTL_INDIV_CONTRIB under both House and Senate candidate IDs in '
                 f'{cycles_str}; counted once per cycle (dedup ${total:.2f}). AIPAC/corporate '
                 f'columns unaffected (transaction-level).')
    if any(e.get('extend_to_columns_6_9') for e in entries):
        # Curtis 2024 extension: the dropped copy is also zeroed for the
        # topline columns (see the recorded flag on the dedup entry).
        notes[pk] += (' Topline extension (Nov 12, 2026): the dropped 2024 House copy '
                      '(H8UT03238) is also zeroed for total receipts, transfers from/to '
                      'authorized committees, and total disbursements — kept-minus-dropped is '
                      '$107,207.83 exactly on receipts, transfers-from-auth, and disbursements, '
                      'and the dropped transfers-to is $3,300.00; the dropped row is a strict '
                      'subset of the kept Senate row.')

with open(ROOT / CFG['paths']['money_per_cycle'], 'w') as f:
    json.dump(mpc, f, indent=1)
print(f"wrote {CFG['paths']['money_per_cycle']} "
      f"({n_zeroed} dropped copies zeroed, {n_already} already zero)")

with open(ROOT / CFG['paths']['money_pas2_weball'], 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(pas2_fields))
    w.writeheader()
    w.writerows(pas2_rows)
print(f"wrote {CFG['paths']['money_pas2_weball']} ({len(pas2_rows)} rows)")

with open(ROOT / CFG['paths']['dedup_notes'], 'w') as f:
    json.dump(notes, f, indent=1)
print(f"wrote {CFG['paths']['dedup_notes']} ({len(notes)} persons, "
      f"${sum(Decimal(e['amount']) for e in dedup):,.2f} corrected across {len(dedup)} groups)")
