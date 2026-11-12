#!/usr/bin/env python3
"""Ranking columns for the Congress money tracker (methodology §12).

- `total_accepted_career` = individual contributions + corporate PAC
  money + AIPAC PAC direct. The two earmark columns are subsets of their
  parent columns and are never added again. UDP independent expenditures
  are NOT counted as accepted — that money was never given to the
  campaign, it was spent about the race — but UDP support is ranked
  separately in its own column.
- Ranks (`rank_total_accepted`, `rank_individual`, `rank_corporate_pac`,
  `rank_aipac_direct`, `rank_udp_support`, `rank_udp_opposing_opponents`,
  `rank_udp_total_benefit`, `rank_self_funding`, `rank_all_ie_support`,
  `rank_all_ie_oppose`, `rank_all_ie_total`,
  `rank_other_committees_total`): 1 = most money, ties share a rank
  (competition ranking: rank = 1 + the number of people with strictly
  more). Ranks are computed over all 664 people; Alan Armstrong is
  unranked (money unknown, not zero) — his `total_accepted_career` and
  all twelve ranks are null. A negative total (Patrick Ryan, AIPAC
  -$10,000) ranks as filed.

Reads the dataset written by `merge_dataset.py`, adds the columns, and
rewrites both files in the final column order (the 2026 columns are
added later by `compute_2026.py`). All other values are carried through
untouched. `all_ie_top_committees` is JSON-only by design: it is carried
through the JSON and has no CSV column, so the CSV/JSON order check
below allows for exactly that one key.
"""
import json

import pandas as pd

from config import load_config

CFG = load_config()
ROOT = CFG['_root']

RANK_DEFS = [
    ('rank_total_accepted', 'total_accepted_career'),
    ('rank_individual', 'individual_contribution_total_career'),
    ('rank_corporate_pac', 'corporate_pac_career'),
    ('rank_aipac_direct', 'aipac_pac_direct_career'),
    ('rank_udp_support', 'udp_ie_support_career'),
    ('rank_udp_opposing_opponents', 'udp_ie_opposing_opponents_career'),
    ('rank_udp_total_benefit', 'udp_ie_total_benefit_career'),
    ('rank_self_funding', 'self_funding_career'),
    ('rank_all_ie_support', 'all_ie_support_career'),
    ('rank_all_ie_oppose', 'all_ie_oppose_career'),
    ('rank_all_ie_total', 'all_ie_total_career'),
    ('rank_other_committees_total', 'other_committees_total_career'),
]


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def competition_ranks(records, value_col):
    """rank = 1 + count of strictly greater values (numeric rows only)."""
    values = [r[value_col] for r in records if is_num(r[value_col])]
    ranks = {}
    for r in records:
        v = r[value_col]
        if not is_num(v):
            ranks[r['person_key']] = None
        else:
            ranks[r['person_key']] = 1 + sum(1 for x in values if x > v)
    return ranks


records = json.load(open(ROOT / CFG['paths']['dataset_json']))

# total_accepted_career
for r in records:
    ind, corp, aipac = (r['individual_contribution_total_career'],
                        r['corporate_pac_career'], r['aipac_pac_direct_career'])
    if is_num(ind) and is_num(corp) and is_num(aipac):
        r['total_accepted_career'] = round(ind + corp + aipac, 2)
    else:
        r['total_accepted_career'] = None

# ranks
rank_maps = {rank_col: competition_ranks(records, val_col)
             for rank_col, val_col in RANK_DEFS}
for r in records:
    for rank_col, _ in RANK_DEFS:
        r[rank_col] = rank_maps[rank_col][r['person_key']]

# Rebuild in the final column order (minus the 2026 columns, which do
# not exist yet). CSV and JSON orders agree for these columns except for
# all_ie_top_committees, which is JSON-only by design.
csv_cols = [c for c in CFG['dataset']['csv_columns'] if '2026' not in c]
json_keys = [k for k in CFG['dataset']['json_keys'] if '2026' not in k]
assert [k for k in json_keys if k != 'all_ie_top_committees'] == csv_cols, \
    'CSV/JSON orders diverge before the 2026 columns (beyond all_ie_top_committees)'
assert 'all_ie_top_committees' in json_keys, 'all_ie_top_committees missing from json_keys'
ordered = [{k: r[k] for k in json_keys} for r in records]

with open(ROOT / CFG['paths']['dataset_json'], 'w') as f:
    json.dump(ordered, f, indent=1)
print(f"wrote {CFG['paths']['dataset_json']} ({len(ordered)} rows)")
pd.DataFrame(ordered, columns=csv_cols).to_csv(ROOT / CFG['paths']['dataset_csv'], index=False)
print(f"wrote {CFG['paths']['dataset_csv']} ({len(ordered)} rows)")

top = sorted((r for r in records if is_num(r['total_accepted_career'])),
             key=lambda r: -r['total_accepted_career'])[:10]
print('top 10 by total accepted (career):')
for r in top:
    print(f"  {r['rank_total_accepted']:>3} {r['full_name']:<30} ${r['total_accepted_career']:,.2f}")
