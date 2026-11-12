#!/usr/bin/env python3
"""Merge roster + money + opposition into the base dataset.

Inputs (all staged; see config.yaml `paths`):
- `roster_intermediate.json` — the enriched roster (665 rows).
- `money_per_cycle.json` + `money_pas2_weball.csv` — career money
  (post-`apply_dedup.py`: the weball double-count is already corrected).
- `money_udp.csv` + `money_udp_per_cycle.json` — UDP support (from
  `pull_udp.py`).
- `opposition-computed.json` — UDP opposition credit (from
  `compute_opposition.py`).
- `dedup-notes.json` — per-person correction notes (from
  `apply_dedup.py`).

Outputs: `congress-money-tracker.csv` / `.json` with the base columns
(roster fields, career money, `per_cycle` / `udp_per_cycle` breakdowns,
opposition money columns). Ranking (`compute_ranking.py`) and the 2026
columns (`compute_2026.py`) run after this and add their columns; this
script writes the dataset in the final column order filtered to the
columns it produces (see config `dataset.csv_columns` / `json_keys`).

Rules (methodology §6, §7, §9, §13):
- Join on `person_key`. Career money columns are sums over the
  `per_cycle` entries (floats, 2dp); `udp_ie_support_career` is the sum
  over `udp_per_cycle` and is asserted equal to `money_udp.csv`.
- `per_cycle` / `udp_per_cycle` entries are carried verbatim (amounts
  as floats), preserving the staged order.
- Alan Armstrong (`A000383`, no FEC candidate IDs): all six money
  columns are the string `"unknown"`, not 0 — and the opposition
  columns are null. His `data_notes` is a fixed custom note (below).
- Roster fix — Kristen McDonald Rivet appears twice in the source
  roster (`M001237`, 119th-only, and `kristen-mcdonaldrivetmihouse`,
  120th-only) with the same FEC ID and identical money. The two rows
  collapse to one (`M001237`, both chambers, both districts 8, both
  parties Democrat, in both Congresses); money is counted once, not
  twice. The collapse is detected generally (two roster rows sharing an
  FEC ID with the same name) but the fix note is the recorded text for
  this person — a future collapse with no recorded note fails loudly
  rather than inventing one.
- `data_notes` assembly: the pas2 note + `' | '` + the UDP note,
  skipping empties; the dedup note (if any) is appended with a space
  after that. The Rivet fix note replaces the pas2 duplicate note
  (`duplicate roster entry: FEC ID shared with ...`).
- Opposition money: `udp_ie_opposing_opponents_career` is the
  `credit_by_person` figure (0.0 when absent);
  `udp_ie_total_benefit_career` is support + credit.
- Row order is roster.json order: the records are sorted
  case-insensitively by (last_name, first_name) and the resulting key
  order is asserted equal to `roster.json` (minus collapsed rows).
- `data_as_of` comes from config.

Internal consistency asserts (fail loudly, exit non-zero):
- every money person_key joins 1:1 to the roster; FEC IDs agree
  between roster and money files (the only shared ID is Rivet's);
- the pas2 career totals match the per-cycle sums to the cent
  (individual, AIPAC direct/earmark, corporate/earmark);
- the UDP career total matches the per-cycle UDP sum;
- 664 rows after the collapse.
"""
import csv, json
from collections import defaultdict
from decimal import Decimal

import pandas as pd

from config import load_config

CFG = load_config()
ROOT = CFG['_root']
CURRENT = CFG['cycles']['current']

# Recorded special-case notes (exact committed text; do not reword).
ARMSTRONG_NOTE = ('No FEC candidate IDs in roster (appointed senator, never ran for the seat); '
                  'money totals unknown, not zero. Not searchable in UDP IE data.')
RIVET_FIX_NOTES = {
    'M001237': ('Roster fix: Kristen McDonald Rivet appeared twice in the source roster '
                '(person_keys M001237 and kristen-mcdonaldrivetmihouse, same FEC ID H4MI08218, '
                'identical money totals); collapsed to a single row. Money totals counted once, '
                'not twice. She served in the 119th (MI-08) and was re-elected to the 120th (MI-08).'),
}

ROSTER_FIELDS = ['person_key', 'full_name', 'chamber_119', 'chamber_120', 'state',
                 'district_119', 'district_120', 'party_119', 'party_120',
                 'leadership_119', 'leadership_120', 'in_119th', 'in_120th',
                 'fec_candidate_ids']
MONEY_COLS = ['individual_contribution_total_career', 'aipac_pac_direct_career',
              'aipac_earmark_transmitted_career', 'corporate_pac_career',
              'corporate_earmark_transmitted_career', 'udp_ie_support_career']


def money2float(s):
    return round(float(Decimal(str(s))), 2)


# ---------- Load ----------
roster = json.load(open(ROOT / CFG['paths']['roster_intermediate']))
mpc = json.load(open(ROOT / CFG['paths']['money_per_cycle']))
with open(ROOT / CFG['paths']['money_pas2_weball'], newline='') as f:
    pas2 = {r['person_key']: r for r in csv.DictReader(f)}
with open(ROOT / CFG['paths']['money_udp'], newline='') as f:
    udp_csv = {r['person_key']: r for r in csv.DictReader(f)}
udp_pc = json.load(open(ROOT / CFG['paths']['money_udp_per_cycle']))
opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
dedup_notes = json.load(open(ROOT / CFG['paths']['dedup_notes']))
roster_json = json.load(open(ROOT / CFG['paths']['roster']))

by_key = {r['person_key']: r for r in roster}

# ---------- Collapse duplicate roster rows (shared FEC ID, same person) ----------
id_to_keys = defaultdict(list)
for r in roster:
    for cid in (r.get('fec_candidate_ids') or []):
        id_to_keys[cid].append(r['person_key'])
collapsed = {}   # dropped key -> kept key
for cid, keys in sorted(id_to_keys.items()):
    if len(keys) < 2:
        continue
    names = {by_key[k]['full_name'] for k in keys}
    if len(names) != 1:
        raise SystemExit(f'FEC ID {cid} shared by different people {sorted(keys)}: {sorted(names)}')
    # Keep the Bioguide-style key (e.g. M001237) over a slug key.
    kept = sorted(keys, key=lambda k: (0 if len(k) == 7 and k[0].isalpha() and k[1:].isdigit() else 1, k))[0]
    if kept not in RIVET_FIX_NOTES:
        raise SystemExit(f'roster collapse for {kept} has no recorded fix note; add one, do not invent it')
    for k in keys:
        if k == kept:
            continue
        drop, keep = by_key[k], by_key[kept]
        # The 120th-only row supplies the 120th fields; the kept row supplies the 119th.
        for suffix in ('119', '120'):
            if keep.get(f'in_{suffix}th') != 'yes' and drop.get(f'in_{suffix}th') == 'yes':
                for f in (f'chamber_{suffix}', f'district_{suffix}', f'party_{suffix}',
                          f'leadership_{suffix}', f'in_{suffix}th'):
                    keep[f] = drop[f]
        # Money must be identical between the two rows, or the collapse is invalid.
        for src, name in ((mpc, 'money_per_cycle'), (pas2, 'money_pas2_weball'),
                          (udp_csv, 'money_udp'), (udp_pc, 'money_udp_per_cycle')):
            a, b = src.get(kept), src.get(k)
            if name == 'money_per_cycle':
                va = [(e['cycle'], e['candidate_id'], e['individual'], e['aipac_pac_direct'],
                       e['aipac_earmark_transmitted'], e['corporate_pac'],
                       e['corporate_earmark_transmitted']) for e in a['per_cycle']]
                vb = [(e['cycle'], e['candidate_id'], e['individual'], e['aipac_pac_direct'],
                       e['aipac_earmark_transmitted'], e['corporate_pac'],
                       e['corporate_earmark_transmitted']) for e in b['per_cycle']]
            elif name == 'money_udp_per_cycle':
                va, vb = a['udp_per_cycle'], b['udp_per_cycle']
            else:
                # Money figures must be identical; data_notes legitimately
                # differ (each duplicate row names the other key).
                money_fields = [f for f in a
                                if f not in ('person_key', 'full_name', 'data_notes')]
                va = {f: a[f] for f in money_fields}
                vb = {f: b[f] for f in money_fields}
            if va != vb:
                raise SystemExit(f'collapse {kept}/{k}: money differs in {name}')
        collapsed[k] = kept
        print(f'roster collapse: {k} -> {kept} (shared FEC ID {cid})')
rows = [r for r in roster if r['person_key'] not in collapsed]
print(f'roster rows: {len(roster)} -> {len(rows)} after collapse')

# ---------- Build records ----------
PER_CYCLE_MAP = [('individual', 'individual'), ('aipac_pac_direct', 'aipac_pac_direct'),
                 ('aipac_earmark_transmitted', 'aipac_earmark_transmitted'),
                 ('corporate_pac', 'corporate_pac'),
                 ('corporate_earmark_transmitted', 'corporate_earmark_transmitted')]
records = []
for r in rows:
    pk = r['person_key']
    ids = r.get('fec_candidate_ids') or []
    if pk not in mpc or pk not in pas2 or pk not in udp_csv or pk not in udp_pc:
        raise SystemExit(f'{pk} ({r["full_name"]}) missing from a money file')
    # FEC IDs must agree between roster and money files. (money_per_cycle
    # carries no fec_candidate_ids field; its IDs are the per_cycle entries'.)
    mpc_ids = sorted({e['candidate_id'] for e in mpc[pk]['per_cycle']})
    if not set(mpc_ids) <= set(ids):
        raise SystemExit(f'{pk}: per_cycle IDs {mpc_ids} not a subset of roster IDs {sorted(ids)}')
    for src, label in ((pas2[pk], 'money_pas2_weball'), (udp_csv[pk], 'money_udp')):
        have = src['fec_candidate_ids']
        have = have.split(';') if have else []
        if sorted(have) != sorted(ids):
            raise SystemExit(f'{pk}: FEC IDs disagree between roster {sorted(ids)} and {label} {sorted(have)}')
    rec = {f: r[f] for f in ROSTER_FIELDS}
    rec['fec_candidate_ids'] = list(ids)

    # per_cycle entries (amounts as floats, staged order preserved)
    per_cycle = []
    for e in mpc[pk]['per_cycle']:
        entry = {'cycle': e['cycle'], 'candidate_id': e['candidate_id']}
        for src_key, _ in PER_CYCLE_MAP:
            entry[src_key] = money2float(e[src_key])
        per_cycle.append(entry)
    rec['per_cycle'] = per_cycle
    udp_entries = []
    for e in udp_pc[pk]['udp_per_cycle']:
        entry = {'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
                 'udp_ie_support': money2float(e['udp_ie_support'])}
        if 'attribution' in e:
            entry['attribution'] = e['attribution']
        udp_entries.append(entry)
    rec['udp_per_cycle'] = udp_entries

    if not ids:
        # Alan Armstrong: money unknown, not zero.
        for c in MONEY_COLS:
            rec[c] = 'unknown'
        rec['udp_ie_opposing_opponents_career'] = None
        rec['udp_ie_total_benefit_career'] = None
        rec['data_notes'] = ARMSTRONG_NOTE
        rec['data_as_of'] = CFG['data_as_of']
        records.append(rec)
        continue

    # Career money = sums over per_cycle (the standing audit: 0 mismatches).
    sums = {dst: round(sum(e[dst] for e in per_cycle), 2) for _, dst in PER_CYCLE_MAP}
    udp_support = round(sum(e['udp_ie_support'] for e in udp_entries), 2)
    rec['individual_contribution_total_career'] = sums['individual']
    rec['aipac_pac_direct_career'] = sums['aipac_pac_direct']
    rec['aipac_earmark_transmitted_career'] = sums['aipac_earmark_transmitted']
    rec['corporate_pac_career'] = sums['corporate_pac']
    rec['corporate_earmark_transmitted_career'] = sums['corporate_earmark_transmitted']
    rec['udp_ie_support_career'] = udp_support
    # Cross-checks against the staged career files (to the cent).
    pas2_row = pas2[pk]
    for col, val in (('individual_contribution_total_career', sums['individual']),
                     ('aipac_pac_direct_career', sums['aipac_pac_direct']),
                     ('aipac_earmark_transmitted_career', sums['aipac_earmark_transmitted']),
                     ('corporate_pac_career', sums['corporate_pac']),
                     ('corporate_earmark_transmitted_career', sums['corporate_earmark_transmitted'])):
        if Decimal(pas2_row[col]) != Decimal(str(val)):
            raise SystemExit(f'{pk}: pas2 {col} {pas2_row[col]} != per-cycle sum {val}')
    if Decimal(udp_csv[pk]['udp_ie_support_career']) != Decimal(str(udp_support)):
        raise SystemExit(f"{pk}: money_udp.csv {udp_csv[pk]['udp_ie_support_career']} "
                         f"!= per-cycle UDP sum {udp_support}")

    # data_notes: pas2 note + ' | ' + UDP note; dedup note appended with a space.
    if pk in RIVET_FIX_NOTES:
        pas2_note = RIVET_FIX_NOTES[pk]
    else:
        pas2_note = pas2_row['data_notes']
    parts = [p for p in (pas2_note, udp_csv[pk]['data_notes']) if p]
    note = ' | '.join(parts)
    if pk in dedup_notes:
        note = f'{note} {dedup_notes[pk]}' if note else dedup_notes[pk]
    rec['data_notes'] = note
    rec['data_as_of'] = CFG['data_as_of']

    # Opposition money.
    credit = round(float(opp['credit_by_person'].get(pk, 0.0)), 2)
    rec['udp_ie_opposing_opponents_career'] = credit
    rec['udp_ie_total_benefit_career'] = round(udp_support + credit, 2)
    records.append(rec)

# Row order: roster.json order (case-insensitive last, first); assert it.
records.sort(key=lambda r: (by_key[r['person_key']]['last_name'].lower(),
                            by_key[r['person_key']]['first_name'].lower()))
expected_order = [r['person_key'] for r in roster_json if r['person_key'] not in collapsed]
if [r['person_key'] for r in records] != expected_order:
    raise SystemExit('merged row order does not match roster.json order')
print(f'merged {len(records)} records (expected 664)')
if len(records) != 664:
    raise SystemExit(f'expected 664 records after collapse, got {len(records)}')

# ---------- Write ----------
csv_cols = [c for c in CFG['dataset']['csv_columns']
            if c in ROSTER_FIELDS + MONEY_COLS + ['data_as_of', 'data_notes', 'per_cycle',
                                                 'udp_per_cycle', 'udp_ie_opposing_opponents_career',
                                                 'udp_ie_total_benefit_career']]
json_keys = [k for k in CFG['dataset']['json_keys'] if k in csv_cols]
ordered = [{k: rec[k] for k in json_keys} for rec in records]
with open(ROOT / CFG['paths']['dataset_json'], 'w') as f:
    json.dump(ordered, f, indent=1)
print(f"wrote {CFG['paths']['dataset_json']} ({len(ordered)} rows)")
pd.DataFrame(ordered, columns=csv_cols).to_csv(ROOT / CFG['paths']['dataset_csv'], index=False)
print(f"wrote {CFG['paths']['dataset_csv']} ({len(ordered)} rows)")
