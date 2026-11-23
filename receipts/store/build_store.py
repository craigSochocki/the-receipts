#!/usr/bin/env python3
"""Build the silver store (DuckDB) from the pinned FEC snapshot and the roster."""

from collections import defaultdict
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from receipts.common import baseline
from receipts.common.settings import (
    AIPAC_PAC,
    CAREER_CYCLES,
    IE_CYCLES,
    PATHS,
    WINRED,
    load_double_count_records,
    load_roster,
)
from receipts.domain.committee_classes import committee_class, unclassified_kind
from receipts.domain.committee_money import is_voided_earmark, reported_once
from receipts.domain.money import Money
from receipts.domain.outside_spending import exclusion, latest_filings
from receipts.domain.roster import candidate_ids
from receipts.domain.seats import house_seat_id
from receipts.domain.weball_double_counts import FINANCIAL_FIELDS, remove_double_counts
from receipts.fec.committee_contributions import committee_contributions
from receipts.fec.committees import committees
from receipts.fec.independent_expenditures import independent_expenditures
from receipts.fec.weball import candidate_summaries
from receipts.store import congress

BULK, STORE, SOURCE = PATHS.bulk, PATHS.store, PATHS.source
CANDIDATE_SNAPSHOT = BULK / 'cn' / 'SNAPSHOT'
VOIDED_EARMARK = 'voided_earmark'
REPORTED_AGAIN = 'reported_again'


def people_rows(roster, legislators_119th):
    people = [
        {
            'person_key': p['person_key'],
            'full_name': p['full_name'],
            'first_name': p.get('first_name'),
            'last_name': p.get('last_name'),
            'roster_position': position,
        }
        for position, p in enumerate(roster)
    ]
    on_roster = {p['person_key'] for p in roster}
    for legislator in legislators_119th:
        if legislator['id']['bioguide'] not in on_roster:
            name = legislator['name']
            people.append(
                {
                    'person_key': legislator['id']['bioguide'],
                    'full_name': name.get('official_full') or f'{name["first"]} {name["last"]}',
                    'first_name': name['first'],
                    'last_name': name['last'],
                    'roster_position': None,
                }
            )
    ids = [
        {'person_key': p['person_key'], 'candidate_id': candidate_id, 'position': position}
        for p in roster
        for position, candidate_id in enumerate(candidate_ids(p))
    ]
    return people, ids


def read_summaries(files_read):
    """{(candidate_id, cycle): (summary, {field: Money})} for every weball row."""
    found = {}
    for cycle in CAREER_CYCLES:
        weball = candidate_summaries(BULK, cycle)
        for summary in weball:
            amounts = {field: summary.amount(field) for field in FINANCIAL_FIELDS}
            found[summary.candidate_id, cycle] = (summary, amounts)
        files_read.append(read_counts('weball', cycle, weball))
    return found


def summary_row(key, summary, amounts):
    candidate_id, cycle = key
    return {
        'candidate_id': candidate_id,
        'cycle': cycle,
        'name': summary.name,
        'office_state': summary.office_state,
        'office_district': summary.office_district,
        'party': summary.party,
        **{f'{field}_cents': amount.cents for field, amount in amounts.items()},
        'other_committee_contributions_cents': summary.amount(
            'other_committee_contributions'
        ).cents,
        'coverage_end': summary.coverage_end,
    }


def counted_once(summaries, dedup_records, person_keys):
    """Apply the recorded double-count corrections; return counted amounts and the audit rows."""
    counted = {key: dict(amounts) for key, (_, amounts) in summaries.items()}
    report = remove_double_counts(counted, dedup_records, person_keys)
    kept_by_dropped = {
        (dropped_id, record['cycle']): (record['person_key'], record['kept_id'])
        for record in dedup_records
        for dropped_id in record['dropped_ids']
    }
    corrections = [
        {
            'person_key': kept_by_dropped[key][0],
            'candidate_id': key[0],
            'cycle': key[1],
            'field': field,
            'filed_cents': filed.cents,
            'counted_cents': counted[key][field].cents,
            'kept_id': kept_by_dropped[key][1],
        }
        for key, (_, amounts) in summaries.items()
        if key in kept_by_dropped
        for field, filed in amounts.items()
        if counted[key][field] != filed
    ]
    differences = [
        {
            'position': position,
            'person_key': record['person_key'],
            'candidate_id': dropped_id,
            'cycle': record['cycle'],
            'field': field,
            'kept_id': record['kept_id'],
            'kept_cents': kept.cents,
            'dropped_cents': dropped.cents,
        }
        for position, (record, dropped_id, field, kept, dropped) in enumerate(report.differing)
    ]
    return counted, corrections, differences


def read_counts(file, cycle, bulk_file):
    return {
        'file': file,
        'cycle': cycle,
        'rows_read': bulk_file.rows_read,
        'columns': ','.join(getattr(bulk_file, 'columns', None) or []) or None,
    }


def committee_rows(files_read):
    for cycle in CAREER_CYCLES:
        registry = committees(BULK, cycle)
        for c in registry:
            yield {
                'committee_id': c.committee_id,
                'cycle': cycle,
                'name': c.name,
                'committee_type': c.committee_type,
                'designation': c.designation,
                'organization_type': c.organization_type,
                'committee_class': committee_class(c, AIPAC_PAC).value,
                'kind': unclassified_kind(c, WINRED),
            }
        files_read.append(read_counts('cm', cycle, registry))


def contribution_row(contribution, cycle, excluded_because):
    return {
        'committee_id': contribution.committee_id,
        'candidate_id': contribution.candidate_id,
        'cycle': cycle,
        'amount_cents': contribution.amount.cents,
        'is_earmark': contribution.is_earmark,
        'date': contribution.date,
        'excluded_because': excluded_because,
    }


def contribution_rows(files_read):
    """Every contribution to a candidate, each counted once.

    Voided earmarks are set aside before duplicates are matched, as the
    money pulls have always done.
    """
    for cycle in CAREER_CYCLES:
        filed_once = reported_once()
        filed = committee_contributions(BULK, cycle)
        for contribution in filed:
            if not contribution.is_to_candidate:
                continue
            if is_voided_earmark(contribution):
                yield contribution_row(contribution, cycle, VOIDED_EARMARK)
                continue
            filed_once.add(contribution)
        for contribution in filed_once:
            yield contribution_row(contribution, cycle, None)
        for contribution in filed_once.dropped:
            yield contribution_row(contribution, cycle, REPORTED_AGAIN)
        files_read.append(read_counts('pas2', cycle, filed))


def identified_candidates(roster):
    found = {candidate_id for p in roster for candidate_id in candidate_ids(p)}
    for cycle in CAREER_CYCLES:
        found |= {s.candidate_id for s in candidate_summaries(BULK, cycle)}
    return found


def outside_spending_row(e, file_order, excluded_because):
    return {
        'file_order': file_order,
        'spender_id': e.spender_id,
        'spender_name': e.spe_nam.strip(),
        'candidate_id': e.candidate_id,
        'candidate_name': e.cand_name.strip(),
        'cycle': e.cycle,
        'direction': e.direction,
        'amount_cents': e.amount.cents,
        'office': e.can_office.strip(),
        'office_state': e.can_office_state.strip(),
        'office_district': e.can_office_dis.strip(),
        'expenditure_date': e.exp_date.strip(),
        'election_type': e.ele_type.strip(),
        'transaction_id': e.tran_id.strip(),
        'excluded_because': excluded_because,
    }


def outside_spending_rows(roster, files_read):
    identified = identified_candidates(roster)
    for cycle in IE_CYCLES:
        registered = {c.committee_id for c in committees(BULK, cycle)}
        filings = latest_filings()
        filed = independent_expenditures(BULK / 'ie', cycle)
        for expenditure in filed:
            filings.add(expenditure)
        for file_order, e in enumerate(filings):
            yield outside_spending_row(e, file_order, exclusion(e, registered, identified))
        for e in filings.dropped:
            yield outside_spending_row(e, None, REPORTED_AGAIN)
        files_read.append(read_counts('ie', cycle, filed))


def congress_rows(roster):
    with open(SOURCE / 'house_maps.yaml') as f:
        new_map_states = set(yaml.safe_load(f)['new_map_for_2026'])
    legislators = congress.read_legislators(SOURCE)
    legislators_119th = [
        p for p in legislators if any(congress.served_in_119th(t) for t in p.get('terms', []))
    ]
    terms = list(congress.terms_119th(legislators_119th, new_map_states)) + list(
        congress.terms_120th(roster, new_map_states)
    )
    senate_classes = congress.senate_classes_by_state(terms)
    house_2024 = {
        (t['seat_id'].split('-')[1], int(t['seat_id'].split('-')[2].split('/')[0]))
        for t in terms
        if t['seat_id'].startswith('H-') and t['congress'] == 119
    }
    house_2026 = defaultdict(dict)
    for state, district in house_2024:
        if state in new_map_states:
            house_2026[state][district] = house_seat_id(state, district, 2026, new_map_states)
    seats = congress.seat_rows(terms, house_2026, senate_classes)
    candidacies = congress.candidacy_rows(
        BULK, CAREER_CYCLES, new_map_states, senate_classes, {seat['seat_id'] for seat in seats}
    )
    return legislators_119th, seats, terms, candidacies


def check_candidate_snapshot():
    pinned = baseline.candidates_snapshot()
    staged = CANDIDATE_SNAPSHOT.read_text().strip() if CANDIDATE_SNAPSHOT.exists() else None
    if staged != pinned and not baseline.rebaselining():
        raise SystemExit(
            f'staged candidate files are {staged}, but the baseline pins {pinned}; '
            f'run ./fetch_snapshot.sh'
        )


def double_count_rows(dedup_records):
    for record in dedup_records:
        for dropped_id in record['dropped_ids']:
            yield {
                'person_key': record['person_key'],
                'cycle': record['cycle'],
                'kept_id': record['kept_id'],
                'dropped_id': dropped_id,
                'amount_cents': Money.parse(record['amount']).cents,
            }


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
    roster = load_roster()
    dedup_records = load_double_count_records()
    check_candidate_snapshot()
    legislators_119th, seats, terms, candidacies = congress_rows(roster)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.unlink(missing_ok=True)
    with duckdb.connect(str(STORE)) as db:
        db.execute((Path(__file__).parent / 'schema.sql').read_text())
        people, ids = people_rows(roster, legislators_119th)
        insert(db, 'people', people)
        insert(db, 'person_candidate_ids', ids)
        files_read = []
        summaries = read_summaries(files_read)
        counted, corrections, differences = counted_once(
            summaries, dedup_records, {p['person_key'] for p in roster}
        )
        insert(
            db,
            'candidate_summaries',
            (summary_row(key, s, amounts) for key, (s, amounts) in summaries.items()),
        )
        insert(
            db,
            'counted_summaries',
            (summary_row(key, s, counted[key]) for key, (s, _) in summaries.items()),
        )
        insert(db, 'double_counts', double_count_rows(dedup_records))
        insert(db, 'summary_corrections', corrections)
        insert(db, 'summary_differences', differences)
        insert(db, 'committees', committee_rows(files_read))
        insert(db, 'committee_contributions', contribution_rows(files_read))
        insert(db, 'outside_spending', outside_spending_rows(roster, files_read))
        insert(db, 'files_read', files_read)
        insert(db, 'seats', seats)
        insert(db, 'terms', terms)
        insert(db, 'candidacies', candidacies)


if __name__ == '__main__':
    main()
