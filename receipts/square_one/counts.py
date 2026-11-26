"""Flag and clean counts under both JFC variants, from the square-one derivation.

The cycle records are built from the derivation's own figures (weball,
committee money, IE, corrected AIPAC) and judged by the repo's own rules:
compute_2026.cycle_record and headline for the per-cycle verdicts and
the term headline, domain.term.term_record for the term sums, and the
clean_2026 tier functions. Nothing about the verdict rules is
re-implemented here — only the inputs are re-derived.

Variants: 'baseline' uses the pas2 AIPAC figures (the check that the
re-derivation reproduces the committed counts); 'A' substitutes the API
AIPAC direct plus JFC shares for cycles 2022–2026; 'B' substitutes the
API direct only. For the substituted cycles the API figure replaces pas2
wholesale (zero when the person has no API figure, the recount rule);
earlier cycles keep pas2. Ryan stays at zero under every variant: his
committee maps to an unlinked candidate ID, so the API money is
unattributed — a roster gap, not a refund question.
"""

from collections import defaultdict
from functools import cache
from pathlib import Path

from receipts.domain.term import term_record
from receipts.square_one import parsers
from receipts.transform import compute_2026

CURRENT = 2026
API_CYCLES = (2022, 2024, 2026)
ALL_CYCLES = list(range(1980, 2027, 2))
BUCKET_MAP = {
    'party': 'party_committees',
    'leadership': 'leadership_pacs',
    'labor': 'labor_pacs',
    'trade': 'trade_pacs',
    'membership': 'membership_pacs',
    'cooperative': 'cooperative_pacs',
    'other_unclassified': 'other_unclassified',
}


def dollars(cents: int) -> float:
    """Integer cents as the dollars the cycle records carry, rounded to cents."""
    return round(cents / 100, 2)


def build_filed(bulk_dir: Path, cycles: list[int] | None = None) -> dict:
    """{(candidate_id, cycle): the election years the cycle's candidacies file for}."""
    filed: dict[tuple, set] = defaultdict(set)
    for cycle in cycles or ALL_CYCLES:
        for row in parsers.candidate_rows(bulk_dir, cycle):
            try:
                year = int(row.election_year)
            except ValueError:
                continue
            filed[(row.candidate_id, cycle)].add(year)
    return dict(filed)


def build_races_getter(bulk_dir: Path):
    """races_for(cycle) -> (race_map, race_of), as the store's races_in, from weball."""

    @cache
    def races_for(cycle: int):
        race_map: dict[tuple, list] = defaultdict(list)
        race_of: dict[str, tuple] = {}
        for row in parsers.weball_rows(bulk_dir, cycle):
            race = (row.candidate_id[0], row.office_state, row.office_district)
            race_map[race].append((row.candidate_id, row.cents('total_receipts')))
            race_of[row.candidate_id] = race
        return dict(race_map), race_of

    return races_for


def _aipac_for_cycle(entry: dict, corrected: dict | None, variant: str, person_key: str) -> int:
    """AIPAC direct cents for one (person, cycle): pas2, or the API substitution."""
    cycle = entry['cycle']
    if variant == 'baseline' or corrected is None or cycle not in API_CYCLES:
        return entry['aipac']
    field = 'aipac_a_cents' if variant == 'A' else 'aipac_b_cents'
    figure = corrected.get((person_key, cycle))
    return figure[field] if figure else 0


def _filed_aipac_or_corp(committee_money: dict, cid: str, cycle: int) -> bool:
    """Whether one candidate filed any AIPAC/corporate pas2 money in a cycle."""
    entry = committee_money.get((cid, cycle))
    if entry is None:
        return False
    return any(
        entry.get(field, 0) != 0
        for field in ('aipac', 'aipac_earmark', 'corporate', 'corporate_earmark')
    )


def build_person_lists(
    person: dict,
    rollup: dict,
    weball: dict,
    weball_filed: dict,
    committee_money: dict,
    corrected: dict | None,
    variant: str,
    udp_support: dict,
    all_ie: dict,
) -> dict:
    """One store-shaped person dict for compute_2026.cycle_record and headline.

    per_cycle / udp / other-committee / all-IE lists are per person per
    cycle; self-funding stays per candidate, so each candidate's own
    coverage end date decides linkage. A per_cycle entry exists where the
    pipeline's does: the candidate filed individual money, or any
    AIPAC/corporate pas2 money (direct or earmark) — as filed, so a
    double-count correction that leaves the counted figure at zero still
    counts as filed. A corrected API figure with no other data in the
    cycle still gets a per_cycle entry (the recount edge case), recorded
    in `edge_cycles` for the caller to inspect.
    """
    person_key = person['person_key']
    ids = person['fec_candidate_ids']
    edge_cycles = []
    per_cycle, udp, self_funding, other, all_ie_list = [], [], [], [], []
    for cycle in ALL_CYCLES:
        entry = rollup.get((person_key, cycle))
        if entry is None:
            entry = {'cycle': cycle, 'aipac': 0, 'has_weball': False, 'has_committee_money': False}
        aipac = _aipac_for_cycle(entry, corrected, variant, person_key)
        filed = any(
            weball_filed.get((cid, cycle), {}).get('individual', 0) != 0
            or _filed_aipac_or_corp(committee_money, cid, cycle)
            for cid in ids
        )
        if filed or aipac != 0:
            if not filed:
                edge_cycles.append(cycle)
            per_cycle.append(
                {
                    'cycle': cycle,
                    'individual': dollars(entry.get('individual', 0)),
                    'corporate_pac': dollars(entry.get('corporate', 0)),
                    'aipac_pac_direct': dollars(aipac),
                }
            )
        support = udp_support.get((person_key, cycle), 0)
        if support > 0:
            udp.append({'cycle': cycle, 'udp_ie_support': dollars(support)})
        if entry['has_weball']:
            for cid in ids:
                web = weball.get((cid, cycle))
                if web is None:
                    continue
                self_funding.append(
                    {
                        'cycle': cycle,
                        'candidate_contributions': dollars(web['cand_contrib']),
                        'candidate_loans': dollars(web['cand_loans']),
                        'total_receipts': dollars(web['total_receipts']),
                        'total_disbursements': dollars(web['total_disbursements']),
                        'cash_on_hand': dollars(web['cash_on_hand']),
                        'coverage_end_date': web['coverage_end'],
                    }
                )
        buckets = {field: dollars(entry.get(kind, 0)) for kind, field in BUCKET_MAP.items()}
        if any(buckets.values()):
            other.append({'cycle': cycle, **buckets})
        support_ie, oppose_ie, total_ie = all_ie.get((person_key, cycle), (0, 0, 0))
        if support_ie or oppose_ie or total_ie:
            all_ie_list.append(
                {
                    'cycle': cycle,
                    'all_ie_support': dollars(support_ie),
                    'all_ie_oppose': dollars(oppose_ie),
                    'all_ie_total': dollars(total_ie),
                }
            )
    return {
        'person_key': person_key,
        'full_name': person['full_name'],
        'in_120th': person['in_120th'],
        'chamber_120': person['chamber_120'],
        'senate_class': person['senate_class'],
        'fec_candidate_ids': ids,
        'per_cycle': per_cycle,
        'udp_per_cycle': udp,
        'self_funding_per_cycle': self_funding,
        'other_committees_per_cycle': other,
        'all_ie_per_cycle': all_ie_list,
        'edge_cycles': edge_cycles,
    }


def person_result(r: dict, credits: dict, races_for, filed: dict) -> dict:
    """Cycle-2026 record, headline verdict and term sums for one person."""
    records = []
    for cycle in compute_2026.cycles_of(r):
        record, _, _ = compute_2026.cycle_record(
            r, cycle, credits.get((cycle, r['person_key']), 0.0), races_for(cycle), filed
        )
        records.append(record)
    r['cycles'] = records
    head = compute_2026.headline(r, filed)
    c26 = next((c for c in records if c['cycle'] == CURRENT), None)
    term = (
        term_record(records, head['verdict_cycle']) if head['verdict_cycle'] is not None else None
    )
    return {
        'person_key': r['person_key'],
        'full_name': r['full_name'],
        'in_120': r['in_120th'] == 'yes',
        'chamber_120': r['chamber_120'],
        'c26': c26,
        'headline': head,
        'term': term,
        'cycles': records,
        'edge_cycles': r['edge_cycles'],
    }


def career_sums(rollup: dict, udp_support: dict, opp_credits: dict) -> dict:
    """Per-person career sums in cents: pas2 AIPAC, corporate PAC, UDP support, UDP credit."""
    sums: dict[str, dict] = {}
    for (key, _cycle), entry in rollup.items():
        person_sums = sums.setdefault(key, {'aipac': 0, 'corp': 0, 'udp_sup': 0, 'udp_cred': 0})
        person_sums['aipac'] += entry.get('aipac', 0)
        person_sums['corp'] += entry.get('corporate', 0)
    for (key, _cycle), cents in udp_support.items():
        sums.setdefault(key, {'aipac': 0, 'corp': 0, 'udp_sup': 0, 'udp_cred': 0})['udp_sup'] += (
            cents
        )
    for (key, _cycle), cents in opp_credits.items():
        sums.setdefault(key, {'aipac': 0, 'corp': 0, 'udp_sup': 0, 'udp_cred': 0})['udp_cred'] += (
            cents
        )
    return sums


def aipac_career_cents(
    person_key: str,
    rollup: dict,
    corrected: dict | None,
    variant: str,
    pas2_career: int,
) -> int:
    """One person's AIPAC career total in cents under a variant (recount formula)."""
    if variant == 'baseline' or corrected is None:
        return pas2_career
    pas2_3cy = sum(rollup.get((person_key, cycle), {}).get('aipac', 0) for cycle in API_CYCLES)
    api_3cy = 0
    jfc_3cy = 0
    for cycle in API_CYCLES:
        figure = corrected.get((person_key, cycle))
        if figure is None:
            continue
        api_3cy += figure['aipac_b_cents']
        jfc_3cy += figure['jfc_aipac_cents']
    if variant == 'A':
        return pas2_career - pas2_3cy + api_3cy + jfc_3cy
    return pas2_career - pas2_3cy + api_3cy


def career_clean(
    person_key: str,
    rollup: dict,
    corrected: dict | None,
    variant: str,
    sums: dict,
) -> bool:
    """No career dirty money: corporate PAC, AIPAC direct, UDP support and credit all zero."""
    person_sums = sums.get(person_key, {'aipac': 0, 'corp': 0, 'udp_sup': 0, 'udp_cred': 0})
    return (
        person_sums['corp'] == 0
        and aipac_career_cents(person_key, rollup, corrected, variant, person_sums['aipac']) == 0
        and person_sums['udp_sup'] == 0
        and person_sums['udp_cred'] == 0
    )


def count_results(results: list[dict]) -> dict:
    """The recount-shaped counts over the 120th (n=535)."""
    rows = [v for v in results if v['in_120']]
    c26 = [v['c26'] for v in rows if v['c26'] is not None]
    terms = [v for v in rows if v['term'] is not None]
    headlines = [v['headline'] for v in rows]

    def not_dirty(records, key):
        return sum(1 for r in records if r[key] in ('clean', 'below_threshold'))

    return {
        'n': len(rows),
        'c26_flag': sum(1 for c in c26 if c['aipac_udp_flag']),
        'c26_strict_clean': sum(1 for c in c26 if c['clean'] is True),
        'c26_null': sum(1 for c in c26 if c['clean'] is None),
        'c26_bal_notdirty': not_dirty(c26, 'tier_balanced'),
        'c26_len_notdirty': not_dirty(c26, 'tier_lenient'),
        'term_flag': sum(1 for v in terms if v['term']['aipac_udp_flag']),
        'term_strict_clean': sum(1 for h in headlines if h['clean'] is True),
        'term_null': sum(1 for h in headlines if h['clean'] is None),
        'term_bal_notdirty': not_dirty(headlines, 'tier_balanced'),
        'term_len_notdirty': not_dirty(headlines, 'tier_lenient'),
        'house_120th_career_clean': sum(
            1 for v in rows if v['chamber_120'] == 'House' and v['career_clean'] is True
        ),
    }


def run_variant(
    people: list[dict],
    rollup: dict,
    weball: dict,
    weball_filed: dict,
    committee_money: dict,
    corrected: dict | None,
    variant: str,
    udp_support: dict,
    all_ie: dict,
    opp_credits: dict,
    races_for,
    filed: dict,
) -> tuple[list[dict], dict]:
    """Per-person results and counts for one variant."""
    credits = {(cycle, key): cents / 100 for (key, cycle), cents in opp_credits.items()}
    sums = career_sums(rollup, udp_support, opp_credits)
    results = []
    for person in people:
        r = build_person_lists(
            person,
            rollup,
            weball,
            weball_filed,
            committee_money,
            corrected,
            variant,
            udp_support,
            all_ie,
        )
        result = person_result(r, credits, races_for, filed)
        result['career_clean'] = career_clean(
            person['person_key'], rollup, corrected, variant, sums
        )
        results.append(result)
    return results, count_results(results)
