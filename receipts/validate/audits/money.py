"""Career money families: self-funding, other committees, all-IE, roster totals, opposition."""

from receipts.common.settings import settings
from receipts.store.read import connect
from receipts.validate.audits.published import METHODOLOGY_TOTAL_COLS, opposition_credit


def self_funding(audit, dataset):
    """(j) self-funding spot cases; debts owed to is null. The per-cycle sums
    are dbt tests on the gold tables (dbt/tests/*_career_is_its_cycles.sql).
    """
    named_sf = {
        'anthonyconstantinonyhouse': 'Constantino',
        'S001217': 'Rick Scott',
        'R000618': 'Pete Ricketts',
        'T000488': 'Shri Thanedar',
        'M001232': 'April McClain Delaney',
        'J000305': 'Sara Jacobs',
        'C001123': 'Gilbert Ray Cisneros, Jr.',
        'S001229': 'Jefferson Shreve',
    }
    for pk, name in named_sf.items():
        audit.pin(
            f'{name} self_funding_career',
            f'spot.self_funding_career.{pk}',
            dataset.by_key[pk]['self_funding_career'],
        )
    const = dataset.by_key['anthonyconstantinonyhouse']
    for col in (
        'total_receipts_career',
        'total_disbursements_career',
        'cash_on_hand_2026',
        'total_receipts_2026',
    ):
        audit.pin(f'Constantino {col}', f'spot.constantino.{col}', const[col])
    audit.check(
        'debts_owed_to_career is null for every numeric row',
        all(r['debts_owed_to_career'] is None for r in dataset.with_known_money),
    )
    arm = dataset.by_key.get('A000383')
    audit.check(
        'Armstrong new money columns are unknown, top committees null',
        arm is not None
        and arm['self_funding_career'] == 'unknown'
        and arm['other_committees_total_career'] == 'unknown'
        and arm['all_ie_total_career'] == 'unknown'
        and arm['all_ie_top_committees'] is None,
    )


def other_committees(audit, dataset):
    """(k) other committees: Lamb's 2026 pas2 total and its residual against weball."""
    oc_buckets = [
        'party_committees',
        'leadership_pacs',
        'labor_pacs',
        'trade_pacs',
        'membership_pacs',
        'cooperative_pacs',
        'other_unclassified',
    ]
    lamb = dataset.by_key['marklambazhouse']
    lamb_pc26 = [
        e for e in lamb['other_committees_per_cycle'] if e['cycle'] == settings().cycles.current
    ]
    lamb_total = round(sum(sum(e[b] for b in oc_buckets) for e in lamb_pc26), 2)
    audit.check(
        'Lamb 2026 other-committee column equals its per-cycle pas2 sum',
        lamb_total == lamb['other_committees_total_2026'],
        f'got {lamb_total}',
    )
    audit.pin(
        'Lamb 2026 other-committee pas2-derived total',
        'spot.lamb.other_committees_total_2026',
        lamb_total,
    )
    with connect() as db:
        lamb_weball, *_ = db.execute(
            'SELECT other_committee_contributions_cents FROM candidate_summaries '
            "WHERE candidate_id = 'H6AZ05265' AND cycle = ?",
            [settings().cycles.current],
        ).fetchone()
    lamb_residual = round(lamb_weball / 100 - lamb_total, 2)
    audit.pin(
        'Lamb 2026 weball-minus-pas2 residual', 'spot.lamb.weball_minus_pas2_2026', lamb_residual
    )
    audit.check(
        'Lamb data_notes states the current pas2 total and residual (or no note at zero)',
        ('PENDING RECONCILIATION' not in lamb['data_notes'])
        if lamb_residual == 0
        else (
            f'${lamb_total:,.2f} by pas2' in lamb['data_notes']
            and f'${lamb_residual:,.2f} residual' in lamb['data_notes']
        ),
        lamb['data_notes'][-260:],
    )


def all_ie(audit, dataset):
    """(l) all-IE: roster cycle totals; the blank-direction gap; top committees.
    The UDP 2024 reconciliation is enforced by the all-IE step itself.
    """
    with connect() as db:
        roster_ie_totals = db.execute(
            'SELECT cycle, sum(all_ie_total) FROM gold.all_ie_per_candidate_cycle '
            'WHERE is_roster GROUP BY cycle ORDER BY cycle'
        ).fetchall()
    for cycle, cents in roster_ie_totals:
        audit.pin(f'all-IE roster total {cycle}', f'all_ie_cycle_totals.{cycle}', cents / 100)
    nodir = round(
        sum(
            r['all_ie_total_career'] - r['all_ie_support_career'] - r['all_ie_oppose_career']
            for r in dataset.with_known_money
        ),
        2,
    )
    audit.pin(
        'all-IE row-sum gap (the blank-direction rows)', 'spot.all_ie_blank_direction_gap', nodir
    )
    mism = 0
    for r in dataset.with_known_money:
        top = r['all_ie_top_committees']
        if top is None:
            mism += 1
            continue
        totals = [c['total'] for c in top]
        if totals != sorted(totals, reverse=True) or len(top) > 5:
            mism += 1
        for c in top:
            if round(c['support'] + c['oppose'], 2) != c['total']:
                mism += 1
    audit.check(
        'all-IE top-committee lists sorted, split correctly, max 5', mism == 0, f'{mism} mismatches'
    )
    elsayed = next(r for r in dataset.with_known_money if 'El-Sayed' in r['full_name'])
    for col in ('all_ie_support_career', 'all_ie_oppose_career'):
        audit.pin(f'El-Sayed {col}', f'spot.elsayed.{col}', elsayed[col])


def roster_totals(audit, dataset):
    """(b) roster totals match methodology.md figures
    (None stocks — cash on hand / debts owed by for people with no
    weball rows at all — are skipped, exactly as the config totals
    were computed from the staged CSVs.)
    """
    for col in METHODOLOGY_TOTAL_COLS:
        total = round(sum(r[col] for r in dataset.with_known_money if r[col] is not None), 2)
        audit.pin(f'roster total {col}', f'methodology_totals.{col}', total)


def opposition(audit, dataset):
    """(f) opposition career columns"""
    career_credit = opposition_credit()
    mism = 0
    for r in dataset.with_known_money:
        credit = career_credit.get(r['person_key'], 0.0)
        if r['udp_ie_opposing_opponents_career'] != credit:
            mism += 1
        if r['udp_ie_total_benefit_career'] != round(r['udp_ie_support_career'] + credit, 2):
            mism += 1
    audit.check(
        'opposition career columns recompute from gold.opposition_credits',
        mism == 0,
        f'{mism} mismatches',
    )
    arm = dataset.by_key.get('A000383')
    audit.check(
        'Armstrong opposition columns are null (money unknown)',
        arm is not None
        and arm['udp_ie_opposing_opponents_career'] is None
        and arm['udp_ie_total_benefit_career'] is None,
    )
