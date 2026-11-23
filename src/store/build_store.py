#!/usr/bin/env python3
"""Build the silver store (DuckDB) from the pinned FEC snapshot and the roster."""
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import load_config
from src.domain.committee_classes import committee_class
from src.domain.committee_money import ReportedOnce, is_voided_earmark
from src.domain.outside_spending import LatestFiling, exclusion
from src.domain.roster import candidate_ids
from src.domain.weball_double_counts import FINANCIAL_FIELDS, remove_double_counts
from src.fec.committee_contributions import committee_contributions
from src.fec.committees import committees
from src.fec.independent_expenditures import independent_expenditures
from src.fec.weball import candidate_summaries

CFG = load_config()
ROOT = CFG['_root']
BULK = ROOT / CFG['paths']['bulk']
STORE = ROOT / CFG['paths']['store']
SOURCE = ROOT / CFG['paths']['source']
CAREER_CYCLES = range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2)
IE_CYCLES = CFG['cycles']['udp']
AIPAC_PAC = CFG['committees']['aipac_pac']
VOIDED_EARMARK = 'voided_earmark'
REPORTED_AGAIN = 'reported_again'


def people_rows(roster):
    people = [{'person_key': p['person_key'], 'full_name': p['full_name'],
               'first_name': p.get('first_name'), 'last_name': p.get('last_name')}
              for p in roster]
    ids = [{'person_key': p['person_key'], 'candidate_id': candidate_id, 'position': position}
           for p in roster for position, candidate_id in enumerate(candidate_ids(p))]
    return people, ids


def read_summaries():
    """{(candidate_id, cycle): (summary, {field: Money})} for every weball row."""
    found = {}
    for cycle in CAREER_CYCLES:
        for summary in candidate_summaries(BULK, cycle):
            amounts = {field: summary.amount(field) for field in FINANCIAL_FIELDS}
            found[summary.candidate_id, cycle] = (summary, amounts)
    return found


def summary_row(key, summary, amounts):
    candidate_id, cycle = key
    return {'candidate_id': candidate_id, 'cycle': cycle, 'name': summary.name,
            'office_state': summary.office_state, 'office_district': summary.office_district,
            'party': summary.party,
            **{f'{field}_cents': amount.cents for field, amount in amounts.items()},
            'other_committee_contributions_cents':
                summary.amount('other_committee_contributions').cents,
            'coverage_end': summary.coverage_end}


def counted_once(summaries, dedup_records, person_keys):
    """Apply the recorded double-count corrections; return counted amounts and the audit rows."""
    counted = {key: dict(amounts) for key, (_, amounts) in summaries.items()}
    remove_double_counts(counted, dedup_records, person_keys)
    kept_by_dropped = {(dropped_id, record['cycle']): (record['person_key'], record['kept_id'])
                       for record in dedup_records for dropped_id in record['dropped_ids']}
    corrections = [
        {'person_key': kept_by_dropped[key][0], 'candidate_id': key[0], 'cycle': key[1],
         'field': field, 'filed_cents': filed.cents, 'counted_cents': counted[key][field].cents,
         'kept_id': kept_by_dropped[key][1]}
        for key, (_, amounts) in summaries.items() if key in kept_by_dropped
        for field, filed in amounts.items() if counted[key][field] != filed]
    return counted, corrections


def committee_rows():
    for cycle in CAREER_CYCLES:
        for c in committees(BULK, cycle):
            yield {'committee_id': c.committee_id, 'cycle': cycle, 'name': c.name,
                   'committee_type': c.committee_type, 'designation': c.designation,
                   'organization_type': c.organization_type,
                   'committee_class': committee_class(c, AIPAC_PAC).value}


def contribution_row(contribution, cycle, excluded_because):
    return {'committee_id': contribution.committee_id,
            'candidate_id': contribution.candidate_id, 'cycle': cycle,
            'amount_cents': contribution.amount.cents, 'is_earmark': contribution.is_earmark,
            'date': contribution.date, 'excluded_because': excluded_because}


def contribution_rows():
    """Every contribution to a candidate, each counted once.

    Voided earmarks are set aside before duplicates are matched, as the
    money pulls have always done.
    """
    for cycle in CAREER_CYCLES:
        reported_once = ReportedOnce()
        for contribution in committee_contributions(BULK, cycle):
            if not contribution.is_to_candidate:
                continue
            if is_voided_earmark(contribution):
                yield contribution_row(contribution, cycle, VOIDED_EARMARK)
                continue
            reported_once.add(contribution)
        for contribution in reported_once:
            yield contribution_row(contribution, cycle, None)
        for contribution in reported_once.dropped_contributions:
            yield contribution_row(contribution, cycle, REPORTED_AGAIN)


def identified_candidates(roster):
    found = {candidate_id for p in roster for candidate_id in candidate_ids(p)}
    for cycle in CAREER_CYCLES:
        found |= {s.candidate_id for s in candidate_summaries(BULK, cycle)}
    return found


def outside_spending_rows(roster):
    identified = identified_candidates(roster)
    for cycle in IE_CYCLES:
        registered = {c.committee_id for c in committees(BULK, cycle)}
        filings = LatestFiling()
        for expenditure in independent_expenditures(BULK / 'ie', cycle):
            filings.add(expenditure)
        for e in filings:
            yield {'spender_id': e.spender_id, 'spender_name': e.spe_nam.strip(),
                   'candidate_id': e.candidate_id, 'candidate_name': e.cand_name.strip(),
                   'cycle': e.cycle, 'direction': e.direction, 'amount_cents': e.amount.cents,
                   'office': e.can_office.strip(), 'office_state': e.can_office_state.strip(),
                   'office_district': e.can_office_dis.strip(),
                   'expenditure_date': e.exp_date.strip(),
                   'excluded_because': exclusion(e, registered, identified)}


def batches(rows, size=250_000):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def insert(db, table, rows):
    count = 0
    for batch in batches(rows):
        db.register('incoming', pd.DataFrame(batch))
        db.execute(f'INSERT INTO {table} BY NAME SELECT * FROM incoming')
        db.unregister('incoming')
        count += len(batch)
    print(f'{table}: {count:,} rows')


def main():
    with open(ROOT / CFG['paths']['roster']) as f:
        roster = json.load(f)
    with open(SOURCE / 'dedup-applied.json') as f:
        dedup_records = json.load(f)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.unlink(missing_ok=True)
    with duckdb.connect(str(STORE)) as db:
        db.execute((Path(__file__).parent / 'schema.sql').read_text())
        people, ids = people_rows(roster)
        insert(db, 'people', people)
        insert(db, 'person_candidate_ids', ids)
        summaries = read_summaries()
        counted, corrections = counted_once(summaries, dedup_records,
                                            {p['person_key'] for p in roster})
        insert(db, 'candidate_summaries',
               (summary_row(key, s, amounts) for key, (s, amounts) in summaries.items()))
        insert(db, 'counted_summaries',
               (summary_row(key, s, counted[key]) for key, (s, _) in summaries.items()))
        insert(db, 'summary_corrections', corrections)
        insert(db, 'committees', committee_rows())
        insert(db, 'committee_contributions', contribution_rows())
        insert(db, 'outside_spending', outside_spending_rows(roster))
        db.execute((Path(__file__).parent / 'views.sql').read_text())


if __name__ == '__main__':
    main()
