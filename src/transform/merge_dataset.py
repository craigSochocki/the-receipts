#!/usr/bin/env python3
"""Merge roster + money + opposition into the base dataset.

Inputs (all staged; see config.yaml `paths`):
- `roster_intermediate.json` — the enriched roster (665 rows).
- `money_per_cycle.json` + `money_pas2_weball.csv` — career money
  (post-`apply_dedup.py`: the weball double-count is already corrected).
- `money_udp.csv` + `money_udp_per_cycle.json` — UDP support (from
  `pull_udp.py`).
- `self_funding_per_cycle.json` + `self_funding.csv` — self-funding +
  topline from weball (from `pull_self_funding.py`, Curtis-corrected
  for cols 6-9 via the recorded dedup extension).
- `other_committees_per_cycle.json` + `other_committees.csv` — other
  committee contributions from pas2 + cm (from
  `pull_other_committees.py`).
- `all_ie_per_cycle.json` + `all_ie.csv` + `all_ie_top_committees.json`
  — all independent expenditures 2022-2026 (from `pull_all_ie.py`).
- `opposition-computed.json` — UDP opposition credit (from
  `compute_opposition.py`).
- `dedup-notes.json` — per-person correction notes (from
  `apply_dedup.py`).

Outputs: `congress-money-tracker.csv` / `.json` with the base columns
(roster fields, career money, `per_cycle` / `udp_per_cycle` /
`self_funding_per_cycle` / `other_committees_per_cycle` /
`all_ie_per_cycle` breakdowns, `all_ie_top_committees`,
opposition money columns). Ranking (`compute_ranking.py`) and the 2026
columns (`compute_2026.py`) run after this and add their columns; this
script writes the dataset in the final column order filtered to the
columns it produces (see config `dataset.csv_columns` / `json_keys`).
`all_ie_top_committees` is JSON-only (not in the CSV) by design.

Rules (methodology §6, §7, §9, §13, §15):
- Join on `person_key`. Career money columns are sums over the
  `per_cycle` entries (floats, 2dp); `udp_ie_support_career` is the sum
  over `udp_per_cycle` and is asserted equal to `money_udp.csv`. The
  same sum-and-assert pattern holds for the new families: self-funding
  / topline sums over `self_funding_per_cycle` (flows summed; cash on
  hand and debts owed by are stocks = latest cycle's value, asserted
  against `self_funding.csv`); other-committee sums over
  `other_committees_per_cycle` (asserted against
  `other_committees.csv`); all-IE sums over `all_ie_per_cycle`
  (asserted against `all_ie.csv`).
- `per_cycle` / `udp_per_cycle` entries are carried verbatim (amounts
  as floats), preserving the staged order. The new per-cycle lists are
  built the same way from their staged files (string amounts converted
  to floats); `all_ie_per_cycle` is built per (cycle, candidate_id)
  from the pull's per-candidate entries, and `all_ie_top_committees`
  is carried verbatim from `all_ie_top_committees.json`.
- Alan Armstrong (`A000383`, no FEC candidate IDs): all money
  columns are the string `"unknown"`, not 0 — and the opposition
  columns are null. His `data_notes` is a fixed custom note (below).
  His per-cycle lists are empty and `all_ie_top_committees` is null.
- Roster fix — Kristen McDonald Rivet appears twice in the source
  roster (`M001237`, 119th-only, and `kristen-mcdonaldrivetmihouse`,
  120th-only) with the same FEC ID and identical money. The two rows
  collapse to one (`M001237`, both chambers, both districts 8, both
  parties Democrat, in both Congresses); money is counted once, not
  twice. The collapse is detected generally (two roster rows sharing an
  FEC ID with the same name) but the fix note is the recorded text for
  this person — a future collapse with no recorded note fails loudly
  rather than inventing one. The collapse validation covers ALL
  per-cycle files (self-funding, other-committees, all-IE) as well as
  the career files: both Rivet person_keys share FEC ID H4MI08218, so
  values must be identical in each file; fail loudly on mismatch.
  (Per-person sums double-count her $2,952,792.48 career all-IE /
  $2,219,737 other-committee in roster totals — same convention as
  the existing methodology totals; the merged dataset rows must not
  double-count.)
- `data_notes` assembly: the pas2 note + `' | '` + the UDP note,
  skipping empties; the dedup note (if any) is appended with a space
  after that. The Rivet fix note replaces the pas2 duplicate note
  (`duplicate roster entry: FEC ID shared with ...`). Two further
  recorded notes are appended with `' | '`: the Lamb 2026 pending
  reconciliation (below) and any WinRed-conduit segment from the
  other-committee pull (other_unclassified includes WinRed net where
  nonzero).
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
- the self-funding / topline career totals match the per-cycle sums
  to the cent (flows summed; cash on hand and debts owed by are the
  latest cycle's values, per the recorded stock cycle in
  `self_funding.csv`);
- the other-committee career totals (per class, earmarks, total)
  match the per-cycle sums to the cent;
- the all-IE career totals match the per-cycle sums to the cent
  (support + oppose + blank-direction rows = total);
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
# Mark Lamb (marklambazhouse, AZ House): the staged pas2 2026 file
# effectively ends Sep 30, while weball runs through Oct 14 — his
# other-committee 2026 money is $96,500 pas2-derived vs $129,150 in
# weball col 26, a $32,650 residual not reproducible until the mid-Dec
# re-pull. Recorded, not adjusted.
LAMB_NOTE = ('2026 PENDING RECONCILIATION: other-committee money in 2026 is $96,500.00 by pas2 '
             '(leadership $43,000; labor $5,000; trade $6,000; membership $8,000; '
             'other-unclassified $34,500) but weball col 26 (OTHER_POL_CMTE_CONTRIB) reports '
             '$129,150.00 — $32,650.00 residual, not reproducible until the mid-Dec re-pull '
             '(staged pas2 2026 effectively ends Sep 30, weball runs through Oct 14). '
             'Do not adjust either figure.')

ROSTER_FIELDS = ['person_key', 'full_name', 'chamber_119', 'chamber_120', 'state',
                 'district_119', 'district_120', 'party_119', 'party_120',
                 'leadership_119', 'leadership_120', 'in_119th', 'in_120th',
                 'fec_candidate_ids']
MONEY_COLS = ['individual_contribution_total_career', 'aipac_pac_direct_career',
              'aipac_earmark_transmitted_career', 'corporate_pac_career',
              'corporate_earmark_transmitted_career', 'udp_ie_support_career']
# New career money columns (complete-financial-picture build, Nov 12 2026).
SF_FLOW_COLS = ['cand_contrib_career', 'cand_loans_career', 'self_funding_career',
                'loan_repayments_career', 'total_receipts_career',
                'total_disbursements_career', 'transfers_from_auth_career',
                'transfers_to_auth_career']
SF_STOCK_COLS = ['debts_owed_by_career', 'cash_on_hand_career']
SF_COLS = SF_FLOW_COLS + ['debts_owed_to_career'] + SF_STOCK_COLS
OC_BUCKETS = ['party_committees', 'leadership_pacs', 'labor_pacs', 'trade_pacs',
              'membership_pacs', 'cooperative_pacs', 'other_unclassified']
OC_COLS = ([f'{b}_career' for b in OC_BUCKETS] + ['other_committees_total_career']
           + [f'{b}_earmark_transmitted_career' for b in OC_BUCKETS])
AIE_COLS = ['all_ie_support_career', 'all_ie_oppose_career', 'all_ie_total_career']
NEW_MONEY_COLS = SF_COLS + OC_COLS + AIE_COLS
ALL_MONEY_COLS = MONEY_COLS + NEW_MONEY_COLS


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
sf_pc_raw = json.load(open(ROOT / CFG['paths']['self_funding_per_cycle']))
sf_pc = sf_pc_raw['persons']
with open(ROOT / CFG['paths']['self_funding_csv'], newline='') as f:
    sf_csv = {r['person_key']: r for r in csv.DictReader(f)}
oc_pc = json.load(open(ROOT / CFG['paths']['other_committees_per_cycle']))
with open(ROOT / CFG['paths']['other_committees_csv'], newline='') as f:
    oc_csv = {r['person_key']: r for r in csv.DictReader(f)}
aie_raw = json.load(open(ROOT / CFG['paths']['all_ie_per_cycle']))
with open(ROOT / CFG['paths']['all_ie_csv'], newline='') as f:
    aie_csv = {r['person_key']: r for r in csv.DictReader(f)}
aie_top = json.load(open(ROOT / CFG['paths']['all_ie_top_committees']))
opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
dedup_notes = json.load(open(ROOT / CFG['paths']['dedup_notes']))
roster_json = json.load(open(ROOT / CFG['paths']['roster']))

# All-IE per-cycle entries, grouped per person from the pull's
# per-candidate entries (keyed by candidate_id, not person_key).
aie_pc_by_person = {}
for _e in aie_raw['per_candidate_per_cycle']:
    _cid = _e['candidate_id']
    for _pk in {p['person_key'] for p in roster if _cid in (p.get('fec_candidate_ids') or [])}:
        aie_pc_by_person.setdefault(_pk, []).append({
            'cycle': _e['cycle'], 'candidate_id': _cid,
            'all_ie_support': _e['all_ie_support'],
            'all_ie_oppose': _e['all_ie_oppose'],
            'all_ie_total': _e['all_ie_total'],
            'no_direction_amount': _e['no_direction_amount']})
for _pk in aie_pc_by_person:
    aie_pc_by_person[_pk].sort(key=lambda e: (e['cycle'], e['candidate_id']))

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
                          (udp_csv, 'money_udp'), (udp_pc, 'money_udp_per_cycle'),
                          (sf_pc, 'self_funding_per_cycle'), (sf_csv, 'self_funding'),
                          (oc_pc, 'other_committees_per_cycle'),
                          (oc_csv, 'other_committees'),
                          (aie_csv, 'all_ie'),
                          (aie_pc_by_person, 'all_ie_per_cycle')):
            a, b = src.get(kept), src.get(k)
            if a is None or b is None:
                raise SystemExit(f'collapse {kept}/{k}: missing from {name}')
            if name == 'money_per_cycle':
                va = [(e['cycle'], e['candidate_id'], e['individual'], e['aipac_pac_direct'],
                       e['aipac_earmark_transmitted'], e['corporate_pac'],
                       e['corporate_earmark_transmitted']) for e in a['per_cycle']]
                vb = [(e['cycle'], e['candidate_id'], e['individual'], e['aipac_pac_direct'],
                       e['aipac_earmark_transmitted'], e['corporate_pac'],
                       e['corporate_earmark_transmitted']) for e in b['per_cycle']]
            elif name == 'money_udp_per_cycle':
                va, vb = a['udp_per_cycle'], b['udp_per_cycle']
            elif name in ('self_funding_per_cycle', 'other_committees_per_cycle'):
                va, vb = a['per_cycle'], b['per_cycle']
            elif name == 'all_ie_per_cycle':
                # aie_pc_by_person values are already per-person entry lists.
                va, vb = a, b
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
    if (pk not in mpc or pk not in pas2 or pk not in udp_csv or pk not in udp_pc
            or pk not in sf_pc or pk not in sf_csv or pk not in oc_pc or pk not in oc_csv
            or pk not in aie_csv or pk not in aie_top):
        raise SystemExit(f'{pk} ({r["full_name"]}) missing from a money file')
    # FEC IDs must agree between roster and money files. (money_per_cycle
    # carries no fec_candidate_ids field; its IDs are the per_cycle entries'.)
    mpc_ids = sorted({e['candidate_id'] for e in mpc[pk]['per_cycle']})
    if not set(mpc_ids) <= set(ids):
        raise SystemExit(f'{pk}: per_cycle IDs {mpc_ids} not a subset of roster IDs {sorted(ids)}')
    for src, label in ((pas2[pk], 'money_pas2_weball'), (udp_csv[pk], 'money_udp'),
                       (sf_csv[pk], 'self_funding'), (oc_csv[pk], 'other_committees'),
                       (aie_csv[pk], 'all_ie')):
        have = src['fec_candidate_ids']
        have = have.split(';') if have else []
        if sorted(have) != sorted(ids):
            raise SystemExit(f'{pk}: FEC IDs disagree between roster {sorted(ids)} and {label} {sorted(have)}')
    sf_ids = sorted({e['candidate_id'] for e in sf_pc[pk]['per_cycle']})
    if not set(sf_ids) <= set(ids):
        raise SystemExit(f'{pk}: self_funding per_cycle IDs {sf_ids} not a subset of roster IDs {sorted(ids)}')
    oc_ids = sorted({e['candidate_id'] for e in oc_pc[pk]['per_cycle']})
    if not set(oc_ids) <= set(ids):
        raise SystemExit(f'{pk}: other_committees per_cycle IDs {oc_ids} not a subset of roster IDs {sorted(ids)}')
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

    # self_funding_per_cycle entries (string amounts -> floats; the pull
    # omits all-zero (cycle, candidate) pairs, staged order preserved).
    sf_entries = []
    for e in sf_pc[pk]['per_cycle']:
        entry = {'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
                 'candidate_contributions': money2float(e['candidate_contributions']),
                 'candidate_loans': money2float(e['candidate_loans']),
                 'loan_repayments': money2float(e['loan_repayments']),
                 'debts_owed_by': money2float(e['debts_owed_by']),
                 'debts_owed_to': None,
                 'total_receipts': money2float(e['total_receipts']),
                 'total_disbursements': money2float(e['total_disbursements']),
                 'cash_on_hand': money2float(e['cash_on_hand']),
                 'transfers_from_auth': money2float(e['transfers_from_auth']),
                 'transfers_to_auth': money2float(e['transfers_to_auth']),
                 'coverage_end_date': e['coverage_end_date']}
        sf_entries.append(entry)
    rec['self_funding_per_cycle'] = sf_entries

    # other_committees_per_cycle entries (string amounts -> floats).
    oc_entries = []
    for e in oc_pc[pk]['per_cycle']:
        entry = {'cycle': e['cycle'], 'candidate_id': e['candidate_id']}
        for b in OC_BUCKETS:
            entry[b] = money2float(e[b])
        entry['earmark_transmitted'] = {b: money2float(v)
                                        for b, v in e.get('earmark_transmitted', {}).items()}
        entry['winred_included'] = money2float(e.get('winred_included', '0.00'))
        oc_entries.append(entry)
    rec['other_committees_per_cycle'] = oc_entries

    # all_ie_per_cycle entries (already floats, built from the pull's
    # per-candidate entries above; sorted by (cycle, candidate_id)).
    aie_entries = [{'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
                    'all_ie_support': e['all_ie_support'],
                    'all_ie_oppose': e['all_ie_oppose'],
                    'all_ie_total': e['all_ie_total'],
                    'no_direction_amount': e['no_direction_amount']}
                   for e in aie_pc_by_person.get(pk, [])]
    rec['all_ie_per_cycle'] = aie_entries
    rec['all_ie_top_committees'] = aie_top.get(pk)

    if not ids:
        # Alan Armstrong: money unknown, not zero.
        for c in ALL_MONEY_COLS:
            rec[c] = 'unknown'
        rec['udp_ie_opposing_opponents_career'] = None
        rec['udp_ie_total_benefit_career'] = None
        rec['all_ie_top_committees'] = None
        rec['data_notes'] = ARMSTRONG_NOTE
        rec['data_as_of'] = CFG['data_as_of']
        records.append(rec)
        continue

    # Career money = sums over per_cycle (the standing audit: 0 mismatches).
    # NOTE: force float — round(sum([]), 2) is int 0 in Python, but the
    # committed dataset stores every career money column as a float
    # (0.0, not 0). The 2026 columns are the exception (int 0 when no
    # 2026 entries) and keep their own rule in compute_2026.py.
    sums = {dst: round(float(sum(e[dst] for e in per_cycle)), 2) for _, dst in PER_CYCLE_MAP}
    udp_support = round(float(sum(e['udp_ie_support'] for e in udp_entries)), 2)
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

    # Self-funding / topline: flows summed; stocks (cash on hand, debts
    # owed by) are the latest cycle's values, per the recorded stock
    # cycle in self_funding.csv (the pull's latest cycle with a weball
    # row). A latest cycle whose row is all-zero contributes 0.0 — the
    # per-cycle list omits all-zero pairs, so sum over the entries in
    # that cycle, defaulting to 0.0.
    sf_row = sf_csv[pk]
    # (per-cycle key, dataset career column, self_funding.csv column)
    sf_flows = [
        ('candidate_contributions', 'cand_contrib_career', 'candidate_contributions_career'),
        ('candidate_loans', 'cand_loans_career', 'candidate_loans_career'),
        ('loan_repayments', 'loan_repayments_career', 'loan_repayments_career'),
        ('total_receipts', 'total_receipts_career', 'total_receipts_career'),
        ('total_disbursements', 'total_disbursements_career', 'total_disbursements_career'),
        ('transfers_from_auth', 'transfers_from_auth_career', 'transfers_from_auth_career'),
        ('transfers_to_auth', 'transfers_to_auth_career', 'transfers_to_auth_career'),
    ]
    for src_key, dst_col, csv_col in sf_flows:
        val = round(float(sum(e[src_key] for e in sf_entries)), 2)
        rec[dst_col] = val
        if Decimal(sf_row[csv_col]) != Decimal(str(val)):
            raise SystemExit(f'{pk}: self_funding {csv_col} {sf_row[csv_col]} '
                             f'!= per-cycle sum {val}')
    rec['self_funding_career'] = round(rec['cand_contrib_career']
                                       + rec['cand_loans_career'], 2)
    if Decimal(sf_row['self_funding_career']) != Decimal(str(rec['self_funding_career'])):
        raise SystemExit(f"{pk}: self_funding self_funding_career {sf_row['self_funding_career']} "
                         f"!= per-cycle sum {rec['self_funding_career']}")
    if sf_row['cash_on_hand_cycle'] != sf_row['debts_owed_by_cycle']:
        raise SystemExit(f"{pk}: self_funding stock cycles disagree: "
                         f"{sf_row['cash_on_hand_cycle']} vs {sf_row['debts_owed_by_cycle']}")
    stock_cycle = sf_row['cash_on_hand_cycle']
    for src_key, dst_col in (('cash_on_hand', 'cash_on_hand_career'),
                             ('debts_owed_by', 'debts_owed_by_career')):
        if stock_cycle == '':
            val = None
        else:
            val = round(float(sum(e[src_key] for e in sf_entries
                                  if str(e['cycle']) == stock_cycle)), 2)
        rec[dst_col] = val
        if sf_row[dst_col] == '':
            if val is not None:
                raise SystemExit(f'{pk}: self_funding {dst_col} blank but per-cycle sum {val}')
        elif Decimal(sf_row[dst_col]) != Decimal(str(val)):
            raise SystemExit(f'{pk}: self_funding {dst_col} {sf_row[dst_col]} '
                             f'!= per-cycle sum {val}')
    rec['debts_owed_to_career'] = None
    if sf_row['debts_owed_to_career'] != '':
        raise SystemExit(f"{pk}: self_funding debts_owed_to_career unexpectedly "
                         f"non-blank: {sf_row['debts_owed_to_career']}")

    # Other committees: per-class sums, earmark sums, total.
    oc_row = oc_csv[pk]
    for b in OC_BUCKETS:
        val = round(float(sum(e[b] for e in oc_entries)), 2)
        rec[f'{b}_career'] = val
        if Decimal(oc_row[f'{b}_career']) != Decimal(str(val)):
            raise SystemExit(f'{pk}: other_committees {b}_career {oc_row[f"{b}_career"]} '
                             f'!= per-cycle sum {val}')
        em = round(float(sum(e['earmark_transmitted'].get(b, 0.0) for e in oc_entries)), 2)
        rec[f'{b}_earmark_transmitted_career'] = em
        if Decimal(oc_row[f'{b}_earmark_transmitted_career']) != Decimal(str(em)):
            raise SystemExit(f'{pk}: other_committees {b}_earmark_transmitted_career '
                             f"{oc_row[f'{b}_earmark_transmitted_career']} != per-cycle sum {em}")
    oc_total = round(float(sum(rec[f'{b}_career'] for b in OC_BUCKETS)), 2)
    rec['other_committees_total_career'] = oc_total
    if Decimal(oc_row['other_committees_total_career']) != Decimal(str(oc_total)):
        raise SystemExit(f"{pk}: other_committees total {oc_row['other_committees_total_career']} "
                         f"!= per-cycle sum {oc_total}")

    # All-IE: support / oppose / total (total includes blank-direction rows).
    aie_row = aie_csv[pk]
    for src_key, dst_col in (('all_ie_support', 'all_ie_support_career'),
                             ('all_ie_oppose', 'all_ie_oppose_career'),
                             ('all_ie_total', 'all_ie_total_career')):
        val = round(float(sum(e[src_key] for e in aie_entries)), 2)
        rec[dst_col] = val
        if Decimal(aie_row[dst_col]) != Decimal(str(val)):
            raise SystemExit(f'{pk}: all_ie {dst_col} {aie_row[dst_col]} '
                             f'!= per-cycle sum {val}')

    # data_notes: pas2 note + ' | ' + UDP note; dedup note appended with a space.
    if pk in RIVET_FIX_NOTES:
        pas2_note = RIVET_FIX_NOTES[pk]
    else:
        pas2_note = pas2_row['data_notes']
    parts = [p for p in (pas2_note, udp_csv[pk]['data_notes']) if p]
    note = ' | '.join(parts)
    if pk in dedup_notes:
        note = f'{note} {dedup_notes[pk]}' if note else dedup_notes[pk]
    if pk == 'marklambazhouse':
        note = f'{note} | {LAMB_NOTE}' if note else LAMB_NOTE
    winred_segments = [s for s in (oc_row['data_notes'] or '').split(' | ')
                       if 'WinRed' in s]
    for s in winred_segments:
        note = f'{note} | {s}' if note else s
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
# NOTE: json_keys is filtered to the produced columns independently of
# csv_cols (not `if k in csv_cols`): all_ie_top_committees is JSON-only
# by design and must survive into the JSON even though it has no CSV
# column. The other writers (compute_ranking.py, compute_2026.py) use
# the same rule.
PRODUCED = (ROSTER_FIELDS + ALL_MONEY_COLS
            + ['data_as_of', 'data_notes', 'per_cycle', 'udp_per_cycle',
               'self_funding_per_cycle', 'other_committees_per_cycle',
               'all_ie_per_cycle', 'all_ie_top_committees',
               'udp_ie_opposing_opponents_career', 'udp_ie_total_benefit_career'])
csv_cols = [c for c in CFG['dataset']['csv_columns'] if c in PRODUCED]
json_keys = [k for k in CFG['dataset']['json_keys'] if k in PRODUCED]
ordered = [{k: rec[k] for k in json_keys} for rec in records]
with open(ROOT / CFG['paths']['dataset_json'], 'w') as f:
    json.dump(ordered, f, indent=1)
print(f"wrote {CFG['paths']['dataset_json']} ({len(ordered)} rows)")
pd.DataFrame(ordered, columns=csv_cols).to_csv(ROOT / CFG['paths']['dataset_csv'], index=False)
print(f"wrote {CFG['paths']['dataset_csv']} ({len(ordered)} rows)")
