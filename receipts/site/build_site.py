#!/usr/bin/env python3
"""The Receipts — static site generator.

Reads the canonical dataset (congress-money-tracker.json at the repo root)
and emits the static site under docs/ for GitHub Pages. The site is a
single self-contained index.html: the dataset is embedded in a compact
positional encoding (column list + array-of-arrays, ~1.6 MB vs 5.5 MB
minified JSON) and every view on the page — table, filters, leaderboards,
clean view, breakdown, primary targets, CSV download — is computed from
that embedded data at runtime, so the figures on the page can never drift
from the dataset. A second, smaller payload carries the race-phase UDP
opposition-credit detail (from data/intermediate/opposition-computed.json,
the race-level record) so a person's drill-down can show the credit split
by primary / general / other phase.

Usage:
    python3 receipts/site/build_site.py            # regenerate docs/index.html
    python3 receipts/site/verify_site.py           # verify the generated site

Rules (see AGENTS.md):
- Never hand-edit docs/index.html. The page lives in templates/ (page.html,
  style.css, tracker.js, views.js, method.html); edit those or this
  generator and re-run it.
- The generator must be deterministic apart from the generation timestamp
  in the footer (dataset md5 + data_as_of are the stable identifiers).
- Figures are never hardcoded in the template: header stats, leaderboards
  and totals are all computed from the embedded data in the browser.
- Two modes, one page (landing-first, Nov 12, 2026): the front door is
  the default — dirtiest in 2026, the clean story, the finder, one
  freshness line, one "Explore the full data" button — and #explore opens
  the full-data workspace (tabs, filters, table, methodology) with the
  story and finder removed from above the table. Mode, tab, filters,
  preset, view, sort and the open drill-down all live in the URL hash
  (Change 2, FE5): a view is shareable, and Back/forward restores it —
  Back from a drill-down closes the sheet.
"""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from receipts.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']
SITE_DIR = ROOT / CFG['paths']['site']
DATASET_JSON = ROOT / CFG['paths']['dataset_json']
DATASET_CSV = ROOT / CFG['paths']['dataset_csv']

# ---- compact encoding: column lists (fixed order) ----
# Scalar fields, in the order they appear in each row array. Must cover
# every field the page reads; the verifier checks the round-trip.
SCALARS = [
    'person_key',
    'full_name',
    'state',
    'district_119',
    'district_120',
    'chamber_119',
    'chamber_120',
    'party_119',
    'party_120',
    'leadership_119',
    'leadership_120',
    'in_119th',
    'in_120th',
    'fec_candidate_ids',
    'senate_class',
    'individual_contribution_total_career',
    'aipac_pac_direct_career',
    'aipac_earmark_transmitted_career',
    'corporate_pac_career',
    'corporate_earmark_transmitted_career',
    'udp_ie_support_career',
    'udp_ie_opposing_opponents_career',
    'udp_ie_total_benefit_career',
    'cand_contrib_career',
    'cand_loans_career',
    'self_funding_career',
    'loan_repayments_career',
    'debts_owed_by_career',
    'debts_owed_to_career',
    'total_receipts_career',
    'total_disbursements_career',
    'transfers_from_auth_career',
    'transfers_to_auth_career',
    'cash_on_hand_career',
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
    'total_accepted_career',
    'rank_total_accepted',
    'rank_individual',
    'rank_corporate_pac',
    'rank_aipac_direct',
    'rank_udp_support',
    'rank_udp_opposing_opponents',
    'rank_udp_total_benefit',
    'rank_self_funding',
    'rank_all_ie_support',
    'rank_all_ie_oppose',
    'rank_all_ie_total',
    'rank_other_committees_total',
    'corp_2026',
    'aipac_direct_2026',
    'individual_2026',
    'udp_support_2026',
    'udp_opp_credit_2026',
    'udp_benefit_2026',
    'dirty_2026',
    'dirty_career',
    'clean_2026',
    'unopposed_2026',
    'aipac_udp_flag_2026',
    'tier_balanced_2026',
    'tier_lenient_2026',
    'dep_share_2026',
    'self_funding_2026',
    'cand_loans_2026',
    'cand_contrib_2026',
    'total_receipts_2026',
    'total_disbursements_2026',
    'cash_on_hand_2026',
    'other_committees_total_2026',
    'all_ie_support_2026',
    'all_ie_oppose_2026',
    'all_ie_total_2026',
    'data_notes',
    'data_as_of',
]
PC_COLS = [
    'cycle',
    'candidate_id',
    'individual',
    'aipac_pac_direct',
    'aipac_earmark_transmitted',
    'corporate_pac',
    'corporate_earmark_transmitted',
]
UPC_COLS = ['cycle', 'candidate_id', 'udp_ie_support', 'attribution']
SF_COLS = [
    'cycle',
    'candidate_id',
    'candidate_contributions',
    'candidate_loans',
    'loan_repayments',
    'debts_owed_by',
    'debts_owed_to',
    'total_receipts',
    'total_disbursements',
    'cash_on_hand',
    'transfers_from_auth',
    'transfers_to_auth',
    'coverage_end_date',
]
OC_COLS = [
    'cycle',
    'candidate_id',
    'party_committees',
    'leadership_pacs',
    'labor_pacs',
    'trade_pacs',
    'membership_pacs',
    'cooperative_pacs',
    'other_unclassified',
    'earmark_transmitted',
    'winred_included',
]
AIE_COLS = [
    'cycle',
    'candidate_id',
    'all_ie_support',
    'all_ie_oppose',
    'all_ie_total',
    'no_direction_amount',
]
TC_COLS = ['committee_id', 'committee_name', 'support', 'oppose', 'total', 'rows']
# Nested lists sit at fixed positions after the scalars in each row array.
NESTED = [
    'per_cycle',
    'udp_per_cycle',
    'self_funding_per_cycle',
    'other_committees_per_cycle',
    'all_ie_per_cycle',
    'all_ie_top_committees',
]
NESTED_COLS = {
    'per_cycle': PC_COLS,
    'udp_per_cycle': UPC_COLS,
    'self_funding_per_cycle': SF_COLS,
    'other_committees_per_cycle': OC_COLS,
    'all_ie_per_cycle': AIE_COLS,
    'all_ie_top_committees': TC_COLS,
}


def encode_row(r):
    """One dataset row -> compact array: scalars, then six nested lists."""
    out = [r.get(k) for k in SCALARS]
    for name in NESTED:
        cols = NESTED_COLS[name]
        vals = r.get(name) or []
        out.append([[e.get(k) for k in cols] for e in vals])
    return out


def build_opp_payload():
    """Race-phase UDP opposition credit per roster person, for the drill-down.

    From data/intermediate/opposition-computed.json (the race-level record):
    {person_key: [{cycle, office, state, district, phase, amount, opposed:
    [[name, amount], ...]}, ...]}. Non-roster credits are excluded (no
    drill-down row exists for them). Deterministic: entries sorted by race
    key, opposed names by amount descending.
    """
    opp = json.loads((ROOT / CFG['paths']['opposition_computed']).read_text())
    out = {}
    for race, pk, _name, amount, opposed in opp['credit_detail']:
        if pk.startswith('__nonroster__'):
            continue
        cycle, office, state, district, ele_type = race
        out.setdefault(pk, []).append(
            {
                'cycle': cycle,
                'office': office,
                'state': state,
                'district': district,
                'phase': ele_type,
                'amount': round(float(amount), 2),
                'opposed': sorted(
                    [[n, round(float(a), 2)] for n, a in opposed.items()], key=lambda x: -x[1]
                ),
            }
        )
    for pk in out:
        out[pk].sort(key=lambda e: (e['cycle'], e['office'], e['state'], e['district'], e['phase']))
    return out


def safe_json(obj):
    """Minified JSON safe to embed inside a <script> tag."""
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')


TEMPLATES = Path(__file__).parent / 'templates'


def template(name):
    return (TEMPLATES / name).read_text(encoding='utf-8')


def page_template():
    """templates/page.html with its stylesheet and two scripts inlined: the page is one file."""
    page = template('page.html')
    for slot, name in (
        ('%%STYLE%%', 'style.css'),
        ('%%TRACKER_JS%%', 'tracker.js'),
        ('%%VIEWS_JS%%', 'views.js'),
    ):
        page = page.replace(slot, template(name))
    return page


def human_list(names):
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} and {names[1]}'
    return ', '.join(names[:-1]) + f', and {names[-1]}'


def is_career_clean(r):
    """Same four-component rule as the site's isCareerClean."""
    return (
        r['corporate_pac_career'] == 0
        and r['aipac_pac_direct_career'] == 0
        and r['udp_ie_support_career'] == 0
        and r['udp_ie_opposing_opponents_career'] == 0
    )


def clean_method_html(dataset):
    """The methodology clean paragraph, computed from the dataset.

    Every figure in the paragraph is computed here — never hardcoded —
    so a data change cannot strand stale numbers in the live page.
    Tokens are replaced in main(); verify_site.py fails the build if
    any %%TOKEN%% survives unreplaced.
    """
    incoming = [r for r in dataset if r['in_120th'] == 'yes']
    house = [r for r in incoming if r['chamber_120'] == 'House']
    sen = [r for r in incoming if r['chamber_120'] == 'Senate']
    h_clean = [r for r in house if r['clean_2026'] is True]
    s_clean = [r for r in sen if r['clean_2026'] is True]
    h_r = [r['full_name'] for r in h_clean if r['party_120'] == 'Republican']
    if h_r:
        n = len(h_r)
        r_sentence = (
            f'The {n} clean House Republican{"s are" if n > 1 else " is"} {human_list(h_r)}.'
        )
    else:
        r_sentence = 'No House Republican is verified clean.'
    unver = [r['full_name'] for r in dataset if r['clean_2026'] is None and not r['unopposed_2026']]
    if len(unver) == 1:
        unver_sentence = f'{unver[0]} is the one unverified member.'
    elif unver:
        unver_sentence = f'{len(unver)} members are unverified: {human_list(unver)}.'
    else:
        unver_sentence = 'No member is unverified.'
    excluded = [r['full_name'] for r in dataset if r['unopposed_2026'] and r['clean_2026'] is None]
    if excluded:
        n = len(excluded)
        unopp_sentence = (
            f'{n} {"members ran" if n > 1 else "member ran"} unopposed in 2026 — '
            f'no opponent with receipts over $0 — so $0 dirty money there is not '
            f'counted as verified-clean: {human_list(excluded)}.'
        )
    else:
        unopp_sentence = 'No member ran unopposed in 2026.'
    tokens = {
        '%%CLEAN_TOTAL_120%%': str(len(h_clean) + len(s_clean)),
        '%%HOUSE_CLEAN%%': str(len(h_clean)),
        '%%HOUSE_CLEAN_D%%': str(sum(1 for r in h_clean if r['party_120'] == 'Democrat')),
        '%%HOUSE_CLEAN_R%%': str(len(h_r)),
        '%%SEN_CLEAN%%': str(len(s_clean)),
        '%%SEN_CLEAN_D%%': str(sum(1 for r in s_clean if r['party_120'] == 'Democrat')),
        '%%SEN_CLEAN_I%%': str(sum(1 for r in s_clean if r['party_120'] == 'Independent')),
        '%%SEN_CLEAN_R%%': str(sum(1 for r in s_clean if r['party_120'] == 'Republican')),
        '%%CLEAN_HOUSE_R_SENTENCE%%': r_sentence,
        '%%UNVERIFIED_SENTENCE%%': unver_sentence,
        '%%UNOPPOSED_SENTENCE%%': unopp_sentence,
        '%%CAREER_CLEAN_HOUSE%%': str(sum(1 for r in house if is_career_clean(r))),
        '%%BALANCED_NOT_DIRTY%%': str(
            sum(1 for r in incoming if r['tier_balanced_2026'] in ('clean', 'below_threshold'))
        ),
        '%%LENIENT_NOT_DIRTY%%': str(
            sum(1 for r in incoming if r['tier_lenient_2026'] in ('clean', 'below_threshold'))
        ),
        '%%FLAG_120%%': str(sum(1 for r in incoming if r['aipac_udp_flag_2026'] is True)),
    }
    html = template('method.html')
    for token, value in tokens.items():
        html = html.replace(token, value)
    return html


def main():
    dataset = json.loads(DATASET_JSON.read_text())
    if not isinstance(dataset, list):
        raise SystemExit('dataset JSON is not a list')
    with open(DATASET_CSV, newline='') as f:
        csv_cols = next(csv.reader(f))
    missing = [k for k in SCALARS if k not in dataset[0]]
    if missing:
        raise SystemExit(f'dataset rows missing scalar fields: {missing}')
    rows = [encode_row(r) for r in dataset]
    opp_payload = build_opp_payload()
    cols_payload = {
        'scalars': SCALARS,
        'pc': PC_COLS,
        'upc': UPC_COLS,
        'sf': SF_COLS,
        'oc': OC_COLS,
        'aie': AIE_COLS,
        'tc': TC_COLS,
        'csv': csv_cols,
    }
    dataset_md5 = hashlib.md5(DATASET_JSON.read_bytes()).hexdigest()
    data_as_of = sorted({r.get('data_as_of', '') for r in dataset})
    # Visible data-as-of stamp (header). Coverage end dates come from
    # config.yaml verification.coverage_end — never hardcoded here.
    # The build time reuses the exact "Generated <ts>" string the footer
    # uses, so the verifier's strip_ts regex normalizes both occurrences
    # and the generator stays deterministic apart from that timestamp.
    coverage = CFG['verification']['coverage_end']

    def fmt_cov(iso):
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%b %d, %Y')

    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    stamp = (
        'Data as of \u2014 committee money through '
        f'{fmt_cov(coverage["committee_money_pas2"])}; '
        'individual / self-funding / topline through '
        f'{fmt_cov(coverage["weball"])}; '
        'independent expenditures through '
        f'{fmt_cov(coverage["independent_expenditures"])}. '
        f'2026 is partial. Generated {generated_at}.'
    )
    # Front-door freshness line: one line, from the same config dates —
    # the latest coverage end across families, never a typed date.
    fresh_line = (
        'Data through '
        f'{fmt_cov(max(coverage.values()))}'
        ' \u2014 2026 is partial. Full coverage dates in the methodology.'
    )
    html = page_template()
    html = html.replace('%%METHOD_HTML%%', clean_method_html(dataset))
    html = html.replace('%%COLS_JSON%%', safe_json(cols_payload))
    html = html.replace('%%DATA_JSON%%', safe_json(rows))
    html = html.replace('%%OPP_JSON%%', safe_json(opp_payload))
    targets_2026_house = sum(
        1
        for r in dataset
        if r['in_120th'] == 'yes'
        and r['chamber_120'] == 'House'
        and r['party_120'] == 'Democrat'
        and isinstance(r['dirty_2026'], (int, float))
        and r['dirty_2026'] > 0
    )
    html = html.replace('%%TARGETS_2026_HOUSE%%', str(targets_2026_house))
    html = html.replace('%%DATASET_MD5%%', dataset_md5)
    html = html.replace('%%DATA_AS_OF%%', ', '.join(data_as_of))
    html = html.replace('%%STAMP%%', stamp)
    html = html.replace('%%COV_PAS2%%', fmt_cov(coverage['committee_money_pas2']))
    html = html.replace('%%COV_WEBALL%%', fmt_cov(coverage['weball']))
    html = html.replace('%%COV_IE%%', fmt_cov(coverage['independent_expenditures']))
    html = html.replace('%%FRESH_LINE%%', fresh_line)
    html = html.replace('%%GENERATED_AT%%', generated_at)
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    out = SITE_DIR / 'index.html'
    out.write_text(html, encoding='utf-8')
    print(f'rows: {len(rows)}')
    print(f'dataset md5: {dataset_md5}')
    print(f'embedded payload bytes: {len(safe_json(rows))}')
    print(
        f'opposition detail: {len(opp_payload)} persons, '
        f'{sum(len(v) for v in opp_payload.values())} race-phases'
    )
    print(f'wrote {out} ({out.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
