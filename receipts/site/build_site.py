#!/usr/bin/env python3
"""Generate docs/index.html from templates/ and the dataset; never hand-edit the output."""

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from receipts.common.log import log, run
from receipts.common.settings import settings
from receipts.domain.clean_2026 import is_career_clean, is_not_dirty
from receipts.domain.seats import regular_senate_class
from receipts.domain.targets import primary_targets
from receipts.site.expectations import dollars, latest
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


def page_template():
    """templates/page.html with its stylesheet and scripts inlined: the page is one file.

    The vendored libraries come first (d3, then Plot on the d3 global,
    then scrollama), then the tracker's own scripts.
    """
    page = template('page.html')
    for slot, name in (
        ('%%D3_JS%%', 'd3.min.js'),
        ('%%PLOT_JS%%', 'plot.umd.min.js'),
        ('%%SCROLLAMA_JS%%', 'scrollama.min.js'),
    ):
        page = page.replace(slot, vendor_script(name))
    for slot, name in (
        ('%%STYLE%%', 'style.css'),
        ('%%TRACKER_JS%%', 'tracker.js'),
        ('%%VIEWS_JS%%', 'views.js'),
        ('%%STORY_JS%%', 'story.js'),
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


def clean_method_html(dataset):
    """The methodology clean paragraph, every figure computed from the dataset."""
    html = template('method.html')
    for token, value in method_tokens(dataset).items():
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


# ---- server-rendered story text (the no-JS fallback) ----
# The step cards' text, computed here from the dataset exactly as
# story.js storyTexts() computes it in the browser: default preset
# (Balanced) and the latest election. The script re-renders on preset
# or cycle change, so this static text is the default-view fallback.


def esc_html(value):
    """The page's esc(): the same replacements, in the same order."""
    text = '' if value is None else str(value)
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;')
    )


def _to_fixed(value, places):
    """A number with fixed decimals, halves rounded away from zero like the page."""
    quantum = Decimal(1).scaleb(-places)
    return format(Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP), 'f')


def fmt_compact(value):
    """Compact money, as the page formats it."""
    if value is None:
        return '—'
    if value == 'unknown':
        return 'unknown'
    if not isinstance(value, (int, float)):
        return str(value)
    neg = value < 0
    size = abs(value)
    if size >= 1e9:
        text = f'${_to_fixed(size / 1e9, 2)}B'
    elif size >= 1e6:
        text = f'${_to_fixed(size / 1e6, 2)}M'
    elif size >= 1e3:
        text = f'${_to_fixed(size / 1e3, 1)}K'
    else:
        text = f'${_to_fixed(size, 0)}'
    return ('\u2212' if neg else '') + text


def preset_short(preset):
    """The tolerance short label, from the config thresholds."""
    return (
        f'corporate PAC over ${preset.corp_amount // 1000}k'
        f' and over {round(preset.corp_share * 100)}% of receipts'
    )


def story_steps():
    """The step names, read from story.js so the renderer follows it."""
    match = re.search(r'const STORY_STEPS = \[([^\]]+)\]', template('story.js'))
    if not match:
        raise SystemExit('story.js has no STORY_STEPS list')
    return re.findall(r"'(\w+)'", match.group(1))


def story_status(person):
    """The Balanced tier, or unjudged where there is none."""
    tier = latest(person)['tier_balanced']
    return tier if tier is not None else 'unjudged'


def party_of(person):
    return person['party_120'] or person['party_119'] or '—'


def party_groups(people):
    """The people grouped Democrats / Republicans / Others, in that order."""
    named = {'Democrat': 'Democrats', 'Republican': 'Republicans'}
    groups = []
    for label in ('Democrats', 'Republicans', 'Others'):
        members = [p for p in people if named.get(party_of(p), 'Others') == label]
        if members:
            groups.append((label, members))
    return groups


def group_line(groups):
    """One '<b>n of m</b> Label' per group, joined as the page joins them."""
    parts = []
    for label, members in groups:
        dirty = sum(1 for p in members if story_status(p) == 'dirty')
        parts.append(f'<b>{dirty} of {len(members)}</b> {esc_html(label)}')
    return ' · '.join(parts)


def incoming_members(dataset):
    """The members of the incoming Congress."""
    return [r for r in dataset if r['in_120th'] == 'yes']


def chamber_members(people, chamber):
    """The incoming members of one chamber."""
    return [p for p in people if p['chamber_120'] == chamber]


def count_dirty(people):
    """How many of these people took dirty money under the default preset."""
    return sum(1 for p in people if story_status(p) == 'dirty')


def count_not_dirty(people):
    """How many of these people were not dirty under the default preset."""
    return sum(1 for p in people if is_not_dirty(latest(p)['tier_balanced']))


def story_texts(dataset):
    """Every step card's text, computed from the dataset."""
    people = incoming_members(dataset)
    preset = settings().verification.tolerance_presets['balanced']
    top = max(people, key=lambda p: dollars(latest(p)['dirty']))
    targets = primary_targets(people, 'balanced', settings().cycles.next)
    house = chamber_members(people, 'House')
    senate = chamber_members(people, 'Senate')
    return {
        'all': (
            f'These are the <b>{len(people)}</b> members of the incoming 120th Congress. '
            'Each dot is one person.'
        ),
        'status': (
            f'<b>{count_dirty(people)}</b> of them took dirty money since their last election — '
            'corporate PAC, AIPAC PAC direct or UDP benefit. '
            f'<b>{count_not_dirty(people)}</b> were not dirty. '
            'The rest were not judged (unopposed or unlinked). '
            f'Balanced tolerance: {esc_html(preset_short(preset))}.'
        ),
        'ranked': (
            'Lined up by how much: '
            f'<b>{esc_html(top["full_name"])}</b> took '
            f'<b>{esc_html(fmt_compact(dollars(latest(top)["dirty"])))}</b> '
            'since their last election, the most of anyone arriving in the 120th.'
        ),
        'party': f'By party, dirty: {group_line(party_groups(people))}.',
        'house': (f'The House, seat by seat: {group_line(party_groups(house))} took dirty money.'),
        'districts': (
            'District by district: each House seat shaded by its member — party colour, '
            'strong when dirty, light when below threshold, white when clean. '
            'The five territorial delegates are not on the map.'
        ),
        'senate': (
            'The Senate, state by state: '
            f'{group_line(party_groups(senate))} took dirty money. '
            'Each state is shaded by its senators’ parties; each dot is one senator.'
        ),
        'targets': (
            f'<b>{len(targets)}</b> hold seats on the ballot in {settings().cycles.next} '
            'and took dirty money — the primary targets. '
            '<button type="button" class="linklike" data-story-go="targets">See the list</button>'
        ),
        'find': (
            'Which one is yours? '
            '<button type="button" class="linklike" data-story-go="finder">Find your member</button> '
            'and their dot lights up.'
        ),
    }


def render_story_slots(html, dataset):
    """Fill each step card's slot with its computed text."""
    texts = story_texts(dataset)
    for step in story_steps():
        if step not in texts:
            raise SystemExit(f'no server-rendered text for story step: {step}')
        html = html.replace(f'%%STORY_{step.upper()}%%', texts[step])
    return html


# ---- server-rendered main table (the no-JS fallback) ----
# The default column view (core) and default sort, rendered from the
# dataset as tracker.js renderTable() renders them in the browser.
# The script re-renders on first entry into Explore, so these rows
# are the fallback for a reader with no script.
CORE_COLS = [
    ('full_name', 'Name', 'name'),
    ('place', 'State / Dist.', 'place'),
    ('party', 'Party', 'party'),
    ('outcome', 'Outcome', 'outcome'),
    ('chamber', 'Chamber', 'chamber'),
    ('congress', 'Congress', 'congress'),
    ('individual_contribution_total_career', 'Individual (career)', 'money'),
    ('corporate_pac_career', 'Corp PAC (career)', 'money'),
    ('aipac_pac_direct_career', 'AIPAC direct (career)', 'money'),
    ('total_accepted_career', 'Total accepted', 'money'),
    ('rank_total_accepted', 'Rank', 'rank'),
    ('cy_dirty', 'Dirty latest', 'money'),
    ('cy_clean', 'Tier latest', 'clean'),
]
CORE_SORTABLE = frozenset(
    [
        'full_name',
        'individual_contribution_total_career',
        'corporate_pac_career',
        'aipac_pac_direct_career',
        'total_accepted_career',
        'rank_total_accepted',
        'cy_dirty',
    ]
)


def fmt_money(value):
    """Exact money, as the page formats it."""
    if value is None:
        return '—'
    if value == 'unknown':
        return 'unknown'
    if not isinstance(value, (int, float)):
        return str(value)
    return ('\u2212$' if value < 0 else '$') + f'{abs(value):,.2f}'


def fmt_rank(value):
    return '—' if value is None else f'#{value}'


def place_of(person):
    """State and district, or the state Senate seat."""
    district = (
        person['district_120']
        if person['district_120'] not in ('', None)
        else person['district_119']
    )
    if person['chamber_120'] == 'Senate' or person['chamber_119'] == 'Senate':
        return f'{person["state"]} · Senate'
    return person['state'] + (f'-{district}' if district not in ('', None) else '')


def party_chip(person):
    """The party letter chip: letter and colour, never colour alone."""
    name = person['party_120'] or person['party_119'] or ''
    if not name:
        return ''
    letter, cls = {'Democrat': ('D', 'd'), 'Republican': ('R', 'r'), 'Independent': ('I', 'o')}.get(
        name, (name, 'o')
    )
    return f'<span class="pchip {cls}" title="{esc_html(name)}">{esc_html(letter)}</span>'


def outcome_of(person):
    if person['in_120th'] == 'yes':
        return 'Won'
    if person['in_120th'] == 'unknown':
        return 'Uncalled'
    return 'Not returning'


def chamber_of(person):
    return person['chamber_120'] or person['chamber_119'] or '—'


def congress_of(person):
    if person['in_119th'] == 'yes' and person['in_120th'] == 'yes':
        return '119th + 120th'
    if person['in_120th'] == 'yes':
        return '120th'
    if person['in_119th'] == 'yes':
        return '119th'
    return 'TBD'


def table_value(person, key):
    """The cell value, as the page's getVal reads it."""
    if key == 'place':
        return place_of(person)
    if key == 'party':
        return party_of(person)
    if key == 'chamber':
        return chamber_of(person)
    if key == 'congress':
        return congress_of(person)
    if key == 'cy_dirty':
        return latest(person)['dirty']
    return person[key]


def fmt_tier_badge(person):
    """The tier badge for the latest election, as the page renders it."""
    record = latest(person)
    tier = record['tier_balanced']
    if tier is None:
        if record['unopposed'] is True:
            return '<span class="badge unopp">Unopposed</span>'
        return '<span class="badge unver">Unverified</span>'
    if tier == 'clean':
        return '<span class="badge clean">Clean</span>'
    if tier == 'below_threshold':
        return f'<span class="badge below">Below threshold · {fmt_money(record["corp"])}</span>'
    flag = (
        ' <span class="badge flag" title="Took AIPAC PAC direct money or UDP benefit '
        'since their last election — flagged under every tolerance preset">AIPAC/UDP</span>'
        if record['aipac_udp_flag'] is True
        else ''
    )
    return f'<span class="badge dirty">Dirty</span>{flag}'


def table_cell(person, key, kind):
    """One cell's HTML, as the page's cellHtml renders it."""
    if kind == 'name':
        return (
            '<button type="button" class="name-btn" data-key="'
            f'{esc_html(person["person_key"])}">{esc_html(person["full_name"])}</button>'
        )
    if kind == 'party':
        return party_chip(person) or '—'
    if kind == 'outcome':
        return outcome_of(person)
    if kind == 'money':
        value = table_value(person, key)
        return f'<span title="{esc_html(fmt_money(value))}">{fmt_compact(value)}</span>'
    if kind == 'rank':
        return fmt_rank(table_value(person, key))
    if kind == 'clean':
        return fmt_tier_badge(person)
    return esc_html(table_value(person, key) or '—')


def table_thead():
    """The default view's header row, with the default sort marked."""
    cells = []
    for key, label, kind in CORE_COLS:
        sortable = key in CORE_SORTABLE
        cls = ' class="num"' if kind in ('money', 'pct', 'rank') else ''
        sort = f' data-sort="{key}"' if sortable else ''
        if key == 'cy_dirty':
            aria, arrow = ' aria-sort="descending"', ' ▼'
        elif sortable:
            aria, arrow = ' aria-sort="none"', ''
        else:
            aria, arrow = '', ''
        cells.append(f'<th{cls}{sort}{aria}>{esc_html(label)}{arrow}</th>')
    return '<tr>' + ''.join(cells) + '</tr>'


def table_row(person):
    """One row in the default view."""
    cells = []
    for key, _label, kind in CORE_COLS:
        cls = (
            ' class="name"'
            if kind == 'name'
            else ' class="num"'
            if kind in ('money', 'pct', 'rank')
            else ''
        )
        cells.append(f'<td{cls}>{table_cell(person, key, kind)}</td>')
    return f'<tr data-key="{esc_html(person["person_key"])}">' + ''.join(cells) + '</tr>'


def table_rows(dataset):
    """Every person, in the default sort: dirtiest latest first, unknowns last."""

    def sort_key(person):
        dirty = latest(person)['dirty']
        if dirty is None:
            return (1, 0, person['full_name'].casefold())
        return (0, -dirty, person['full_name'].casefold())

    return sorted(dataset, key=sort_key)


def render_table_slots(html, dataset):
    """Fill the main table's head and body with the default view."""
    rows = table_rows(dataset)
    html = html.replace('%%MAIN_THEAD%%', table_thead())
    return html.replace('%%MAIN_TBODY%%', ''.join(table_row(p) for p in rows))


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
    data_as_of = sorted({r.get('data_as_of', '') for r in dataset})
    # Visible data-as-of stamp (header). Coverage end dates come from
    # config.yaml verification.coverage_end — never hardcoded here.
    # The build time reuses the exact "Generated <ts>" string the footer
    # uses, so the verifier's strip_ts regex normalizes both occurrences
    # and the generator stays deterministic apart from that timestamp.
    coverage = asdict(settings().verification.coverage_end)

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
        f'{settings().cycles.current} is partial. Generated {generated_at}.'
    )
    # Front-door freshness line: one line, from the same config dates —
    # the latest coverage end across families, never a typed date.
    fresh_line = (
        'Data through '
        f'{fmt_cov(max(coverage.values()))}'
        f' \u2014 {settings().cycles.current} is partial. Full coverage dates in the methodology.'
    )
    html = page_template()
    html = html.replace('%%METHOD_HTML%%', clean_method_html(dataset))
    html = render_story_slots(html, dataset)
    html = render_table_slots(html, dataset)
    for token, value in cycle_tokens().items():
        html = html.replace(token, value)
    html = html.replace('%%COLS_JSON%%', safe_json(cols_payload))
    html = html.replace('%%DATA_JSON%%', safe_json(rows))
    html = html.replace('%%OPP_JSON%%', safe_json(opp_payload))
    html = html.replace(
        '%%US_STATES_JSON%%', settings().paths.us_states_geometry.read_text().strip()
    )
    html = html.replace(
        '%%US_DISTRICTS_JSON%%', settings().paths.us_districts_geometry.read_text().strip()
    )
    html = html.replace('%%DATASET_MD5%%', dataset_md5)
    html = html.replace('%%DATA_AS_OF%%', ', '.join(data_as_of))
    html = html.replace('%%STAMP%%', stamp)
    html = html.replace('%%COV_PAS2%%', fmt_cov(coverage['committee_money_pas2']))
    html = html.replace('%%COV_WEBALL%%', fmt_cov(coverage['weball']))
    html = html.replace('%%COV_IE%%', fmt_cov(coverage['independent_expenditures']))
    html = html.replace('%%FRESH_LINE%%', fresh_line)
    html = html.replace('%%GENERATED_AT%%', generated_at)
    settings().paths.site.mkdir(parents=True, exist_ok=True)
    out = settings().paths.site / 'index.html'
    out.write_text(html, encoding='utf-8')
    log.info(f'rows: {len(rows)}')
    log.info(f'dataset md5: {dataset_md5}')
    log.info(f'embedded payload bytes: {len(safe_json(rows))}')
    log.info(
        f'opposition detail: {len(opp_payload)} persons, '
        f'{sum(len(v) for v in opp_payload.values())} race-phases'
    )
    log.info(f'wrote {out} ({out.stat().st_size} bytes)')


if __name__ == '__main__':
    run(main)
