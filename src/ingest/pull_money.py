#!/usr/bin/env python3
"""Career money per roster candidate, from the FEC bulk files.

Individual contributions come from weball; AIPAC PAC and corporate PAC
contributions from pas2, classified with the committee master (cm).
Rules and evidence: methodology.md §4, research/pull-log-a.md.
"""
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import load_config
from src.domain.committee_money import (ReportedOnce, Source, Tally, is_voided_earmark,
                                        tracked_source)
from src.domain.money import ZERO, Money
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


@dataclass
class CycleMoney:
    individual: Money = ZERO
    aipac_pac_direct: Money = ZERO
    aipac_earmark_transmitted: Money = ZERO
    corporate_pac: Money = ZERO
    corporate_earmark_transmitted: Money = ZERO

    def add(self, column, amount):
        setattr(self, column, getattr(self, column) + amount)

    def __bool__(self):
        return any(getattr(self, column) for column in CAREER_COLUMNS)

    def as_text(self):
        return {column: str(getattr(self, column)) for column in CAREER_COLUMNS}


class Roster:
    def __init__(self, people):
        self.people = people
        self.people_by_candidate = defaultdict(list)
        for person in people:
            for candidate_id in candidate_ids(person):
                self.people_by_candidate[candidate_id].append(person['person_key'])

    def __contains__(self, candidate_id):
        return candidate_id in self.people_by_candidate

    def others_sharing_an_id_with(self, person):
        return sorted({key for candidate_id in candidate_ids(person)
                       for key in self.people_by_candidate[candidate_id]
                       if key != person['person_key']})


def candidate_ids(person):
    return person.get('fec_candidate_ids') or []


class Ledger:
    """Money per candidate ID per cycle, and which IDs appear in the files at all."""

    def __init__(self):
        self._money = defaultdict(CycleMoney)
        self.candidates_seen = set()

    def add(self, candidate_id, cycle, column, amount):
        self._money[candidate_id, cycle].add(column, amount)

    def cycles_of(self, person):
        return [(cycle, candidate_id, self._money[candidate_id, cycle])
                for cycle in CYCLES for candidate_id in candidate_ids(person)
                if (candidate_id, cycle) in self._money and self._money[candidate_id, cycle]]

    def career_of(self, person):
        career = CycleMoney()
        for _, _, money in self.cycles_of(person):
            for column in CAREER_COLUMNS:
                career.add(column, getattr(money, column))
        return career


def read_individual_contributions(cycle, roster, ledger):
    summaries = candidate_summaries(BULK, cycle)
    matched = 0
    latest_coverage_end = ''
    for summary in summaries:
        if summary.candidate_id in roster:
            matched += 1
            ledger.candidates_seen.add(summary.candidate_id)
            ledger.add(summary.candidate_id, cycle, 'individual',
                       summary.individual_contributions)
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


def read_committee_contributions(cycle, roster, ledger):
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
        ledger.candidates_seen.add(contribution.candidate_id)
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


def notes_for(person, career, roster, ledger):
    ids = candidate_ids(person)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    elif not ledger.candidates_seen.intersection(ids):
        notes.append('no FEC activity found')
    elif not (career.individual or career.aipac_pac_direct or career.corporate_pac):
        notes.append('FEC activity found; all totals zero')
    shared_with = roster.others_sharing_an_id_with(person)
    if shared_with:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(shared_with))
    if career.aipac_pac_direct.is_negative:
        notes.append('net-negative AIPAC total (voids exceed direct contributions)')
    return ' | '.join(notes)


def career_row(person, roster, ledger):
    career = ledger.career_of(person)
    totals = {CAREER_COLUMNS[column]: text for column, text in career.as_text().items()}
    return {'person_key': person['person_key'], 'full_name': person['full_name'],
            'fec_candidate_ids': ';'.join(candidate_ids(person)),
            **totals,
            'data_notes': notes_for(person, career, roster, ledger)}


def per_cycle_record(person, ledger):
    entries = [{'cycle': cycle, 'candidate_id': candidate_id, **money.as_text()}
               for cycle, candidate_id, money in ledger.cycles_of(person)]
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

    diagnostics = [read_individual_contributions(cycle, roster, ledger) for cycle in CYCLES]
    missing_from_registry = {}
    for cycle_diagnostics in diagnostics:
        cycle = cycle_diagnostics['cycle']
        counts, missing_from_registry[cycle] = read_committee_contributions(
            cycle, roster, ledger)
        cycle_diagnostics.update(counts)

    rows = [career_row(person, roster, ledger) for person in roster.people]
    write_career_csv(rows)
    write_json('money_per_cycle.json',
               {person['person_key']: per_cycle_record(person, ledger)
                for person in roster.people})
    write_json('pull-diagnostics.json',
               {'per_cycle': diagnostics, 'cm_missing': missing_from_registry})
    print_summary(rows, diagnostics)


if __name__ == '__main__':
    main()
