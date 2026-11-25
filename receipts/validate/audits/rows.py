"""Row count, unique keys, row order, and CSV agreeing with JSON field by field."""

import pandas as pd

from receipts.common.files import read_json
from receipts.common.settings import settings


def unfolded_keys(roster):
    """Roster keys in order, without a later entry that shares an FEC ID with an earlier one."""
    keys, seen = [], set()
    for row in roster:
        ids = set(row['fec_candidate_ids'] or [])
        if not ids & seen:
            keys.append(row['person_key'])
        seen |= ids
    return keys


def rows_and_order(audit, dataset):
    """(i) row count, uniqueness, order"""
    audit.pin('row count', 'rows.count', len(dataset.records))
    audit.check('person_keys unique', len(dataset.by_key) == len(dataset.records))
    roster_keys = unfolded_keys(read_json(settings().paths.roster))
    audit.check(
        'row order matches roster.json', [r['person_key'] for r in dataset.records] == roster_keys
    )


def csv_matches_json(audit, dataset):
    """(h) CSV <-> JSON agreement"""
    df = pd.read_csv(dataset.csv_path, dtype=str, keep_default_na=False)
    audit.check(
        'CSV has one data row per JSON record',
        len(df) == len(dataset.records),
        f'CSV {len(df)}, JSON {len(dataset.records)}',
    )
    csv_by_key = {row['person_key']: row for _, row in df.iterrows()}
    audit.check('CSV person_keys match JSON', set(csv_by_key) == set(dataset.by_key))
    mism = 0
    json_keys = settings().dataset.json_keys
    for pk, r in dataset.by_key.items():
        crow = csv_by_key.get(pk)
        if crow is None:
            continue
        for k in json_keys:
            if k in ('all_ie_top_committees', 'cycles'):
                continue  # JSON-only by design; not in the CSV.
            cv, jv = crow[k], r[k]
            if k in (
                'per_cycle',
                'udp_per_cycle',
                'self_funding_per_cycle',
                'other_committees_per_cycle',
                'all_ie_per_cycle',
                'pro_israel_per_cycle',
                'fec_candidate_ids',
            ):
                if cv != repr(jv):
                    mism += 1
            elif k == 'clean_2026':
                want = '' if jv is None else str(jv)
                if cv != want:
                    mism += 1
            elif jv is None:
                if cv != '':
                    mism += 1
            elif isinstance(jv, (int, float)) and not isinstance(jv, bool):
                # Numeric compare: pandas writes a mixed int/float column
                # as floats ('510.0' for JSON int 510) because Armstrong's
                # null forces the column to float dtype. Same value,
                # different string form.
                if cv == '' or float(cv) != float(jv):
                    mism += 1
            else:
                if cv != str(jv):
                    mism += 1
    audit.check('CSV and JSON agree field by field', mism == 0, f'{mism} mismatches')
