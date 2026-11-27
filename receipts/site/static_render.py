"""The build-time static renders: the story step texts and the main table.

Computed here from the dataset exactly as the page's scripts compute
them in the browser, so the static page is the no-JS fallback. The
script re-renders on preset, cycle, or filter change.
"""

import json
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from receipts.common.settings import settings
from receipts.domain.targets import primary_targets
from receipts.site.expectations import latest
from receipts.site.story_data import build_story_data, round_money

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


def party_of(person):
    return person['party_120'] or person['party_119'] or '—'


def story_data(dataset):
    """The Story aggregates, from the dataset and the configured cycles."""
    cycles = settings().cycles
    return build_story_data(dataset, cycles.current, cycles.next)


def story_steps():
    """The step names, read from story.js so the renderer follows it."""
    match = re.search(r'const STORY_STEPS = \[([^\]]+)\]', _template('story.js'))
    if not match:
        raise SystemExit('story.js has no STORY_STEPS list')
    return re.findall(r"'(\w+)'", match.group(1))


def incoming_members(dataset):
    """The members of the incoming Congress."""
    return [r for r in dataset if r['in_120th'] == 'yes']


def _party_counts(counts):
    """'261 Democrats, 173 Republicans' from one waffle panel's counts."""
    parts = []
    if counts['dem']:
        parts.append(f'{counts["dem"]} Democrats')
    if counts['rep']:
        parts.append(f'{counts["rep"]} Republicans')
    if counts['ind']:
        parts.append(f'{counts["ind"]} independents')
    if counts['other']:
        parts.append(f'{counts["other"]} others')
    return ', '.join(parts)


def story_texts(dataset):
    """Every step card's text, computed from the dataset.

    The browser script renders the same strings from the same
    aggregates (story.js storyStepText), so the static cards and the
    live story can never disagree about a number.
    """
    data = story_data(dataset)
    house = data['waffle']['house']
    senate = data['waffle']['senate']
    member = data['member']
    zoom = member['zoom']
    ratio = zoom['member_dirty'] / zoom['top'][0]['dirty']
    tiers = Counter(d['tier'] for d in data['map']['districts'])
    targets_total = len(
        primary_targets(incoming_members(dataset), 'balanced', settings().cycles.next)
    )
    stacked = data['stacked']
    preset = settings().verification.tolerance_presets['balanced']
    return {
        'waffle_all': (
            f'These are the <b>{data["meta"]["incoming_total"]}</b> seats of the incoming '
            '120th Congress — '
            f'<b>{house["seats"]}</b> in the House, <b>{senate["seats"]}</b> in the Senate. '
            'Each dot is one seat.'
        ),
        'waffle_party': (
            'First, the party split — Democrats in one block, Republicans in one block, '
            f'in each chamber. House: <b>{_party_counts(house["counts"])}</b>. '
            f'Senate: <b>{_party_counts(senate["counts"])}</b>.'
        ),
        'waffle_flag': (
            'Now who the rules flag — any AIPAC direct dollar or UDP benefit dollar '
            f'since their last election. House: <b>{house["counts"]["flagged"]} of '
            f'{house["seats"]}</b> seats. Senate: <b>{senate["counts"]["flagged"]} of '
            f"{senate['seats']}</b>. Flagged members sit at the head of their party's "
            "block, in the lighter tint of their own party's colour. Under the Balanced "
            f'tolerance ({esc_html(preset_short(preset))}), '
            f'<b>{data["counts"]["balanced_dirty"]}</b> of the incoming '
            f'{data["meta"]["incoming_total"]} count as dirty. '
            '<a href="methodology/">How we flagged members</a>.'
        ),
        'ranked': (
            'Who takes the most — in each chamber. House: '
            f'<b>{esc_html(data["ranked"]["house"][0]["name"])}</b>, '
            f'<b>{data["ranked"]["house"][0]["rounded"]}</b>. Senate: '
            f'<b>{esc_html(data["ranked"]["senate"][0]["name"])}</b>, '
            f'<b>{data["ranked"]["senate"][0]["rounded"]}</b>. '
            'Dirty money since their last election, ranked within each chamber.'
        ),
        'stacked_aipac': (
            'Where the money comes from. Start with the AIPAC PAC: '
            f'<b>{round_money(stacked["house"]["aipac"])}</b> to House campaigns since '
            f'their last election, <b>{round_money(stacked["senate"]["aipac"])}</b> to '
            'Senate campaigns — direct contributions, earmarked checks included.'
        ),
        'stacked_corp': (
            'Add corporate PACs: '
            f'<b>{round_money(stacked["house"]["corp"])}</b> in the House, '
            f'<b>{round_money(stacked["senate"]["corp"])}</b> in the Senate. Together '
            'with AIPAC, that is '
            f'<b>{round_money(stacked["house"]["aipac"] + stacked["house"]["corp"])}</b> '
            f'House and <b>{round_money(stacked["senate"]["aipac"] + stacked["senate"]["corp"])}</b> '
            'Senate from PACs.'
        ),
        'stacked_individual': (
            'And individuals — the rest, and most of it: '
            f'<b>{round_money(stacked["house"]["individual"])}</b> House, '
            f'<b>{round_money(stacked["senate"]["individual"])}</b> Senate. Individual '
            'contributions are not dirty money. Total accepted since their last '
            f'election: <b>{round_money(stacked["house"]["total"])}</b> House, '
            f'<b>{round_money(stacked["senate"]["total"])}</b> Senate.'
        ),
        'rest': 'The money is real. The question is what it buys.',
        'member': (
            f'<b>{esc_html(member["name"])}</b> took '
            f'<b>{member["split"]["rounded"]["dirty"]}</b> in dirty money in '
            f'{member["trend"][-1]["cycle"]} — the most of anyone in the dataset — '
            'almost all of it UDP benefit: '
            f'<b>{member["split"]["rounded"]["udp_benefit"]}</b> spent for her Senate '
            f'race, against <b>{member["split"]["rounded"]["individual"]}</b> raised '
            'from individuals. She is not returning to Congress.'
        ),
        'member_trend': (
            'It was not always like this. Her dirty money by election: '
            + ', '.join(f'<b>{t["rounded"]}</b> in {t["cycle"]}' for t in member['trend'])
            + ', when she ran for the Senate.'
        ),
        'member_zoom': (
            'Zoom back out, to the Senate she ran for. The incoming senator who took '
            f'the most dirty money, <b>{esc_html(zoom["top"][0]["name"])}</b>, took '
            f'<b>{zoom["top"][0]["rounded"]}</b> — Stevens took more than '
            f'<b>{int(ratio)} times</b> that. The Senate median is '
            f'<b>{zoom["median_rounded"]}</b>.'
        ),
        'map': (
            'Geography. Each district is coloured by its member’s verdict — '
            f'<b>{tiers["dirty"]}</b> dirty, <b>{tiers["below_threshold"]}</b> below '
            f'threshold, <b>{tiers["clean"]}</b> clean, '
            f'<b>{tiers[None]}</b> not judged under the Balanced rule — never '
            'by raw dollars. Find your district below, and see your member’s money.'
        ),
        'targets': (
            f"What's next: <b>{targets_total}</b> incoming members whose seat is on the "
            f'ballot in {data["meta"]["next_cycle"]} and who took dirty money. The top '
            f'eight are listed — <b>{esc_html(data["targets"][0]["name"])}</b> first, '
            f'at <b>{data["targets"][0]["rounded"]}</b>.'
        ),
    }


# ---- server-rendered story figures (the no-JS fallback) ----
# The static page is the story's final frame: the waffle shows the
# party split with the flag overlay, the stacked bars show all three
# sources, the map is fully coloured. The script only rewinds those
# pictures to earlier steps as the reader scrolls.


def waffle_dots(panel):
    """One <i> per plotted seat, in layout order, plus placeholders."""
    dots = []
    for m in panel['members']:
        cls = m['party'].lower() + (' flagged' if m['flagged'] else '')
        if m['uncalled']:
            cls += ' uncalled'
        dots.append(f'<i class="{cls}" title="{esc_html(m["name"])}"></i>')
    for _ in range(panel['seats'] - panel['named']):
        dots.append('<i class="open" title="Seat uncalled — no member named yet"></i>')
    return ''.join(dots)


def ranked_html(entries, lead=None):
    """One ranked-bar row per entry; the lead row is the Beat 4 subject."""
    rows = []
    if lead is not None:
        rows.append(
            '<div class="rank-row lead"><span class="rank-name">'
            f'<a href="explore/?member={esc_html(lead["key"])}">'
            f'{esc_html(lead["name"])}</a> '
            '<span class="rank-note">not returning</span></span>'
            f'<span class="rank-bar"><span class="rank-fill lead" style="width:100%"></span></span>'
            f'<span class="rank-amt">{lead["rounded"]}</span></div>'
        )
    top = max(
        [e['dirty'] for e in entries] + [lead['dirty']] if lead else [e['dirty'] for e in entries]
    )
    for entry in entries:
        width = 100 * entry['dirty'] / top if top else 0
        rows.append(
            '<div class="rank-row"><span class="rank-name">'
            f'<span class="pdot {entry["party"].lower()}">{entry["party"]}</span> '
            f'<a href="explore/?member={esc_html(entry["key"])}">'
            f'{esc_html(entry["name"])}</a> '
            f'<span class="rank-seat">{esc_html(entry["seat"])}</span></span>'
            f'<span class="rank-bar"><span class="rank-fill" style="width:{width:.1f}%"></span></span>'
            f'<span class="rank-amt">{entry["rounded"]}</span></div>'
        )
    return ''.join(rows)


def stacked_html(stacked):
    """One stacked bar: AIPAC, then corporate PACs, then individuals."""
    parts = [
        ('aipac', 'AIPAC PAC direct'),
        ('corp', 'Corporate PACs'),
        ('individual', 'Individuals'),
    ]
    segments = []
    legend = []
    for key, label in parts:
        share = stacked['shares'][key] or 0
        segments.append(
            f'<span class="seg seg-{key}" style="width:{100 * share:.1f}%">'
            f'<span class="seg-label">{label} · {round_money(stacked[key])}</span></span>'
        )
        legend.append(
            f'<li><span class="swatch seg-{key}"></span>{label} — '
            f'<b>{round_money(stacked[key])}</b> ({share:.0%})</li>'
        )
    return (
        '<div class="stacked" data-state="3">'
        + ''.join(segments)
        + '</div><ul class="stack-legend">'
        + ''.join(legend)
        + f'<li>Total accepted — <b>{round_money(stacked["total"])}</b></li></ul>'
    )


def member_split_html(member):
    """Beat 4's split: the dirty money's three parts, plus individuals."""
    split = member['split']
    dirty = split['dirty']
    parts = [
        ('udp_benefit', 'UDP benefit'),
        ('aipac_direct', 'AIPAC PAC direct'),
        ('corp', 'Corporate PACs'),
    ]
    segments = []
    legend = []
    for key, label in parts:
        share = split[key] / dirty if dirty else 0
        segments.append(
            f'<span class="seg seg-{key}" style="width:{100 * share:.1f}%">'
            f'<span class="seg-label">{label} · {split["rounded"][key]}</span></span>'
        )
        legend.append(
            f'<li><span class="swatch seg-{key}"></span>{label} — '
            f'<b>{split["rounded"][key]}</b> ({share:.0%})</li>'
        )
    return (
        '<div class="stacked" data-state="3">'
        + ''.join(segments)
        + '</div><ul class="stack-legend">'
        + ''.join(legend)
        + f'<li>Dirty money — <b>{split["rounded"]["dirty"]}</b></li>'
        f'<li>Individuals, for scale — <b>{split["rounded"]["individual"]}</b> '
        '(not dirty money)</li></ul>'
    )


def member_trend_html(member):
    """Beat 4's trend: one column per election the member was up for."""
    top = max(t['dirty'] for t in member['trend'])
    cols = []
    for t in member['trend']:
        height = 100 * t['dirty'] / top if top else 0
        cols.append(
            '<div class="trend-col">'
            f'<span class="trend-amt">{t["rounded"]}</span>'
            f'<span class="trend-bar" style="height:{height:.1f}%"></span>'
            f'<span class="trend-cycle">{t["cycle"]}</span></div>'
        )
    return '<div class="trend">' + ''.join(cols) + '</div>'


TIER_LABELS = {
    'dirty': 'Dirty',
    'below_threshold': 'Below threshold',
    'clean': 'Clean',
    None: 'Not judged',
}


def district_map_svg(dataset):
    """The district map, coloured by verdict — never by raw dollars."""
    geometry = json.loads(settings().paths.us_districts_geometry.read_text())
    states = json.loads(settings().paths.us_states_geometry.read_text())
    data = story_data(dataset)
    member = {d['key']: d for d in data['map']['districts']}
    paths = []
    for key in sorted(geometry):
        d = member.get(key)
        if d is None:
            paths.append(
                f'<path class="map-open" d="{geometry[key]["d"]}">'
                f'<title>{esc_html(key)} · no member named</title></path>'
            )
            continue
        tier = d['tier'] or 'unjudged'
        paths.append(
            f'<path class="map-{tier}-{d["party"]}" d="{geometry[key]["d"]}" '
            f'data-key="{esc_html(d["member_key"])}">'
            f'<title>{esc_html(key)} · {esc_html(d["name"])} — '
            f'{TIER_LABELS[d["tier"]]}</title></path>'
        )
    outlines = ''.join(f'<path d="{states[state]["d"]}"/>' for state in sorted(states))
    return (
        '<svg class="district-map" viewBox="0 0 975 610" role="img" '
        'aria-label="House districts coloured by their member’s verdict">'
        '<g class="districts">'
        + ''.join(paths)
        + '</g><g class="state-lines">'
        + outlines
        + '</g></svg>'
    )


def targets_html(targets):
    """The 2028 targets as a short ranked list, one number each."""
    rows = []
    for i, t in enumerate(targets, 1):
        rows.append(
            '<li><span class="target-rank">'
            f'{i}</span>'
            f'<span class="pdot {t["party"].lower()}">{t["party"]}</span> '
            f'<a href="explore/?member={esc_html(t["key"])}">'
            f'{esc_html(t["name"])}</a> '
            f'<span class="target-seat">{esc_html(t["seat"])} · {esc_html(t["chamber"])}</span>'
            f'<span class="target-amt">{t["rounded"]}</span></li>'
        )
    return '<ol class="target-list">' + ''.join(rows) + '</ol>'


def story_slots(dataset):
    """Every %%STORY_*%% slot the Story template carries."""
    data = story_data(dataset)
    member = data['member']
    return {
        '%%HERO_NUMBER%%': data['hero']['dirty_total_rounded'],
        '%%HERO_FLAGGED%%': (
            f'{data["hero"]["flagged"]} of the {data["hero"]["members"]} incoming members '
            'are flagged — any AIPAC direct dollar or UDP benefit dollar since '
            'their last election.'
        ),
        '%%STORY_WAFFLE_HOUSE%%': waffle_dots(data['waffle']['house']),
        '%%STORY_WAFFLE_SENATE%%': waffle_dots(data['waffle']['senate']),
        '%%STORY_DELEGATES%%': (
            'The six non-voting delegates are not plotted — they have no vote: '
            + ', '.join(esc_html(name) for name in data['waffle']['house']['delegates'])
            + '.'
        ),
        '%%STORY_RANKED_HOUSE%%': ranked_html(data['ranked']['house']),
        '%%STORY_RANKED_SENATE%%': ranked_html(data['ranked']['senate']),
        '%%STORY_STACKED_HOUSE%%': stacked_html(data['stacked']['house']),
        '%%STORY_STACKED_SENATE%%': stacked_html(data['stacked']['senate']),
        '%%STORY_MEMBER_SPLIT%%': member_split_html(member),
        '%%STORY_MEMBER_TREND%%': member_trend_html(member),
        '%%STORY_MEMBER_ZOOM%%': ranked_html(
            member['zoom']['top'],
            lead={
                'key': member['key'],
                'name': member['name'],
                'dirty': member['zoom']['member_dirty'],
                'rounded': member['zoom']['member_rounded'],
            },
        ),
        '%%STORY_MAP%%': district_map_svg(dataset),
        '%%STORY_TARGETS%%': targets_html(data['targets']),
    }


def render_story_slots(html, dataset):
    """Fill each story slot with its computed text or figure."""
    texts = story_texts(dataset)
    for step in story_steps():
        if step not in texts:
            raise SystemExit(f'no server-rendered text for story step: {step}')
        html = html.replace(f'%%STORY_{step.upper()}%%', texts[step])
    for token, value in story_slots(dataset).items():
        html = html.replace(token, value)
    left = sorted(set(re.findall(r'%%STORY_[A-Z_]+%%', html)))
    if left:
        raise SystemExit(f'unfilled story slots: {", ".join(left)}')
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
