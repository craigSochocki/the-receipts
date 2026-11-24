"""The dataset's rows before the cycle columns, from the store's gold tables and marts."""

from collections import defaultdict

from receipts.common.files import read_json
from receipts.common.settings import load_double_count_records, settings
from receipts.domain.committee_classes import OTHER_COMMITTEE_CLASSES
from receipts.domain.weball_double_counts import correction_notes
from receipts.store.read import connect

BUCKETS = [c.value for c in OTHER_COMMITTEE_CLASSES]
ARMSTRONG_NOTE = (
    'No FEC candidate IDs in roster (appointed senator, never ran for the seat); '
    'money totals unknown, not zero. Not searchable in UDP IE data.'
)
FOLDED_ROSTER_NOTES = {
    'M001237': (
        'Roster fix: Kristen McDonald Rivet appeared twice in the source roster '
        '(person_keys M001237 and kristen-mcdonaldrivetmihouse, same FEC ID H4MI08218, '
        'identical money totals); collapsed to a single row. Money totals counted once, '
        'not twice. She served in the 119th (MI-08) and was re-elected to the 120th (MI-08).'
    ),
}
ROSTER_FIELDS = [
    'person_key', 'full_name', 'chamber_119', 'chamber_120', 'state',
    'district_119', 'district_120', 'party_119', 'party_120',
    'leadership_119', 'leadership_120', 'in_119th', 'in_120th',
    'fec_candidate_ids', 'senate_class',
]  # fmt: skip
SERVED_FIELDS = ('chamber', 'district', 'party', 'leadership')
ACCEPTED = [
    'individual_contribution_total_career', 'aipac_pac_direct_career',
    'aipac_earmark_transmitted_career', 'corporate_pac_career',
    'corporate_earmark_transmitted_career',
]  # fmt: skip
SELF_FUNDING = {
    'cand_contrib_career': 'candidate_contributions_career',
    'cand_loans_career': 'candidate_loans_career',
    'self_funding_career': 'self_funding_career',
    'loan_repayments_career': 'loan_repayments_career',
    'total_receipts_career': 'total_receipts_career',
    'total_disbursements_career': 'total_disbursements_career',
    'transfers_from_auth_career': 'transfers_from_auth_career',
    'transfers_to_auth_career': 'transfers_to_auth_career',
    'debts_owed_by_career': 'debts_owed_by_career',
    'cash_on_hand_career': 'cash_on_hand_career',
}
OTHER_COMMITTEES = (
    [f'{b}_career' for b in BUCKETS]
    + ['other_committees_total_career']
    + [f'{b}_earmark_transmitted_career' for b in BUCKETS]
)
ALL_IE = ['all_ie_support_career', 'all_ie_oppose_career', 'all_ie_total_career']
MONEY = (
    ACCEPTED + ['udp_ie_support_career'] + list(SELF_FUNDING) + ['debts_owed_to_career']
    + OTHER_COMMITTEES + ALL_IE
)  # fmt: skip
RANKS = [
    'rank_total_accepted', 'rank_individual', 'rank_corporate_pac', 'rank_aipac_direct',
    'rank_udp_support', 'rank_udp_opposing_opponents', 'rank_udp_total_benefit',
    'rank_self_funding', 'rank_all_ie_support', 'rank_all_ie_oppose', 'rank_all_ie_total',
    'rank_other_committees_total',
]  # fmt: skip
SELF_FUNDING_ENTRY = [
    'candidate_contributions', 'candidate_loans', 'loan_repayments', 'debts_owed_by',
    'debts_owed_to', 'total_receipts', 'total_disbursements', 'cash_on_hand',
    'transfers_from_auth', 'transfers_to_auth',
]  # fmt: skip


def dollars(cents):
    return None if cents is None else cents / 100


def rows(db, sql):
    cursor = db.execute(sql)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def keyed(db, table):
    return {r['person_key']: r for r in rows(db, f'SELECT * FROM {table}')}


def grouped(db, table):
    found = defaultdict(list)
    for r in rows(db, f'SELECT * FROM {table} ORDER BY person_key, entry'):
        found[r['person_key']].append(r)
    return found


def accepted_entries(entries):
    names = ['individual', 'aipac_pac_direct', 'aipac_earmark_transmitted', 'corporate_pac',
             'corporate_earmark_transmitted']  # fmt: skip
    return [{'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
             **{n: dollars(e[n]) for n in names}} for e in entries]  # fmt: skip


def udp_entries(entries):
    found = []
    for e in entries:
        entry = {'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
                 'udp_ie_support': dollars(e['udp_ie_support'])}  # fmt: skip
        if e['attribution'] is not None:
            entry['attribution'] = e['attribution']
        found.append(entry)
    return found


def self_funding_entries(entries):
    return [
        {'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
         **{n: dollars(e[n]) for n in SELF_FUNDING_ENTRY}, 'debts_owed_to': None,
         'coverage_end_date': e['coverage_end_date']}
        for e in entries
    ]  # fmt: skip


def other_committee_entries(entries):
    return [
        {'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
         **{b: dollars(e[b]) for b in BUCKETS},
         'earmark_transmitted': {b: dollars(e[f'earmark_{b}']) for b in BUCKETS
                                 if e[f'earmark_{b}'] is not None},
         'winred_included': dollars(e['winred_included'])}
        for e in entries
    ]  # fmt: skip


def all_ie_entries(by_candidate, ids):
    names = ['all_ie_support', 'all_ie_oppose', 'all_ie_total', 'no_direction_amount']
    found = [e for e in by_candidate if e['candidate_id'] in ids]
    return [{'cycle': e['cycle'], 'candidate_id': e['candidate_id'],
             **{n: dollars(e[n]) for n in names}}
            for e in sorted(found, key=lambda e: (e['cycle'], e['candidate_id']))]  # fmt: skip


def top_committees(entries):
    return [{'committee_id': e['committee_id'], 'committee_name': e['committee_name'],
             'support': dollars(e['support']), 'oppose': dollars(e['oppose']),
             'total': dollars(e['total']), 'rows': e['rows']} for e in entries]  # fmt: skip


def roster_fields(row, folded):
    """The roster fields; a folded second entry supplies a Congress the kept row lacks."""
    row = dict(row)
    for twin in folded:
        for congress in ('119', '120'):
            if row.get(f'in_{congress}th') != 'yes' and twin.get(f'in_{congress}th') == 'yes':
                for field in (*SERVED_FIELDS, 'in'):
                    name = f'in_{congress}th' if field == 'in' else f'{field}_{congress}'
                    row[name] = twin[name]
    return {f: row[f] for f in ROSTER_FIELDS} | {
        'fec_candidate_ids': list(row['fec_candidate_ids'] or [])
    }


def data_notes(key, gold, dedup_notes):
    accepted_note = FOLDED_ROSTER_NOTES.get(key, gold['accepted'][key]['data_notes'])
    note = ' | '.join(n for n in (accepted_note, gold['udp'][key]['data_notes']) if n)
    if key in dedup_notes:
        note = f'{note} {dedup_notes[key]}' if note else dedup_notes[key]
    committees = gold['committees'][key]
    winred = [s for s in (committees['data_notes'] or '').split(' | ') if 'WinRed' in s]
    for segment in [committees['reconciliation_note'], *winred]:
        if segment:
            note = f'{note} | {segment}' if note else segment
    return note


def money_fields(key, gold):
    sf, ie, money = gold['self_funding'][key], gold['all_ie'][key], gold['money'][key]
    return {
        **{c: dollars(gold['accepted'][key][c]) for c in ACCEPTED},
        'udp_ie_support_career': dollars(gold['udp'][key]['udp_ie_support_career']),
        **{c: dollars(sf[source]) for c, source in SELF_FUNDING.items()},
        'debts_owed_to_career': None,
        **{c: dollars(gold['committees'][key][c]) for c in OTHER_COMMITTEES},
        **{c: dollars(ie[c]) for c in ALL_IE},
        'udp_ie_opposing_opponents_career': dollars(money['udp_opposing_opponents']),
        'udp_ie_total_benefit_career': dollars(money['udp_total_benefit']),
        'total_accepted_career': dollars(money['total_accepted']),
        'dirty_career': dollars(money['dirty']),
    }


def unknown_money():
    return {
        **dict.fromkeys(MONEY, 'unknown'),
        **dict.fromkeys(['udp_ie_opposing_opponents_career', 'udp_ie_total_benefit_career',
                         'total_accepted_career', 'dirty_career']),
    }  # fmt: skip


def record(person, gold, dedup_notes):
    key, ids = person['person_key'], person['fec_candidate_ids']
    rec = {
        **person,
        'per_cycle': accepted_entries(gold['accepted_cycles'][key]),
        'udp_per_cycle': udp_entries(gold['udp_cycles'][key]),
        'self_funding_per_cycle': self_funding_entries(gold['self_funding_cycles'][key]),
        'other_committees_per_cycle': other_committee_entries(gold['committee_cycles'][key]),
        'all_ie_per_cycle': all_ie_entries(gold['all_ie_by_candidate'], ids),
        'all_ie_top_committees': top_committees(gold['top_committees'][key]) if ids else None,
        'data_as_of': settings().data_as_of,
        **{r: gold['ranks'][key][r] for r in RANKS},
    }
    if not ids:
        return {**rec, **unknown_money(), 'data_notes': ARMSTRONG_NOTE}
    return {**rec, **money_fields(key, gold), 'data_notes': data_notes(key, gold, dedup_notes)}


def read_gold():
    with connect() as db:
        return {
            'tracked': [r['person_key'] for r in rows(db, 'SELECT person_key FROM tracked_people ORDER BY roster_position')],
            'accepted': keyed(db, 'gold.accepted_money_people'),
            'udp': keyed(db, 'gold.udp_people'),
            'self_funding': keyed(db, 'gold.self_funding_people'),
            'committees': keyed(db, 'gold.other_committees_people'),
            'all_ie': keyed(db, 'gold.all_ie_people'),
            'money': keyed(db, 'person_money'),
            'ranks': keyed(db, 'person_ranks'),
            'accepted_cycles': grouped(db, 'gold.accepted_money_per_cycle'),
            'udp_cycles': grouped(db, 'gold.udp_per_cycle'),
            'self_funding_cycles': grouped(db, 'gold.self_funding_per_cycle'),
            'committee_cycles': grouped(db, 'gold.other_committees_per_cycle'),
            'top_committees': grouped(db, 'gold.all_ie_top_committees'),
            'all_ie_by_candidate': rows(db, 'SELECT * FROM gold.all_ie_per_candidate_cycle'),
        }  # fmt: skip


def tracked_people(tracked, roster_rows):
    """Roster fields for each tracked person, folding in a second entry for the same person."""
    roster = {r['person_key']: r for r in roster_rows}
    kept = set(tracked)
    folded = defaultdict(list)
    for key, row in roster.items():
        if key in kept:
            continue
        for other in tracked:
            if set(row.get('fec_candidate_ids') or []) & set(
                roster[other].get('fec_candidate_ids') or []
            ):
                folded[other].append(row)
    return [roster_fields(roster[key], folded[key]) for key in tracked]


def base_records(json_keys):
    gold = read_gold()
    dedup_notes = correction_notes(load_double_count_records())
    people = tracked_people(gold['tracked'], read_json(settings().paths.roster_intermediate))
    return [{k: r[k] for k in json_keys} for r in (record(p, gold, dedup_notes) for p in people)]
