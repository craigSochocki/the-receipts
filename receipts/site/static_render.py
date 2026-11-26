"""The build-time static renders: the story step texts and the main table.

Computed here from the dataset exactly as the page's scripts compute
them in the browser, so the static page is the no-JS fallback. The
script re-renders on preset, cycle, or filter change.
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from receipts.common.settings import settings
from receipts.domain.clean_2026 import is_not_dirty
from receipts.domain.targets import primary_targets
from receipts.site.expectations import dollars, latest

TEMPLATES = Path(__file__).parent / 'templates'


def _template(name):
    return (TEMPLATES / name).read_text(encoding='utf-8')


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
    match = re.search(r'const STORY_STEPS = \[([^\]]+)\]', _template('story.js'))
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
