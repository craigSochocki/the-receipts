from receipts.transform.assemble import (
    ACCEPTED,
    ALL_IE,
    ARMSTRONG_NOTE,
    OTHER_COMMITTEES,
    PRO_ISRAEL,
    RANKS,
    SELF_FUNDING,
    record,
    tracked_people,
)


def roster_row(key, ids, congress_119=None, congress_120=None):
    row = {'person_key': key, 'full_name': key.title(), 'state': 'MI', 'senate_class': None,
           'fec_candidate_ids': ids}  # fmt: skip
    for congress, served in (('119', congress_119), ('120', congress_120)):
        row[f'in_{congress}th'] = 'yes' if served else 'no'
        for field in ('chamber', 'district', 'party', 'leadership'):
            row[f'{field}_{congress}'] = (served or {}).get(field, '')
    return row


SEAT = {'chamber': 'House', 'district': 8, 'party': 'Democrat', 'leadership': ''}


def test_a_second_roster_entry_for_the_same_person_supplies_the_missing_congress():
    roster = [
        roster_row('kept', ['H1'], congress_119=SEAT),
        roster_row('twin', ['H1'], congress_120=SEAT),
        roster_row('other', ['H2'], congress_120=SEAT),
    ]
    people = tracked_people(['kept', 'other'], roster)
    kept = people[0]
    assert (kept['in_119th'], kept['in_120th']) == ('yes', 'yes')
    assert (kept['chamber_120'], kept['district_120']) == ('House', 8)
    assert [p['person_key'] for p in people] == ['kept', 'other']


def gold(key='p', **notes):
    def money_row(columns):
        return {'person_key': key, **dict.fromkeys(columns, 123_45)}

    return {
        'accepted': {key: {**money_row(ACCEPTED), 'data_notes': notes.get('accepted', '')}},
        'udp': {key: {'udp_ie_support_career': 0, 'data_notes': notes.get('udp', '')}},
        'self_funding': {key: money_row(SELF_FUNDING.values())},
        'committees': {
            key: {
                **money_row(OTHER_COMMITTEES),
                'data_notes': notes.get('committees', ''),
                'reconciliation_note': notes.get('reconciliation', ''),
            }
        },
        'all_ie': {key: money_row(ALL_IE)},
        'pro_israel': {key: money_row(PRO_ISRAEL)},
        'pro_israel_cycles': {
            key: [{'cycle': 2024, 'pro_israel_pac': 5_00, 'pro_israel_ie_support': 0}]
        },
        'money': {
            key: {
                'udp_opposing_opponents': 0,
                'udp_total_benefit': 0,
                'total_accepted': 370_35,
                'dirty': 246_90,
            }
        },  # fmt: skip
        'ranks': {key: dict.fromkeys(RANKS, 7)},
        'accepted_cycles': {
            key: [
                {
                    'cycle': 2024,
                    'candidate_id': 'H1',
                    'individual': 10_00,
                    'aipac_pac_direct': 0,
                    'aipac_earmark_transmitted': 0,
                    'corporate_pac': 5_00,
                    'corporate_earmark_transmitted': 0,
                }
            ]
        },  # fmt: skip
        'udp_cycles': {key: []},
        'self_funding_cycles': {key: []},
        'committee_cycles': {key: []},
        'top_committees': {key: []},
        'all_ie_by_candidate': [],
    }


def test_money_arrives_in_cents_and_leaves_in_dollars():
    rec = record({'person_key': 'p', 'fec_candidate_ids': ['H1']}, gold(), dedup_notes={})
    assert rec['individual_contribution_total_career'] == 123.45
    assert rec['total_accepted_career'] == 370.35
    assert rec['debts_owed_to_career'] is None
    assert rec['per_cycle'][0]['corporate_pac'] == 5.0
    assert rec['rank_total_accepted'] == 7


def test_a_person_without_an_fec_id_has_unknown_money_not_zero():
    rec = record({'person_key': 'p', 'fec_candidate_ids': []}, gold(), dedup_notes={})
    assert rec['individual_contribution_total_career'] == 'unknown'
    assert rec['total_accepted_career'] is None
    assert rec['all_ie_top_committees'] is None
    assert rec['data_notes'] == ARMSTRONG_NOTE


def test_data_notes_join_each_step_in_order():
    notes = gold(
        accepted='FEC activity found',
        udp='No UDP support',
        committees='no notes | other_unclassified includes WinRed conduit net 5.00',
        reconciliation='PENDING RECONCILIATION',
    )
    rec = record(
        {'person_key': 'p', 'fec_candidate_ids': ['H1']}, notes, dedup_notes={'p': 'DEDUP.'}
    )
    assert rec['data_notes'] == (
        'FEC activity found | No UDP support DEDUP. | PENDING RECONCILIATION'
        ' | other_unclassified includes WinRed conduit net 5.00'
    )
