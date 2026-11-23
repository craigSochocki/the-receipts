#!/usr/bin/env python3
"""Career money per roster candidate, from the FEC bulk files.

Individual contributions come from weball; AIPAC PAC and corporate PAC
contributions from pas2, classified with the committee master (cm).
Rules and evidence: methodology.md §4, research/pull-log-a.md.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import load_config
from src.domain.committee_money import (ReportedOnce, Source, Tally, is_voided_earmark,
                                        tracked_source)
from src.domain.ledger import Ledger
from src.domain.money import ZERO, Money
from src.domain.roster import Roster, candidate_ids
from src.fec.committee_contributions import committee_contributions
from src.fec.committees import committees
from src.fec.weball import candidate_summaries

CFG = load_config()
ROOT = CFG['_root']
INTERMEDIATE = ROOT / CFG['paths']['intermediate']
BULK = ROOT / CFG['paths']['bulk']
CYCLES = range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2)
CURRENT_CYCLE = CFG['cycles']['current']
AIPAC_PAC = CFG['committees']['aipac_pac']

CAREER_COLUMNS = {
    'individual': 'individual_contribution_total_career',
    'aipac_pac_direct': 'aipac_pac_direct_career',
    'aipac_earmark_transmitted': 'aipac_earmark_transmitted_career',
    'corporate_pac': 'corporate_pac_career',
    'corporate_earmark_transmitted': 'corporate_earmark_transmitted_career',
}
DIRECT = {Source.AIPAC: 'aipac_pac_direct', Source.CORPORATE: 'corporate_pac'}
EARMARK = {Source.AIPAC: 'aipac_earmark_transmitted',
           Source.CORPORATE: 'corporate_earmark_transmitted'}


def cycles_with_money(person, ledger):
    for cycle in CYCLES:
        for candidate_id in candidate_ids(person):
            amounts = {column: ledger.amount(candidate_id, cycle, column)
                       for column in CAREER_COLUMNS}
            if any(amounts.values()):
                yield cycle, candidate_id, amounts


def career_of(person, ledger):
    return {column: ledger.total(candidate_ids(person), CYCLES, column)
            for column in CAREER_COLUMNS}


def as_text(amounts):
    return {column: str(amount) for column, amount in amounts.items()}


def read_individual_contributions(cycle, roster, ledger, candidates_seen):
    summaries = candidate_summaries(BULK, cycle)
    matched = 0
    latest_coverage_end = ''
    for summary in summaries:
        if summary.candidate_id in roster:
            matched += 1
            candidates_seen.add(summary.candidate_id)
            ledger.add(summary.candidate_id, cycle, 'individual',
                       summary.amount('individual_contributions'))
        if cycle == CURRENT_CYCLE:
            latest_coverage_end = max(latest_coverage_end, summary.coverage_end)
    return {'cycle': cycle, 'weball_rows': summaries.rows_read, 'weball_matched': matched,
            'weball_bad_fields': summaries.malformed_rows,
            f'weball_{CURRENT_CYCLE}_max_cvg_end': latest_coverage_end}


def read_committee_registry(cycle):
    registry = committees(BULK, cycle)
    registered, corporate_pacs, blank_organization = set(), set(), 0
    for committee in registry:
        registered.add(committee.committee_id)
        blank_organization += not committee.organization_type
        if committee.is_corporate_pac:
            corporate_pacs.add(committee.committee_id)
    counts = {'cm_rows': registry.rows_read, 'cm_bad_fields': registry.malformed_rows,
              'cm_blank_org_tp': blank_organization, 'corp_pacs': len(corporate_pacs)}
    return registered, corporate_pacs, counts


def read_committee_contributions(cycle, roster, ledger, candidates_seen):
    registered, corporate_pacs, registry_counts = read_committee_registry(cycle)
    filed = committee_contributions(BULK, cycle)
    reported_once = ReportedOnce()
    matched = 0
    negative, voided_earmarks, unregistered = Tally(), Tally(), Tally()
    unregistered_committees = set()
    before_dedup = {source: Tally() for source in Source}

    for contribution in filed:
        if not contribution.is_to_candidate or contribution.candidate_id not in roster:
            continue
        matched += 1
        candidates_seen.add(contribution.candidate_id)
        if contribution.committee_id not in registered:
            unregistered.add(ZERO)
            unregistered_committees.add(contribution.committee_id)
        if contribution.amount.is_negative:
            negative.add(contribution.amount)
        if is_voided_earmark(contribution):
            voided_earmarks.add(contribution.amount)
            continue
        source = tracked_source(contribution, AIPAC_PAC, corporate_pacs)
        if source is None:
            continue
        before_dedup[source].add(contribution.amount)
        reported_once.add(contribution)

    kept = {source: Tally() for source in Source}
    earmarked = {source: Tally() for source in Source}
    for contribution in reported_once:
        source = tracked_source(contribution, AIPAC_PAC, corporate_pacs)
        ledger.add(contribution.candidate_id, cycle, DIRECT[source], contribution.amount)
        kept[source].add(contribution.amount)
        if contribution.is_earmark:
            ledger.add(contribution.candidate_id, cycle, EARMARK[source], contribution.amount)
            earmarked[source].add(contribution.amount)

    counts = {
        **registry_counts,
        'pas2_rows': filed.rows_read, 'pas2_bad_fields': filed.malformed_rows,
        'pas2_matched_roster': matched,
        'pas2_neg_rows': negative.rows, 'pas2_neg_cents': negative.amount.cents,
        'dedup_dropped_rows': reported_once.dropped.rows,
        'dedup_dropped_cents': reported_once.dropped.amount.cents,
        'void_earmark_rows': voided_earmarks.rows,
        'void_earmark_cents': voided_earmarks.amount.cents,
        'earmark_aipac_cents': earmarked[Source.AIPAC].amount.cents,
        'earmark_corp_cents': earmarked[Source.CORPORATE].amount.cents,
        'naive_aipac_cents': before_dedup[Source.AIPAC].amount.cents,
        'naive_corp_cents': before_dedup[Source.CORPORATE].amount.cents,
        'aipac_rows_kept': kept[Source.AIPAC].rows, 'aipac_cents': kept[Source.AIPAC].amount.cents,
        'corp_rows_kept': kept[Source.CORPORATE].rows,
        'corp_cents': kept[Source.CORPORATE].amount.cents,
    }
    missing_from_registry = {'cm_missing_committees': len(unregistered_committees),
                             'cm_missing_rows': unregistered.rows,
                             'cm_missing_ids': sorted(unregistered_committees)[:20]}
    return counts, missing_from_registry


def notes_for(person, career, roster, candidates_seen):
    ids = candidate_ids(person)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    elif not candidates_seen.intersection(ids):
        notes.append('no FEC activity found')
    elif not (career['individual'] or career['aipac_pac_direct'] or career['corporate_pac']):
        notes.append('FEC activity found; all totals zero')
    shared_with = roster.others_sharing_an_id_with(person)
    if shared_with:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(shared_with))
    if career['aipac_pac_direct'].is_negative:
        notes.append('net-negative AIPAC total (voids exceed direct contributions)')
    return ' | '.join(notes)


def career_row(person, roster, ledger, candidates_seen):
    career = career_of(person, ledger)
    totals = {CAREER_COLUMNS[column]: text for column, text in as_text(career).items()}
    return {'person_key': person['person_key'], 'full_name': person['full_name'],
            'fec_candidate_ids': ';'.join(candidate_ids(person)),
            **totals,
            'data_notes': notes_for(person, career, roster, candidates_seen)}


def per_cycle_record(person, ledger):
    entries = [{'cycle': cycle, 'candidate_id': candidate_id, **as_text(amounts)}
               for cycle, candidate_id, amounts in cycles_with_money(person, ledger)]
    return {'person_key': person['person_key'], 'full_name': person['full_name'],
            'per_cycle': entries}


def write_career_csv(rows):
    with open(INTERMEDIATE / 'money_pas2_weball.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(name, content):
    with open(INTERMEDIATE / name, 'w') as f:
        json.dump(content, f, indent=1)


def print_summary(rows, diagnostics):
    def column_total(column):
        return Money.total(Money.parse(row[column]) for row in rows)

    def rows_noted(text):
        return sum(1 for row in rows if text in row['data_notes'])

    def diagnostic_total(key):
        return sum(cycle[key] for cycle in diagnostics)

    print('persons:', len(rows))
    print('no FEC IDs:', rows_noted('no FEC candidate IDs'))
    print('no FEC activity found:', rows_noted('no FEC activity found'))
    print('activity found, all totals zero:', rows_noted('all totals zero'))
    for column in CAREER_COLUMNS.values():
        print(f'TOTAL {column} $:', column_total(column))
    print('duplicate reports dropped:', diagnostic_total('dedup_dropped_rows'), 'rows')
    print('voided earmarks excluded:', diagnostic_total('void_earmark_rows'), 'rows')


def main():
    with open(INTERMEDIATE / 'roster.json') as f:
        roster = Roster(json.load(f))
    ledger = Ledger()
    candidates_seen = set()

    diagnostics = [read_individual_contributions(cycle, roster, ledger, candidates_seen)
                   for cycle in CYCLES]
    missing_from_registry = {}
    for cycle_diagnostics in diagnostics:
        cycle = cycle_diagnostics['cycle']
        counts, missing_from_registry[cycle] = read_committee_contributions(
            cycle, roster, ledger, candidates_seen)
        cycle_diagnostics.update(counts)

    rows = [career_row(person, roster, ledger, candidates_seen) for person in roster.people]
    write_career_csv(rows)
    write_json('money_per_cycle.json',
               {person['person_key']: per_cycle_record(person, ledger)
                for person in roster.people})
    write_json('pull-diagnostics.json',
               {'per_cycle': diagnostics, 'cm_missing': missing_from_registry})
    print_summary(rows, diagnostics)


if __name__ == '__main__':
    main()
