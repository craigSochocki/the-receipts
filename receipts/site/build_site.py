#!/usr/bin/env python3
"""Generate the three site pages from templates/ and the dataset; never hand-edit the output."""

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from receipts.common.log import log, run
from receipts.common.settings import settings
from receipts.domain.clean_2026 import is_career_clean, is_not_dirty
from receipts.domain.seats import regular_senate_class
from receipts.site.expectations import latest
from receipts.site.static_explore import render_explore_slots
from receipts.site.static_render import render_story_slots
from receipts.store.read import connect
from receipts.transform.compute_2026 import cycle_fields

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
    'pro_israel_pac_career',
    'pro_israel_ie_support_career',
    'pro_israel_opp_credit_career',
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
    'verdict_cycle',
    'clean',
    'dirty',
    'tier_balanced',
    'tier_lenient',
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
PI_COLS = ['cycle', 'pro_israel_pac', 'pro_israel_ie_support', 'pro_israel_opp_credit']


def cycle_cols():
    return ['cycle', *cycle_fields(), 'up_for_election']


# Nested lists sit at fixed positions after the scalars in each row array.
NESTED = [
    'per_cycle',
    'udp_per_cycle',
    'self_funding_per_cycle',
    'other_committees_per_cycle',
    'all_ie_per_cycle',
    'all_ie_top_committees',
    'cycles',
    'pro_israel_per_cycle',
]
NESTED_COLS = {
    'per_cycle': PC_COLS,
    'udp_per_cycle': UPC_COLS,
    'self_funding_per_cycle': SF_COLS,
    'other_committees_per_cycle': OC_COLS,
    'all_ie_per_cycle': AIE_COLS,
    'all_ie_top_committees': TC_COLS,
    'pro_israel_per_cycle': PI_COLS,
}


def encode_row(r):
    """One dataset row -> compact array: scalars, then the nested lists."""
    out = [r.get(k) for k in SCALARS]
    for name in NESTED:
        cols = cycle_cols() if name == 'cycles' else NESTED_COLS[name]
        vals = r.get(name) or []
        out.append([[e.get(k) for k in cols] for e in vals])
    return out


def build_opp_payload():
    """Race-phase UDP opposition credit per roster person, sorted for a deterministic page."""
    race = 'cycle, office, state, district, election_type, credited_to'
    with connect() as db:
        credits = db.execute(
            f'SELECT {race}, credit FROM gold.opposition_credits '
            "WHERE credited_to NOT LIKE '__nonroster__%'"
        ).fetchall()
        opposed = defaultdict(list)
        for *key, name, cents in db.execute(
            f'SELECT {race}, opposed_name, amount FROM gold.opposition_opposed ORDER BY position'
        ).fetchall():
            opposed[tuple(key)].append([name, cents / 100])
    out = {}
    for *key, credit in credits:
        cycle, office, state, district, phase, person_key = key
        out.setdefault(person_key, []).append(
            {
                'cycle': cycle,
                'office': office,
                'state': state,
                'district': district,
                'phase': phase,
                'amount': credit / 100,
                'opposed': sorted(opposed[tuple(key)], key=lambda x: -x[1]),
            }
        )
    for entries in out.values():
        entries.sort(key=lambda e: (e['cycle'], e['office'], e['state'], e['district'], e['phase']))
    return out


def safe_json(obj):
    """Minified JSON safe to embed inside a <script> tag."""
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')


TEMPLATES = Path(__file__).parent / 'templates'


def template(name):
    return (TEMPLATES / name).read_text(encoding='utf-8')


def vendor_script(name):
    """A vendored library, inlined; a missing file fails the build loudly."""
    path = TEMPLATES / 'vendor' / name
    if not path.exists():
        raise SystemExit(f'missing vendored library: {path}')
    return path.read_text(encoding='utf-8')


def script_tag(src):
    return f'<script>{src}</script>'


def json_tag(script_id, payload):
    return f'<script id="{script_id}" type="application/json">{safe_json(payload)}</script>'


# Nav hrefs per page: the site is served from the docs/ root, the Story
# at the root and Explore / Methodology one level down.
NAV = {
    'story': {
        '%%NAV_STORY%%': './',
        '%%NAV_EXPLORE%%': 'explore/',
        '%%NAV_METHOD%%': 'methodology/',
        '%%NAV_SEARCH%%': 'explore/#search',
    },
    'explore': {
        '%%NAV_STORY%%': '../',
        '%%NAV_EXPLORE%%': './',
        '%%NAV_METHOD%%': '../methodology/',
        '%%NAV_SEARCH%%': '#search',
    },
    'methodology': {
        '%%NAV_STORY%%': '../',
        '%%NAV_EXPLORE%%': '../explore/',
        '%%NAV_METHOD%%': './',
        '%%NAV_SEARCH%%': '../explore/#search',
    },
}


def assemble(body, page_style, vendor_scripts, page_scripts, nav):
    """The shared shell around one page's body fragment.

    The shell's own slots are filled before the body goes in, so slot
    names mentioned inside a fragment (its wiring comments) are never
    expanded by mistake.
    """
    html = template('shell.html')
    html = html.replace('%%STYLE%%', template('style.css'))
    html = html.replace('%%PAGE_STYLE%%', page_style)
    html = html.replace('%%VENDOR_SCRIPTS%%', vendor_scripts)
    html = html.replace('%%PAGE_SCRIPTS%%', page_scripts)
    html = html.replace('%%BODY%%', body)
    for token, href in nav.items():
        html = html.replace(token, href)
    return html


def human_list(names):
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} and {names[1]}'
    return ', '.join(names[:-1]) + f', and {names[-1]}'


def republicans_sentence(names):
    if not names:
        return 'No House Republican is verified clean.'
    n = len(names)
    return f'The {n} clean House Republican{"s are" if n > 1 else " is"} {human_list(names)}.'


def unverified_sentence(names):
    if len(names) == 1:
        return f'{names[0]} is the one unverified member.'
    if names:
        return f'{len(names)} members are unverified: {human_list(names)}.'
    return 'No member is unverified.'


def unopposed_sentence(names):
    if not names:
        return f'No member ran unopposed in {settings().cycles.current}.'
    n = len(names)
    return (
        f'{n} {"members ran" if n > 1 else "member ran"} unopposed in {settings().cycles.current} — '
        f'no opponent with receipts over $0 — so $0 dirty money there is not '
        f'counted as verified-clean: {human_list(names)}.'
    )


def count_party(rows, party):
    return str(sum(1 for r in rows if r['party_120'] == party))


def clean_count_tokens(h_clean, s_clean):
    return {
        '%%CLEAN_TOTAL_120%%': str(len(h_clean) + len(s_clean)),
        '%%HOUSE_CLEAN%%': str(len(h_clean)),
        '%%HOUSE_CLEAN_D%%': count_party(h_clean, 'Democrat'),
        '%%HOUSE_CLEAN_R%%': count_party(h_clean, 'Republican'),
        '%%SEN_CLEAN%%': str(len(s_clean)),
        '%%SEN_CLEAN_D%%': count_party(s_clean, 'Democrat'),
        '%%SEN_CLEAN_I%%': count_party(s_clean, 'Independent'),
        '%%SEN_CLEAN_R%%': count_party(s_clean, 'Republican'),
    }


def sentence_tokens(dataset, h_clean):
    unknown = [r for r in dataset if latest(r)['clean'] is None]
    return {
        '%%CLEAN_HOUSE_R_SENTENCE%%': republicans_sentence(
            [r['full_name'] for r in h_clean if r['party_120'] == 'Republican']
        ),
        '%%UNVERIFIED_SENTENCE%%': unverified_sentence(
            [r['full_name'] for r in unknown if not latest(r)['unopposed']]
        ),
        '%%UNOPPOSED_SENTENCE%%': unopposed_sentence(
            [r['full_name'] for r in unknown if latest(r)['unopposed']]
        ),
    }


def count_where(rows, test):
    return str(sum(1 for r in rows if test(r)))


def preset_tokens(incoming, house):
    return {
        '%%CAREER_CLEAN_HOUSE%%': count_where(house, is_career_clean),
        '%%BALANCED_NOT_DIRTY%%': count_where(
            incoming, lambda r: is_not_dirty(latest(r)['tier_balanced'])
        ),
        '%%LENIENT_NOT_DIRTY%%': count_where(
            incoming, lambda r: is_not_dirty(latest(r)['tier_lenient'])
        ),
        '%%FLAG_120%%': count_where(incoming, lambda r: latest(r)['aipac_udp_flag'] is True),
    }


def fmt_date(iso):
    return datetime.strptime(iso, '%Y-%m-%d').strftime('%b %d, %Y')


def preset_value_tokens():
    """The tolerance thresholds and the next FEC update, as the methodology page states them."""
    presets = settings().verification.tolerance_presets
    return {
        '%%BALANCED_CORP_AMOUNT%%': f'${presets["balanced"].corp_amount:,}',
        '%%BALANCED_CORP_SHARE%%': f'{presets["balanced"].corp_share * 100:g}%',
        '%%LENIENT_CORP_AMOUNT%%': f'${presets["lenient"].corp_amount:,}',
        '%%LENIENT_CORP_SHARE%%': f'{presets["lenient"].corp_share * 100:g}%',
        '%%NEXT_FEC_UPDATE%%': fmt_date(settings().verification.next_repull),
    }


def method_tokens(dataset):
    """Every figure and sentence the methodology clean paragraph shows."""
    incoming = [r for r in dataset if r['in_120th'] == 'yes']
    house = [r for r in incoming if r['chamber_120'] == 'House']
    h_clean = [r for r in house if latest(r)['clean'] is True]
    s_clean = [r for r in incoming if r['chamber_120'] == 'Senate' and latest(r)['clean'] is True]
    return {
        **clean_count_tokens(h_clean, s_clean),
        **sentence_tokens(dataset, h_clean),
        **preset_tokens(incoming, house),
    }


def method_html(dataset):
    """The Methodology page body: the fragment with every token computed."""
    html = template('method.html')
    for token, value in {**method_tokens(dataset), **preset_value_tokens()}.items():
        html = html.replace(token, value)
    return html


def cycle_tokens():
    cycles = settings().cycles
    return {
        '%%CYCLE%%': str(cycles.current),
        '%%NEXT_CYCLE%%': str(cycles.next),
        '%%CAREER_START%%': str(cycles.career_start),
        '%%CAREER_END%%': str(cycles.career_end),
        '%%IE_SPAN%%': f'{cycles.ie[0]}–{cycles.ie[-1]}',
    }


def shared_tokens(dataset_md5, data_as_of, generated_at):
    """Tokens every page carries: the stamp, the freshness line, the cycle labels.

    Coverage end dates come from config.yaml verification.coverage_end —
    never hardcoded here. The stamp reuses the exact "Generated <ts>"
    string, so the verifier's strip_ts regex normalizes every
    occurrence and the generator stays deterministic apart from that
    timestamp.
    """
    coverage = asdict(settings().verification.coverage_end)
    stamp = (
        'Data as of \u2014 committee money through '
        f'{fmt_date(coverage["committee_money_pas2"])}; '
        'individual / self-funding / topline through '
        f'{fmt_date(coverage["weball"])}; '
        'independent expenditures through '
        f'{fmt_date(coverage["independent_expenditures"])}. '
        f'{settings().cycles.current} is partial. Generated {generated_at}.'
    )
    # Freshness line: one line, from the same config dates — the latest
    # coverage end across families, never a typed date.
    fresh_line = (
        'Data through '
        f'{fmt_date(max(coverage.values()))}'
        f' \u2014 {settings().cycles.current} is partial. Full coverage dates in the methodology.'
    )
    return {
        **cycle_tokens(),
        '%%DATASET_MD5%%': dataset_md5,
        '%%DATA_AS_OF%%': data_as_of,
        '%%STAMP%%': stamp,
        '%%COV_PAS2%%': fmt_date(coverage['committee_money_pas2']),
        '%%COV_WEBALL%%': fmt_date(coverage['weball']),
        '%%COV_IE%%': fmt_date(coverage['independent_expenditures']),
        '%%FRESH_LINE%%': fresh_line,
        '%%GENERATED_AT%%': generated_at,
    }


def finish(html, shared):
    for token, value in shared.items():
        html = html.replace(token, value)
    return html


def write_page(path, html):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')
    log.info(f'wrote {path} ({path.stat().st_size} bytes)')


def main():
    dataset = json.loads(settings().paths.dataset_json.read_text())
    if not isinstance(dataset, list):
        raise SystemExit('dataset JSON is not a list')
    with open(settings().paths.dataset_csv, newline='') as f:
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
        'cy': cycle_cols(),
        'pi': PI_COLS,
        'current_cycle': settings().cycles.current,
        'next_cycle': settings().cycles.next,
        'next_senate_class': regular_senate_class(settings().cycles.next),
        'picker_cycles': settings().cycles.picker,
        'ie_span': cycle_tokens()['%%IE_SPAN%%'],
        'csv': csv_cols,
    }
    dataset_md5 = hashlib.md5(settings().paths.dataset_json.read_bytes()).hexdigest()
    data_as_of = ', '.join(sorted({r.get('data_as_of', '') for r in dataset}))
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    shared = shared_tokens(dataset_md5, data_as_of, generated_at)
    site_dir = settings().paths.site

    vendor = ''.join(
        script_tag(vendor_script(name))
        for name in ('d3.min.js', 'plot.umd.min.js', 'scrollama.min.js')
    )
    story = assemble(
        render_story_slots(template('story.html'), dataset),
        '',
        vendor,
        script_tag(template('story.js')),
        NAV['story'],
    )
    story = story.replace(
        '%%US_STATES_JSON%%', settings().paths.us_states_geometry.read_text().strip()
    )
    story = story.replace(
        '%%US_DISTRICTS_JSON%%', settings().paths.us_districts_geometry.read_text().strip()
    )
    write_page(site_dir / 'index.html', finish(story, shared))

    explore_scripts = (
        json_tag('receipts-cols', cols_payload)
        + json_tag('receipts-data', rows)
        + json_tag('opp-data', opp_payload)
        + script_tag(template('explore.js'))
    )
    explore = assemble(
        render_explore_slots(template('explore.html'), dataset),
        template('explore.css'),
        '',
        explore_scripts,
        NAV['explore'],
    )
    write_page(site_dir / 'explore' / 'index.html', finish(explore, shared))

    methodology = assemble(method_html(dataset), template('method.css'), '', '', NAV['methodology'])
    write_page(site_dir / 'methodology' / 'index.html', finish(methodology, shared))

    log.info(f'rows: {len(rows)}')
    log.info(f'dataset md5: {dataset_md5}')
    log.info(f'embedded payload bytes: {len(safe_json(rows))}')
    log.info(
        f'opposition detail: {len(opp_payload)} persons, '
        f'{sum(len(v) for v in opp_payload.values())} race-phases'
    )


if __name__ == '__main__':
    run(main)
