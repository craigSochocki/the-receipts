"""The published dataset as the audits read it, and helpers the audit groups share."""

from receipts.common.files import read_json
from receipts.common.settings import settings
from receipts.fec.weball import candidate_summaries
from receipts.store.read import connect

METHODOLOGY_TOTAL_COLS = [
    'individual_contribution_total_career',
    'aipac_pac_direct_career',
    'aipac_earmark_transmitted_career',
    'corporate_pac_career',
    'corporate_earmark_transmitted_career',
    'udp_ie_support_career',
    'udp_ie_opposing_opponents_career',
    'udp_ie_total_benefit_career',
    'dirty_career',
    'cand_contrib_career',
    'cand_loans_career',
    'self_funding_career',
    'loan_repayments_career',
    'total_receipts_career',
    'total_disbursements_career',
    'transfers_from_auth_career',
    'transfers_to_auth_career',
    'cash_on_hand_career',
    'debts_owed_by_career',
    'party_committees_career',
    'leadership_pacs_career',
    'labor_pacs_career',
    'trade_pacs_career',
    'membership_pacs_career',
    'cooperative_pacs_career',
    'other_unclassified_career',
    'other_committees_total_career',
    'party_committees_earmark_transmitted_career',
    'leadership_pacs_earmark_transmitted_career',
    'labor_pacs_earmark_transmitted_career',
    'trade_pacs_earmark_transmitted_career',
    'membership_pacs_earmark_transmitted_career',
    'cooperative_pacs_earmark_transmitted_career',
    'other_unclassified_earmark_transmitted_career',
    'all_ie_support_career',
    'all_ie_oppose_career',
    'all_ie_total_career',
]


class Published:
    """The published dataset as the audits read it: the JSON records and the CSV beside them."""

    def __init__(self, json_path, csv_path):
        self.records = read_json(json_path)
        self.by_key = {r['person_key']: r for r in self.records}
        self.with_known_money = [
            r for r in self.records if r['individual_contribution_total_career'] != 'unknown'
        ]
        self.csv_path = csv_path


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def competition_ranks(records, col):
    values = [r[col] for r in records if is_num(r[col])]
    return {
        r['person_key']: (None if not is_num(r[col]) else 1 + sum(1 for x in values if x > r[col]))
        for r in records
    }


def cycle_sum(entries, field):
    vals = [e[field] for e in entries if e['cycle'] == settings().cycles.current]
    return round(sum(vals), 2) if vals else 0


def opposition_credit(cycle=None):
    """Dollars of opposition credit per roster person, summed over phases (and cycles)."""
    with connect() as db:
        credits = db.execute(
            'SELECT credited_to, sum(credit) FROM gold.opposition_credits '
            "WHERE credited_to NOT LIKE '__nonroster__%' AND (? IS NULL OR cycle = ?) "
            'GROUP BY credited_to',
            [cycle, cycle],
        ).fetchall()
    return {person_key: cents / 100 for person_key, cents in credits}


def load_weball_2026_races():
    """Current-cycle races from weball, keyed by the filing's own race (MP files under 01)."""
    race_map = {}
    by_cid = {}
    for row in candidate_summaries(settings().paths.bulk, settings().cycles.current):
        try:
            receipts = float(row.total_receipts or 0)
        except ValueError:
            receipts = 0.0
        race = (row.candidate_id[0], row.office_state, row.office_district)
        race_map.setdefault(race, []).append((row.candidate_id, receipts))
        by_cid[row.candidate_id] = race
    return race_map, by_cid
