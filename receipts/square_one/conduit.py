"""Conduit (earmarked) money: the FEC API Schedule B merge, validated on evidence.

The bulk pas2 files miss most conduit money: a conduit's earmarks reach a
candidate through the conduit's Schedule B, and pas2 only carries the
conduit's own 24K/24P rows. The merge pulls each listed committee's full
Schedule B from the FEC API, keeps line 23 only, dedups on sub_id against
pas2, classifies each disbursement as earmark or own money by the
committee's own signal, and attributes by recipient committee, never by
candidate ID (many conduit rows carry no candidate ID at all).

Two evidence layers validate this module without a live pull:
row-level Schedule B pulls for the five pilot committees
(`data/evidence/square-one/`), and per-recipient aggregates for all 62
listed committees (`data/evidence/jfc-variants/`), classified into
direct / joint-fundraising / other by the recipient's committee-master
designation. The full roster-wide API pull needs the registered
FEC_API_KEY and is a December run; see `fetch_schedule_b`.
"""

import difflib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from receipts.square_one import ie as ie_module
from receipts.square_one import parsers

API_BASE = 'https://api.open.fec.gov/v1'
SCHEDULE_B_PAGE = 100

# Proven renames (the '(FORMERLY ...)' by_recipient rows prove these are the
# same committees): Biden Victory Fund -> Harris Victory Fund (J); Biden
# for President -> Harris for President (P); Biden Action Fund -> Harris
# Action Fund (J). All presidential, non-roster.
ALIASES: dict[str, tuple[str, dict]] = {
    'BIDENVICTORYFUND': (
        'jfc',
        {'cm_id': 'C00744946', 'cm_name': 'HARRIS VICTORY FUND (formerly Biden Victory Fund)'},
    ),
    'BIDENFORPRESIDENT': (
        'direct',
        {
            'cm_id': None,
            'cm_name': 'HARRIS FOR PRESIDENT (formerly Biden for President)',
            'cands': [],
        },
    ),
    'BIDENACTIONFUND': (
        'jfc',
        {'cm_id': None, 'cm_name': 'HARRIS ACTION FUND (formerly Biden Action Fund)'},
    ),
}

JFC_PAT = re.compile(
    r'VICTORY FUND|MAJORITY FUND|BATTLEGROUND|LEADERSHIP FUND|JOINT FUNDRAIS|VICTORY COMMITTEE',
    re.I,
)


def norm_name(name: str) -> str:
    """Recipient names, comparable across sources: alphanumerics only, upper."""
    return re.sub(r'[^A-Z0-9]', '', (name or '').upper())


def load_cm_maps(bulk_dir: Path, cycle: int) -> tuple[dict, dict]:
    """(last-wins name map, multi map) from the cycle's committee master."""
    single: dict[str, tuple] = {}
    multi: dict[str, list] = defaultdict(list)
    for row in parsers.committee_rows(bulk_dir, cycle):
        entry = (row.committee_id, row.designation, row.candidate_id, row.name.strip())
        single[norm_name(row.name)] = entry
        multi[norm_name(row.name)].append(entry)
    return single, dict(multi)


def build_pas2_name_map(bulk_dir: Path, cycles: list[int]) -> dict[str, set]:
    """Candidate-committee name -> candidate IDs, from pas2 24K/24P rows.

    Only rows whose recipient committee (OTHER_ID) is principal/authorized
    count: that is the soundness filter the JFC pilot used — it trusts a
    name->candidate link only when the money went to a candidate's own
    committee.
    """
    designation: dict[str, str] = {}
    for cycle in cycles:
        for row in parsers.committee_rows(bulk_dir, cycle):
            designation.setdefault(row.committee_id, row.designation)
    name_to_cands: dict[str, set] = defaultdict(set)
    for cycle in cycles:
        for row in parsers.pas2_rows(bulk_dir, cycle):
            if row.transaction_type not in ('24K', '24P'):
                continue
            if designation.get(row.other_id) in ('P', 'A') and row.candidate_id:
                name_to_cands[norm_name(row.recipient_name)].add(row.candidate_id)
    return dict(name_to_cands)


def _prefix(table: dict, key: str, minlen: int = 15):
    """The single long name sharing a 15-char prefix, or 'AMBIGUOUS'/None."""
    if len(key) < minlen:
        return None
    hits = [
        v for k, v in table.items() if (k.startswith(key) or key.startswith(k)) and len(k) >= minlen
    ]
    uniq = []
    for hit in hits:
        if hit not in uniq:
            uniq.append(hit)
    return uniq[0] if len(uniq) == 1 else ('AMBIGUOUS' if len(uniq) > 1 else None)


def _fuzzy(table: dict, key: str, thresh: float = 0.88):
    """Best difflib match among names sharing the first 6 chars, else None."""
    short = [k for k in table if k[:6] == key[:6]]
    if not short:
        return None
    best = difflib.get_close_matches(key, short, n=1, cutoff=thresh)
    return table[best[0]] if best else None


def _cm_lookup(cycle: int, key: str, cm_by_cycle: dict[int, dict]):
    """Committee-master hit for a name, this cycle first, then other cycles."""
    hit = cm_by_cycle[cycle].get(key) or _prefix(cm_by_cycle[cycle], key)
    if hit == 'AMBIGUOUS':
        hit = None
    if not hit:
        hit = _fuzzy(cm_by_cycle[cycle], key)
    if hit:
        return hit
    # Terminated committees vanish from the current cycle's master.
    for other_cycle in (2024, 2022, 2026):
        if other_cycle == cycle:
            continue
        hit = cm_by_cycle[other_cycle].get(key) or _prefix(cm_by_cycle[other_cycle], key)
        if hit and hit != 'AMBIGUOUS':
            return hit
    return None


def _cm_verdict(hit, cycle: int, key: str, cm_multi_by_cycle: dict[int, dict]):
    """Designation decides: J -> joint fundraising committee, P/A -> direct."""
    cands_multi = {cand for _, _, cand, _ in cm_multi_by_cycle[cycle].get(key, []) if cand}
    if len(cands_multi) > 1:
        return 'ambiguous', {
            'candidates': sorted(cands_multi),
            'cmtes': sorted({c for c, _, _, _ in cm_multi_by_cycle[cycle].get(key, [])}),
        }
    cm_id, designation, cand_id, legal = hit
    if designation == 'J':
        return 'jfc', {'cm_id': cm_id, 'cm_name': legal}
    if designation in ('P', 'A'):
        return 'direct', {
            'cm_id': cm_id,
            'cm_name': legal,
            'cands': sorted({cand_id}) if cand_id else [],
        }
    return 'other', {'cm_id': cm_id, 'dsgn': designation, 'cm_name': legal}


def _pas2_fallback(
    key: str,
    recipient_name: str,
    pas2_name_map: dict[str, set],
    cand_to_person: dict[str, str],
    person_surname: dict[str, str],
):
    """Committee-master miss only: pas2-name fallback, surname-token rule."""
    cands = pas2_name_map.get(key)
    if not cands:
        cands = _prefix(pas2_name_map, key)
        if cands == 'AMBIGUOUS':
            cands = None
    if not cands:
        cands = _fuzzy(pas2_name_map, key)
    if not cands:
        return None
    persons = {cand_to_person[c] for c in cands if c in cand_to_person}
    tokens = set(re.sub(r'[^A-Z ]', '', recipient_name.upper()).split())
    kept = {pk for pk in persons if person_surname.get(pk, '') in tokens}
    if kept:
        return 'direct', {
            'cm_id': None,
            'cm_name': None,
            'cands': sorted(kept),
            'via': 'pas2-fallback',
        }
    return 'unmatched', {'note': 'pas2-name hit but no roster surname token'}


def classify_recipient(
    cycle: int,
    recipient_name: str,
    cm_by_cycle: dict[int, dict],
    cm_multi_by_cycle: dict[int, dict],
    pas2_name_map: dict[str, set],
    cand_to_person: dict[str, str],
    person_surname: dict[str, str],
) -> tuple[str, dict]:
    """(kind, detail) for one by_recipient row; kind in direct|jfc|other|ambiguous|unmatched|jfc?.

    Designation decides: J -> joint fundraising committee, P/A -> direct
    to the candidate's own committee, anything else -> other. A name
    shared by two committees with different candidate IDs is ambiguous
    and must be resolved from raw Schedule B, never guessed.
    """
    key = norm_name(recipient_name)
    if key in ALIASES:
        return ALIASES[key]
    hit = _cm_lookup(cycle, key, cm_by_cycle)
    if hit:
        return _cm_verdict(hit, cycle, key, cm_multi_by_cycle)
    fallback = _pas2_fallback(key, recipient_name, pas2_name_map, cand_to_person, person_surname)
    if fallback:
        return fallback
    if JFC_PAT.search(recipient_name):
        return 'jfc?', {'cm_id': None, 'note': 'name pattern only, no cm/pas2 match'}
    return 'unmatched', {}


def is_earmark(memo_text: str, memo_code: str | None, disbursement_description: str) -> bool:
    """Whether a Schedule B row is a transmitted earmark, by any committee's signal.

    AIPAC/JStreet write it in the memo text, JACPAC in memo_code 'X',
    NORPAC in the disbursement description. Negative rows are voids of
    earmarks, still earmarks — the caller excludes them from totals.
    """
    memo = (memo_text or '').upper()
    if 'EARMARK' in memo or memo.startswith('ERMK:'):
        return True
    if (memo_code or '').upper() == 'X':
        return True
    desc = (disbursement_description or '').upper()
    return bool(desc.startswith('EARMARK') or 'CONDUIT' in desc)


def summarize_schedule_b(rows: list[dict]) -> dict:
    """Line-23 totals for a committee's Schedule B rows, in cents."""
    total = earmark_gross = earmark_voids = own_money = 0
    line23 = 0
    for row in rows:
        if str(row.get('line_number')) != '23':
            continue
        line23 += 1
        cents = round(float(row.get('disbursement_amount') or 0) * 100)
        total += cents
        if is_earmark(
            row.get('memo_text') or '',
            row.get('memo_code'),
            row.get('disbursement_description') or '',
        ):
            if cents < 0:
                earmark_voids += cents
            else:
                earmark_gross += cents
        else:
            own_money += cents
    return {
        'line23_rows': line23,
        'total_cents': total,
        'earmark_gross_cents': earmark_gross,
        'earmark_void_cents': earmark_voids,
        'earmark_net_cents': earmark_gross + earmark_voids,
        'own_money_cents': own_money,
    }


def fetch_schedule_b(
    committee_id: str,
    cycle: int,
    api_key: str,
    per_page: int = SCHEDULE_B_PAGE,
) -> list[dict]:
    """Every Schedule B row for one committee and cycle, cursor-paginated.

    No server-side filters: the API silently ignores transaction-type
    filters and 504s on line_number filters, so the pull is unfiltered
    and the caller filters line 23 client-side. DEMO_KEY is refused
    here — a roster-wide pull is thousands of calls and the repo rule
    reserves that scale for the registered key.
    """
    if not api_key or api_key == 'DEMO_KEY':
        raise ValueError('fetch_schedule_b needs the registered FEC_API_KEY, not DEMO_KEY')
    rows: list[dict] = []
    params = {
        'api_key': api_key,
        'committee_id': committee_id,
        'two_year_transaction_period': cycle,
        'per_page': per_page,
    }
    while True:
        url = API_BASE + '/schedules/schedule_b/?' + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                page = json.loads(response.read())
        except urllib.error.HTTPError as err:
            raise RuntimeError(
                f'Schedule B pull failed for {committee_id} {cycle}: HTTP {err.code}'
            ) from err
        rows.extend(page.get('results', []))
        indexes = page.get('pagination', {}).get('last_indexes') or {}
        if not indexes.get('last_index'):
            break
        params['last_index'] = indexes['last_index']
        params['last_disbursement_date'] = indexes.get('last_disbursement_date')
    return rows


def load_by_recipient(evidence_dir: Path, committee_id: str, cycle: int) -> list[dict] | None:
    """One committee-cycle aggregate file: per-recipient totals, or None when absent.

    2022 evidence covers AIPAC plus the eight main conduits only; a missing
    file is a coverage gap, not an error.
    """
    path = evidence_dir / f'by_recipient_{committee_id}_{cycle}.json'
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)['results']


def direct_from_by_recipient(
    evidence_dir: Path,
    committees: list[str],
    cycles: list[int],
    cm_by_cycle: dict[int, dict],
    cm_multi_by_cycle: dict[int, dict],
    pas2_name_map: dict[str, set],
    cand_to_person: dict[str, str],
    person_surname: dict[str, str],
    resolutions: dict | None = None,
) -> tuple[dict, dict]:
    """Direct money per (person_key, committee, cycle) from by_recipient evidence.

    Returns (direct cents keyed (person_key, committee, cycle), report)
    where report counts kinds and lists ambiguous/unmatched rows with
    their dollars. Ambiguous names are resolved from the raw Schedule B
    splits in `resolutions`, keyed `committee|cycle|NORMNAME`.
    """
    direct: dict[tuple, int] = defaultdict(int)
    report: dict[str, Any] = {
        'rows': 0,
        'direct_rows': 0,
        'jfc_rows': 0,
        'other_rows': 0,
        'ambiguous_rows': 0,
        'unmatched_rows': 0,
        'jfc_unknown_rows': 0,
        'direct_cents': 0,
        'jfc_cents': 0,
        'other_cents': 0,
        'ambiguous_cents': 0,
        'unmatched_cents': 0,
        'unmatched': [],
        'ambiguous': [],
        'missing_files': [],
        'resolved_keys': set(),
    }
    resolutions = resolutions or {}
    roster_keys = set(cand_to_person.values())
    for committee in committees:
        for cycle in cycles:
            rows = load_by_recipient(evidence_dir, committee, cycle)
            if rows is None:
                report['missing_files'].append((committee, cycle))
                continue
            for row in rows:
                cents = round(float(row.get('total') or 0) * 100)
                report['rows'] += 1
                kind, detail = classify_recipient(
                    cycle,
                    row['recipient_name'],
                    cm_by_cycle,
                    cm_multi_by_cycle,
                    pas2_name_map,
                    cand_to_person,
                    person_surname,
                )
                if kind == 'direct':
                    report['direct_rows'] += 1
                    report['direct_cents'] += cents
                    for cand in detail['cands']:
                        # A 'cand' is a candidate ID, except from the
                        # pas2-name fallback, which returns person keys.
                        person = cand_to_person.get(cand, cand)
                        if person in roster_keys:
                            direct[(person, committee, cycle)] += cents
                elif kind == 'jfc':
                    report['jfc_rows'] += 1
                    report['jfc_cents'] += cents
                elif kind == 'other':
                    report['other_rows'] += 1
                    report['other_cents'] += cents
                elif kind == 'ambiguous':
                    report['ambiguous_rows'] += 1
                    report['ambiguous_cents'] += cents
                    key = f'{committee}|{cycle}|{norm_name(row["recipient_name"])}'
                    resolution = resolutions.get(key)
                    if resolution:
                        report['resolved_keys'].add(key)
                        # The raw Schedule B splits include memo rows; the
                        # by_recipient total excludes them. Cap each split
                        # at the by_recipient total so only non-memo money
                        # lands in direct (the excess is the memo layer).
                        byrec_cents = round(float(resolution['by_recipient_total']) * 100)
                        split_sum = sum(
                            round(float(s['total']) * 100) for s in resolution['splits'].values()
                        )
                        if split_sum > byrec_cents:
                            report['resolution_memo_excess_cents'] = report.get(
                                'resolution_memo_excess_cents', 0
                            ) + (split_sum - byrec_cents)
                        for _cm_id, split in resolution['splits'].items():
                            split_cents = min(round(float(split['total']) * 100), byrec_cents)
                            person = cand_to_person.get(split['cand_id'])
                            if person and split_cents:
                                direct[(person, committee, cycle)] += split_cents
                    else:
                        report['ambiguous'].append((committee, cycle, row['recipient_name'], cents))
                elif kind == 'jfc?':
                    report['jfc_unknown_rows'] += 1
                    report['jfc_cents'] += cents
                else:
                    report['unmatched_rows'] += 1
                    report['unmatched_cents'] += cents
                    report['unmatched'].append((committee, cycle, row['recipient_name'], cents))
    return dict(direct), report


def apply_collision_fixes(
    direct: dict, fixes: list[dict], resolved_keys: set | frozenset = frozenset()
) -> int:
    """Add the Schedule B-verified collision fixes to the direct totals.

    The fixes live in `data/evidence/square-one/collision_fixes.json`:
    amounts the last-wins classifier had put in the wrong candidate's
    bucket, verified recipient-committee by recipient-committee from raw
    Schedule B. A fix whose row already has a resolution applied (same
    committee, cycle and recipient name) is skipped — the resolution
    already moved that money. Returns the total cents moved by fixes
    actually applied.
    """
    moved = 0
    for fix in fixes:
        key = f'{fix["committee"]}|{int(fix["cycle"])}|{fix["name"]}'
        if key in resolved_keys:
            continue
        cents = round(float(fix['amount']) * 100)
        direct[(fix['person_key'], fix['committee'], int(fix['cycle']))] = (
            direct.get((fix['person_key'], fix['committee'], int(fix['cycle'])), 0) + cents
        )
        moved += cents
    return moved


def listed_committees(pro_israel_csv: Path) -> list[str]:
    """The 62 listed committees: the pro-Israel list plus AIPAC itself."""
    import csv

    with open(pro_israel_csv, newline='') as f:
        committees = {
            row['committee_id']
            for row in csv.DictReader(f)
            if row['committee_id'] and not row['committee_id'].startswith('C900')
        }
    committees.add('C00797670')
    return sorted(committees)


def person_surnames(people: list[dict]) -> dict[str, str]:
    """person_key -> upper surname, for the pas2-name fallback's token rule."""
    return {p['person_key']: ie_module.split_person_name(p['full_name'])[1].upper() for p in people}
