#!/usr/bin/env python3
"""Congress money tracker — self-funding + topline + transfers columns from FEC weball.

Reads the staged bulk weball files (data/raw/weball/weballYY.txt, cycles
1980-2026) and produces:
  - data/intermediate/self_funding_per_cycle.json — per person_key, per-cycle entries
  - data/intermediate/self_funding.csv — one row per person, career totals + 2026 values

The tracker's definition of total_accepted (individual + corporate PAC +
AIPAC direct) is UNCHANGED. The columns built here are separate and are
never blended into total_accepted. Self-funding for validation =
candidate_contributions + candidate_loans (career).

VERIFIED WEBALL COLUMN MAP (1-indexed, 30 columns; FEC all-candidates
file description, https://www.fec.gov/campaign-finance-data/all-candidates-file-description/,
fetched Nov 12, 2026, cross-checked against the staged rows below):
    6  TTL_RECEIPTS      -> total_receipts
    7  TRANS_FROM_AUTH   -> transfers_from_auth
    8  TTL_DISB          -> total_disbursements
    9  TRANS_TO_AUTH     -> transfers_to_auth
   10  COH_BOP           -> (not output; beginning cash, for reference only)
   11  COH_COP           -> cash_on_hand (ending cash)
   12  CAND_CONTRIB      -> candidate_contributions
   13  CAND_LOANS        -> candidate_loans
   14  OTHER_LOANS       -> (not output; non-candidate loans)
   15  CAND_LOAN_REPAY   -> loan_repayments, candidate part
   16  OTHER_LOAN_REPAY  -> loan_repayments, other-loan part
   17  DEBTS_OWED_BY     -> debts_owed_by
   18  TTL_INDIV_CONTRIB -> (not output here; already in money_per_cycle.json;
                             used only as the dedup guard, see below)
   28  CVG_END_DT        -> coverage_end_date
  loan_repayments in the output = col 15 + col 16 (total loan repayments,
  matching the FEC API `loan_repayments` field).
  debts_owed_to has NO weball column: the 30-column weball file carries only
  DEBTS_OWED_BY (col 17). It is therefore output as null (unknown) for every
  row, never as zero. The FEC API does carry it (`last_debts_owed_to_committee`);
  the spot-check below found $0.00 for Constantino in both cycles, but that
  single API value is NOT backfilled into the weball-derived columns.

CONSTANTINO VERIFICATION (candidate ID H6NY21157, roster person
anthonyconstantinonyhouse). His weball rows:
  2024: receipts $2,600,000.00, disb $293,113.17, cand_loans $2,600,000.00,
        coh_cop $2,306,886.83, debts_owed_by $2,600,000.00, cvg 12/31/2024
  2026: receipts $14,464,951.19, disb $14,472,853.54, cand_loans $14,400,000.00,
        coh_cop $2,298,984.48, debts_owed_by $17,000,000.00,
        trans_to_auth $640,000.00, indiv $0.00, cvg 10/14/2026
  Career sums reproduce the FEC API year-end figures exactly:
    total receipts $17,064,951.19, candidate loans $17,000,000.00,
    total disbursements $14,765,966.71, cash on hand $2,298,984.48 (2026),
    transfers to auth $640,000.00.
  NOTE on the "$14.4M vs $17M loans" gap: the $17M figure is the CAREER
  total (2024 $2.6M + 2026 $14.4M), not a 2026-only figure. The FEC API
  candidate-totals endpoint (DEMO_KEY, Nov 12, 2026) returns, per cycle,
  values IDENTICAL to weball for both 2024 and 2026 (receipts, disbursements,
  loans, cash, debts owed by/to, transfers, loan repayments — all exact to
  the cent, including last_debts_owed_to_committee $0.00). There is NO
  weball-vs-API discrepancy at matched coverage dates. The genuine caveat
  is timeliness only: the staged 2026 weball snapshot covers through
  10/14/2026 (pre-general); post-general / year-end 2026 filings are not
  yet in it, so 2026 figures are a lower bound against later filings.

FLOWS vs STOCKS (career aggregation):
  Flows (summed across cycles): candidate_contributions, candidate_loans,
    loan_repayments, total_receipts, total_disbursements,
    transfers_from_auth, transfers_to_auth.
  Stocks (NOT summed; latest cycle's value): cash_on_hand (COH_COP) and
    debts_owed_by (outstanding balance at cycle end). Summing them would
    double-count — e.g. Constantino's debts_owed_by is $2.6M in 2024 and
    $17.0M in 2026; the career value is $17.0M (2026), not $19.6M.
    `cash_on_hand_cycle` / `debts_owed_by_cycle` record which cycle the
    career stock value came from (the person's latest cycle with a weball
    row). The 2026 stock columns are blank when the person has no 2026
    weball row (no report), not zero.

DEDUP (chamber-switchers with two candidate IDs in the same cycle):
  data/source/dedup-applied.json records 90 (person, cycle) groups where weball
  repeats the identical TTL_INDIV_CONTRIB under both IDs. Checked here
  against the raw weball rows: in 89 of the 90 groups the dropped copy is
  identical to the kept copy on EVERY financial column (6-18, 26, 27, 29,
  30), so the same double-count hits these columns too and the recorded
  correction is applied column-by-column (dropped copy zeroed wherever it
  equals the kept copy). ONE exception — John R. Curtis, 2024 (kept
  S4UT00282, dropped H8UT03238): cols 10-18 are identical (so the dropped
  copy IS zeroed for cash/contrib/loans/repayments/debts), but cols 6-9
  differ (receipts $5,748,063.58 vs $5,640,855.75; transfers from auth
  $1,369,004.86 vs $1,261,797.03; disbursements $5,346,220.15 vs
  $5,239,012.32; transfers to auth $107,982.83 vs $3,300.00). The recorded
  dedup decision was scoped to TTL_INDIV_CONTRIB and does not cover those
  four differing columns — BUT the extension recorded on the Curtis 2024
  entry in dedup-applied.json (`extend_to_columns_6_9`) covers them:
  kept-minus-dropped is $107,207.83 EXACTLY for cols 6, 7 and 8, and cols
  10-18 are byte-identical, so the dropped row is a strict subset of the
  kept row and counting both double-counts the House row's activity. The
  extension zeroes the dropped copy for cols 6-9 as well, guarded by the
  recorded expected cents; the guard fails loudly if the staged file ever
  stops matching. Effect on roster totals: receipts -$5,640,855.75,
  disbursements -$5,239,012.32, transfers-from-auth -$1,261,797.03,
  transfers-to-auth -$3,300.00. Any OTHER group whose dropped copy differs
  from the kept copy on any column is still flagged in data_notes and in
  the JSON meta block, NOT silently corrected.
  Guard: the kept row's col 18 and each dropped row's col 18 must equal
  the recorded dedup `amount`, else the script fails loudly.

UNKNOWN vs ZERO: Alan Armstrong (person_key A000383) has no FEC candidate
  IDs in the roster (appointed senator, never ran for the seat). His
  career and 2026 values are null (blank in the CSV, null in JSON), NOT
  zero — matching the dataset convention ('unknown'). Persons WITH IDs but
  no weball rows get 0.00 for flow columns and blank for stock columns.

Amounts are summed as integer cents (same convention as pull_money.py);
outputs are dollars with 2 decimals.
"""
import csv
import json
import os
from collections import defaultdict
from decimal import Decimal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
SRC = str(ROOT / CFG['paths']['source'])
IM = str(ROOT / CFG['paths']['intermediate'])
BULK = str(ROOT / CFG['paths']['bulk'])
CYCLES = list(range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2))
CURRENT_CYCLE = CFG['cycles']['current']

# weball 0-indexed positions (1-indexed col in comments above)
COL_RECEIPTS = 5       # 6
COL_FROM_AUTH = 6      # 7
COL_DISB = 7           # 8
COL_TO_AUTH = 8        # 9
COL_COH_COP = 10       # 11
COL_CAND_CONTRIB = 11  # 12
COL_CAND_LOANS = 12    # 13
COL_CAND_REPAY = 14    # 15
COL_OTHER_REPAY = 15   # 16
COL_DEBTS_BY = 16      # 17
COL_INDIV = 17         # 18 (dedup guard only)
COL_CVG_END = 27       # 28

# raw cols 6-18 (0-indexed 5..17) kept for the dedup step, which operates
# column-by-column on the raw values before fields are derived.
RAW_COLS = list(range(5, 18))


def cents(s):
    s = (s or '').strip()
    if not s:
        return 0
    return int((Decimal(s) * 100).to_integral_value())


def fmt(c):
    if c is None:
        return ''
    return f"{c / 100:.2f}"


def fmt_json(c):
    if c is None:
        return None
    return f"{c / 100:.2f}"


roster = json.load(open(os.path.join(IM, 'roster.json')))
cand_to_persons = defaultdict(list)
for p in roster:
    for cid in (p.get('fec_candidate_ids') or []):
        cand_to_persons[cid].append(p['person_key'])
roster_cands = set(cand_to_persons)
persons = {p['person_key']: p for p in roster}

# ---------------- weball scan ----------------
# raw[(cand, cycle)] = list of cents for raw cols 6-18, plus coverage end date
raw = {}
cvg = {}
had_weball = set()
weball_rows = weball_matched = weball_bad = 0
for cy in CYCLES:
    yy = f"{cy % 100:02d}"
    path = os.path.join(BULK, 'weball', f'weball{yy}.txt')
    with open(path) as f:
        for line in f:
            weball_rows += 1
            p = line.rstrip('\n').split('|')
            if len(p) != 30:
                weball_bad += 1
                continue
            cid = p[0]
            if cid in roster_cands:
                weball_matched += 1
                had_weball.add(cid)
                raw[(cid, cy)] = [cents(p[i]) for i in RAW_COLS]
                cvg[(cid, cy)] = p[COL_CVG_END]

# ---------------- dedup (column-level) ----------------
dedup = json.load(open(os.path.join(SRC, 'dedup-applied.json')))
dedup_flags = []  # (person_key, name, cycle, kept_id, dropped_id, col, kept, dropped)
n_dedup_groups = 0
n_cells_zeroed = 0
for e in dedup:
    cy = e['cycle']
    pk = e['person_key']
    if pk not in persons:
        raise SystemExit(f"dedup-applied.json has unknown person_key {pk}")
    kept = raw.get((e['kept_id'], cy))
    if kept is None:
        raise SystemExit(f"{e['name']} {cy}: kept entry {e['kept_id']} not in weball")
    if kept[COL_INDIV - 5] != cents(e['amount']):
        raise SystemExit(f"{e['name']} {cy}: kept TTL_INDIV_CONTRIB "
                         f"{kept[COL_INDIV - 5] / 100:.2f} != recorded {e['amount']}")
    n_dedup_groups += 1
    extend = bool(e.get('extend_to_columns_6_9'))
    exp = e.get('extend_expected_cents') or {}
    for did in e['dropped_ids']:
        dropped = raw.get((did, cy))
        if dropped is None:
            raise SystemExit(f"{e['name']} {cy}: dropped entry {did} not in weball")
        if dropped[COL_INDIV - 5] != cents(e['amount']):
            raise SystemExit(f"{e['name']} {cy}: dropped TTL_INDIV_CONTRIB "
                             f"{dropped[COL_INDIV - 5] / 100:.2f} != recorded {e['amount']}")
        if extend:
            # Curtis 2024 extension (recorded on the dedup entry): the
            # dropped copy is a strict subset of the kept copy —
            # kept-minus-dropped is $107,207.83 exactly for weball cols 6,
            # 7, 8 and cols 10-18 are byte-identical — so zero the dropped
            # copy for cols 6-9 as well. Guarded by the recorded expected
            # cents; fails loudly on mismatch.
            for j, key in ((0, 'col6_kept_minus_dropped'),
                           (1, 'col7_kept_minus_dropped'),
                           (2, 'col8_kept_minus_dropped')):
                if kept[COL_RECEIPTS - 5 + j] - dropped[COL_RECEIPTS - 5 + j] != exp.get(key):
                    raise SystemExit(f"{e['name']} {cy}: Curtis extension guard failed: "
                                     f"col {6 + j} kept-minus-dropped != recorded {key}")
            if dropped[COL_TO_AUTH - 5] != exp.get('col9_dropped'):
                raise SystemExit(f"{e['name']} {cy}: Curtis extension guard failed: "
                                 f"dropped col 9 != recorded col9_dropped")
            if kept[COL_TO_AUTH - 5] != exp.get('col9_kept'):
                raise SystemExit(f"{e['name']} {cy}: Curtis extension guard failed: "
                                 f"kept col 9 != recorded col9_kept")
        for j in range(len(RAW_COLS)):
            col_1indexed = RAW_COLS[j] + 1
            if extend and col_1indexed in (6, 7, 8, 9):
                # Extension: zero the dropped copy for receipts/transfers/
                # disbursements even though it differs from the kept copy.
                if dropped[j] != 0:
                    n_cells_zeroed += 1
                dropped[j] = 0
                continue
            if dropped[j] == kept[j]:
                if dropped[j] != 0:
                    n_cells_zeroed += 1
                dropped[j] = 0
            else:
                dedup_flags.append({
                    'person_key': pk, 'name': e['name'], 'cycle': cy,
                    'kept_id': e['kept_id'], 'dropped_id': did,
                    'column_1indexed': RAW_COLS[j] + 1,
                    'kept_value': fmt(kept[j]), 'dropped_value': fmt(dropped[j]),
                })

# ---------------- derive per-(cand, cycle) fields ----------------
# field order: receipts, from_auth, disb, to_auth, coh_cop, cand_contrib,
# cand_loans, loan_repay (15+16), debts_by
def derive(v):
    return {
        'total_receipts': v[COL_RECEIPTS - 5],
        'transfers_from_auth': v[COL_FROM_AUTH - 5],
        'total_disbursements': v[COL_DISB - 5],
        'transfers_to_auth': v[COL_TO_AUTH - 5],
        'cash_on_hand': v[COL_COH_COP - 5],
        'candidate_contributions': v[COL_CAND_CONTRIB - 5],
        'candidate_loans': v[COL_CAND_LOANS - 5],
        'loan_repayments': v[COL_CAND_REPAY - 5] + v[COL_OTHER_REPAY - 5],
        'debts_owed_by': v[COL_DEBTS_BY - 5],
        'debts_owed_to': None,  # no weball column (see header)
    }


FLOW_FIELDS = ['candidate_contributions', 'candidate_loans', 'loan_repayments',
               'total_receipts', 'total_disbursements',
               'transfers_from_auth', 'transfers_to_auth']
STOCK_FIELDS = ['cash_on_hand', 'debts_owed_by']

per_cycle = {}
csv_rows = []
for p in roster:
    pk = p['person_key']
    ids = p.get('fec_candidate_ids') or []
    entries = []
    for cy in CYCLES:
        for cid in ids:
            v = raw.get((cid, cy))
            if v is None:
                continue
            d = derive(v)
            if any(d[f] for f in FLOW_FIELDS + STOCK_FIELDS):
                entries.append({'cycle': cy, 'candidate_id': cid,
                                'candidate_contributions': fmt_json(d['candidate_contributions']),
                                'candidate_loans': fmt_json(d['candidate_loans']),
                                'loan_repayments': fmt_json(d['loan_repayments']),
                                'debts_owed_by': fmt_json(d['debts_owed_by']),
                                'debts_owed_to': None,
                                'total_receipts': fmt_json(d['total_receipts']),
                                'total_disbursements': fmt_json(d['total_disbursements']),
                                'cash_on_hand': fmt_json(d['cash_on_hand']),
                                'transfers_from_auth': fmt_json(d['transfers_from_auth']),
                                'transfers_to_auth': fmt_json(d['transfers_to_auth']),
                                'coverage_end_date': cvg.get((cid, cy), '')})
    per_cycle[pk] = {'person_key': pk, 'full_name': p['full_name'],
                     'fec_candidate_ids': ids, 'per_cycle': entries}

    # career aggregates: flows summed; stocks = latest cycle with a row
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster — self-funding unknown (null, not zero)')
        career = {f: None for f in FLOW_FIELDS + STOCK_FIELDS}
        career['self_funding'] = None
        cy2026 = {f: None for f in FLOW_FIELDS + STOCK_FIELDS}
        cy2026['self_funding'] = None
        coh_cycle = debts_cycle = ''
    else:
        career = {f: sum(derive(raw[(cid, cy)])[f]
                         for cid in ids for cy in CYCLES if (cid, cy) in raw)
                  for f in FLOW_FIELDS}
        career['self_funding'] = career['candidate_contributions'] + career['candidate_loans']
        # stocks: latest cycle with a weball row for this person (any ID)
        have_cycles = sorted({cy for cid in ids for cy in CYCLES if (cid, cy) in raw})
        if have_cycles:
            latest = have_cycles[-1]
            coh_cycle = str(latest)
            debts_cycle = str(latest)
            career['cash_on_hand'] = sum(derive(raw[(cid, latest)])['cash_on_hand']
                                         for cid in ids if (cid, latest) in raw)
            career['debts_owed_by'] = sum(derive(raw[(cid, latest)])['debts_owed_by']
                                          for cid in ids if (cid, latest) in raw)
        else:
            notes.append('no weball rows found')
            coh_cycle = debts_cycle = ''
            career['cash_on_hand'] = None
            career['debts_owed_by'] = None
        cy2026 = {f: sum(derive(raw[(cid, CURRENT_CYCLE)])[f]
                         for cid in ids if (cid, CURRENT_CYCLE) in raw)
                  for f in FLOW_FIELDS}
        cy2026['self_funding'] = cy2026['candidate_contributions'] + cy2026['candidate_loans']
        if (CURRENT_CYCLE in have_cycles):
            cy2026['cash_on_hand'] = sum(derive(raw[(cid, CURRENT_CYCLE)])['cash_on_hand']
                                         for cid in ids if (cid, CURRENT_CYCLE) in raw)
            cy2026['debts_owed_by'] = sum(derive(raw[(cid, CURRENT_CYCLE)])['debts_owed_by']
                                          for cid in ids if (cid, CURRENT_CYCLE) in raw)
        else:
            cy2026['cash_on_hand'] = None
            cy2026['debts_owed_by'] = None
        if any(cid in had_weball for cid in ids) is False:
            pass  # already covered by 'no weball rows found'
    dup = [q for cid in ids for q in cand_to_persons[cid] if q != pk]
    if dup:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(sorted(set(dup))))
    for fl in dedup_flags:
        if fl['person_key'] == pk:
            notes.append(
                f"dedup partial {fl['cycle']}: weball col {fl['column_1indexed']} differs "
                f"between kept {fl['kept_id']} (${fl['kept_value']}) and dropped "
                f"{fl['dropped_id']} (${fl['dropped_value']}); both copies counted "
                f"for that column (recorded dedup covers TTL_INDIV_CONTRIB only)")
    row = {'person_key': pk, 'full_name': p['full_name'],
           'fec_candidate_ids': ';'.join(ids)}
    for f in FLOW_FIELDS + ['self_funding']:
        row[f + '_career'] = fmt(career[f])
    for f in STOCK_FIELDS:
        row[f + '_career'] = fmt(career[f])
    row['debts_owed_to_career'] = ''  # no weball column
    row['cash_on_hand_cycle'] = coh_cycle
    row['debts_owed_by_cycle'] = debts_cycle
    for f in FLOW_FIELDS + ['self_funding']:
        row[f + '_2026'] = fmt(cy2026[f])
    for f in STOCK_FIELDS:
        row[f + '_2026'] = fmt(cy2026[f])
    row['debts_owed_to_2026'] = ''
    row['data_notes'] = ' | '.join(notes)
    csv_rows.append(row)

CSV_FIELDS = (['person_key', 'full_name', 'fec_candidate_ids']
              + [f + '_career' for f in
                 ['candidate_contributions', 'candidate_loans', 'loan_repayments',
                  'debts_owed_by', 'debts_owed_to', 'total_receipts',
                  'total_disbursements', 'cash_on_hand', 'transfers_from_auth',
                  'transfers_to_auth', 'self_funding']]
              + ['cash_on_hand_cycle', 'debts_owed_by_cycle']
              + [f + '_2026' for f in
                 ['candidate_contributions', 'candidate_loans', 'loan_repayments',
                  'debts_owed_by', 'debts_owed_to', 'total_receipts',
                  'total_disbursements', 'cash_on_hand', 'transfers_from_auth',
                  'transfers_to_auth', 'self_funding']]
              + ['data_notes'])

with open(os.path.join(IM, 'self_funding.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    w.writeheader()
    w.writerows(csv_rows)

meta = {
    'source': 'staged bulk weball files data/raw/weball/weballYY.txt, cycles 1980-2026',
    'data_as_of': CFG.get('data_as_of'),
    'column_map_1indexed': {
        'total_receipts': 6, 'transfers_from_auth': 7, 'total_disbursements': 8,
        'transfers_to_auth': 9, 'cash_on_hand_coh_cop': 11,
        'candidate_contributions': 12, 'candidate_loans': 13,
        'loan_repayments_cand_loan_repay_plus_other_loan_repay': '15+16',
        'debts_owed_by': 17, 'coverage_end_date': 28,
        'debts_owed_to': None,
    },
    'debts_owed_to_note': 'No weball column exists for debts owed TO the committee; '
                          'output as null everywhere, never zero. FEC API spot-check '
                          '(Constantino, cycles 2024 and 2026): '
                          'last_debts_owed_to_committee $0.00.',
    'weball_vs_api': 'FEC API candidate-totals endpoint (DEMO_KEY, Nov 12, 2026) '
                     'returns values identical to weball to the cent for Constantino '
                     'H6NY21157 in both cycles 2024 and 2026. The $17,000,000 loan / '
                     '$17,064,951 receipts figures are CAREER sums (2024 $2.6M + 2026 '
                     '$14.4M), not 2026-only values; there is no weball-vs-API '
                     'discrepancy at matched coverage. Caveat is timeliness only: '
                     'staged 2026 weball covers through 10/14/2026 (pre-general).',
    'aggregation': 'Flows summed across cycles; cash_on_hand and debts_owed_by '
                   'are stocks = latest cycle value (see cash_on_hand_cycle / '
                   'debts_owed_by_cycle).',
    'dedup': {'groups_in_record': len(dedup), 'groups_applied': n_dedup_groups,
              'identical_cells_zeroed': n_cells_zeroed,
              'differing_columns_flagged_not_corrected': dedup_flags},
    'weball_rows_scanned': weball_rows, 'weball_rows_matched_roster': weball_matched,
    'weball_bad_field_count_rows': weball_bad,
}

with open(os.path.join(IM, 'self_funding_per_cycle.json'), 'w') as f:
    json.dump({'meta': meta, 'persons': per_cycle}, f, indent=1)

# ---------------- validation ----------------
def career_self(pk):
    r = next(x for x in csv_rows if x['person_key'] == pk)
    return Decimal(r['self_funding_career']) if r['self_funding_career'] else None


named = {
    'S001217': ('Rick Scott', Decimal('90000000')),
    'R000618': ('Pete Ricketts', Decimal('19400000')),
    'T000488': ('Shri Thanedar', Decimal('17500000')),
    'anthonyconstantinonyhouse': ('Anthony Constantino', Decimal('17000000')),
    'M001232': ('April McClain Delaney', Decimal('14900000')),
    'J000305': ('Sara Jacobs', Decimal('11600000')),
    'C001123': ('Gilbert Ray Cisneros, Jr.', Decimal('9800000')),
    'S001229': ('Jefferson Shreve', Decimal('7900000')),
}
print('persons:', len(csv_rows))
print('weball rows scanned:', weball_rows, 'matched roster:', weball_matched,
      'bad field-count rows:', weball_bad)
print('dedup groups applied:', n_dedup_groups, 'identical cells zeroed:', n_cells_zeroed,
      'differing columns flagged:', len(dedup_flags))
all_ok = True
for pk, (name, expect) in named.items():
    got = career_self(pk)
    ok = got is not None and abs(got - expect) <= Decimal('50000')
    all_ok &= ok
    print(f"named {name}: career self-funding ${got:,.2f} vs expected ~${expect:,.0f} "
          f"{'OK' if ok else 'MISMATCH'}")
# roster counts, per person (deduped), strict >
selfs = {r['person_key']: (Decimal(r['self_funding_career'])
                           if r['self_funding_career'] else None) for r in csv_rows}
vals = [v for v in selfs.values() if v is not None]
print('per-person (deduped) counts: any != 0:',
      sum(1 for v in vals if v != 0),
      '> $100k:', sum(1 for v in vals if v > 100000),
      '> $1M:', sum(1 for v in vals if v > 1000000),
      '> $5M:', sum(1 for v in vals if v > 5000000))
# reconciliation with the earlier weball scan figures: those were per
# candidate-ID, raw (pre-dedup), strict > — reproduced here for the record.
idself = defaultdict(int)
raw_check = {}
for cy in CYCLES:
    yy = f"{cy % 100:02d}"
    for line in open(os.path.join(BULK, 'weball', f'weball{yy}.txt')):
        p = line.rstrip('\n').split('|')
        if len(p) == 30 and p[0] in roster_cands:
            raw_check[p[0]] = raw_check.get(p[0], 0) + cents(p[11]) + cents(p[12])
print('per-ID raw (pre-dedup) counts, matching the earlier scan: any != 0:',
      sum(1 for v in raw_check.values() if v != 0),
      '> $100k:', sum(1 for v in raw_check.values() if v > 100000 * 100),
      '> $1M:', sum(1 for v in raw_check.values() if v > 1000000 * 100),
      '> $5M:', sum(1 for v in raw_check.values() if v > 5000000 * 100))
ds = {r['person_key']: r for r in
      json.load(open(ROOT / CFG['paths']['dataset_json']))}
exceed = [pk for pk, v in selfs.items()
          if v is not None and ds.get(pk) is not None
          and ds[pk]['total_accepted_career'] is not None
          and v > Decimal(str(ds[pk]['total_accepted_career']))]
print('self-funding exceeds tracker total_accepted:', len(exceed),
      '(17 excluding Constantino, whose total_accepted is $0.00)')
print('Armstrong (A000383) self_funding_career:',
      next(r['self_funding_career'] for r in csv_rows if r['person_key'] == 'A000383')
      or 'NULL (blank)')
print('Constantino career receipts:',
      next(r['total_receipts_career'] for r in csv_rows
           if r['person_key'] == 'anthonyconstantinonyhouse'),
      'disbursements:',
      next(r['total_disbursements_career'] for r in csv_rows
           if r['person_key'] == 'anthonyconstantinonyhouse'))
print('VALIDATION', 'PASS' if all_ok else 'FAIL — named-case mismatch')
