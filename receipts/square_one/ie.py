"""All independent expenditures, UDP support, and opposition credits, re-derived.

Rules (methodology §3–§4, §13): the staged IE files hold bogus filings, so
a row counts only when its spender is a registered committee in the
same-cycle master and its candidate is identified (a roster ID or any
candidate with a weball summary). Re-filed rows dedup on (spender,
transaction ID), keeping the latest receipt date then the highest file
number. Opposition credit goes to the single candidate a spender backed
in one race-phase, minus spending against that candidate themselves.
Blank candidate IDs are resolved by name where the name allows.
"""

from collections import defaultdict
from pathlib import Path

from receipts.square_one import parsers

SUFFIXES = ('JR', 'SR', 'II', 'III', 'IV')


def split_person_name(full_name: str) -> tuple[str, str]:
    """(first, last) from a roster full name; suffixes dropped, last token wins."""
    parts = full_name.replace(',', '').split()
    while parts and parts[-1].rstrip('.').upper() in SUFFIXES:
        parts.pop()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return '', parts[0]
    return parts[0], parts[-1]


def _name_key(candidate_name: str, state: str, district: str, office: str) -> tuple:
    return candidate_name.upper(), state, district, office


def _last_and_first(candidate_name: str) -> tuple[str, str]:
    if ',' not in candidate_name:
        return candidate_name.strip().upper(), ''
    last, first = candidate_name.split(',')[:2]
    return last.strip().upper(), first.strip().upper()


def _represents(person: dict, district: str) -> bool:
    return any(
        str(person.get(seat) or '').zfill(2) == district
        for seat in ('district_119', 'district_120')
    )


def roster_matches(candidate_name: str, state: str, district: str, people: list[dict]):
    """Roster people whose last name, first-name start, state and district match."""
    last, first = _last_and_first(candidate_name)
    return [
        p
        for p in people
        if split_person_name(p['full_name'])[1].upper() == last
        and (not first or split_person_name(p['full_name'])[0].upper().startswith(first.split()[0]))
        and p['state'] == state
        and _represents(p, district)
    ]


class IeRow:
    """One counted-or-excluded expenditure row, in cents, with its race key."""

    __slots__ = (
        'spender_id',
        'candidate_id',
        'candidate_name',
        'cycle',
        'direction',
        'cents',
        'office',
        'state',
        'district',
        'election_type',
        'excluded_because',
        'resolved_via',
    )

    def __init__(self, row: parsers.IndependentExpenditure, excluded: str | None) -> None:
        self.spender_id = row.spe_id
        self.candidate_id = row.candidate_id
        self.candidate_name = row.cand_name.strip()
        self.cycle = row.cycle
        self.direction = row.direction
        self.cents = row.amount_cents
        self.office = row.can_office.strip()
        self.state = row.can_office_state.strip()
        self.district = row.can_office_dis.strip()
        self.election_type = row.ele_type.strip()
        self.excluded_because = excluded
        self.resolved_via: str | None = None

    @property
    def counted(self) -> bool:
        return self.excluded_because is None

    @property
    def race_key(self) -> tuple:
        return (self.cycle, self.office, self.state, self.district, self.election_type)


def _latest(rows: list) -> tuple[list, list]:
    """One row per (spender, transaction ID): latest receipt, then highest file number."""
    kept: dict[tuple, parsers.IndependentExpenditure] = {}
    dropped: list[parsers.IndependentExpenditure] = []
    for row in rows:
        prior = kept.get(row.identity)
        if prior is None:
            kept[row.identity] = row
        elif (row.received, row.file_number) > (prior.received, prior.file_number):
            dropped.append(prior)
            kept[row.identity] = row
        else:
            dropped.append(row)
    return list(kept.values()), dropped


def derive_ie(
    bulk_dir: Path, cycles: list[int], people: list[dict], weball: dict
) -> tuple[list[IeRow], dict]:
    """Counted IE rows for the staged cycles, plus exclusion stats."""
    roster_ids = {cid for p in people for cid in p['fec_candidate_ids']}
    identified = roster_ids | {cid for (cid, _cycle) in weball}
    rows: list[IeRow] = []
    stats = {
        'rows_read': 0,
        'dedup_dropped_rows': 0,
        'dedup_dropped_cents': 0,
        'unregistered_committee_rows': 0,
        'unregistered_committee_cents': 0,
        'blank_candidate_rows': 0,
        'blank_candidate_cents': 0,
        'candidate_not_identified_rows': 0,
        'candidate_not_identified_cents': 0,
    }
    for cycle in cycles:
        registered = {r.committee_id for r in parsers.committee_rows(bulk_dir, cycle)}
        filed = list(parsers.ie_rows(bulk_dir / 'ie', cycle))
        stats['rows_read'] += len(filed)
        kept, dropped = _latest(filed)
        stats['dedup_dropped_rows'] += len(dropped)
        stats['dedup_dropped_cents'] += sum(r.amount_cents for r in dropped)
        for row in kept:
            if row.spe_id not in registered:
                excluded = 'unregistered_committee'
                stats['unregistered_committee_rows'] += 1
                stats['unregistered_committee_cents'] += row.amount_cents
            elif not row.candidate_id:
                excluded = 'blank_candidate'
                stats['blank_candidate_rows'] += 1
                stats['blank_candidate_cents'] += row.amount_cents
            elif row.candidate_id not in identified:
                excluded = 'candidate_not_identified'
                stats['candidate_not_identified_rows'] += 1
                stats['candidate_not_identified_cents'] += row.amount_cents
            else:
                excluded = None
            rows.append(IeRow(row, excluded))
    return rows, stats


def resolve_blank_ids(rows: list[IeRow], people: list[dict]) -> tuple[int, list[IeRow]]:
    """Resolve blank candidate IDs by name where the name allows; returns unresolved rows."""
    index: dict[tuple, str] = {}
    for row in rows:
        if row.candidate_id:
            key = _name_key(row.candidate_name, row.state, row.district, row.office)
            index.setdefault(key, row.candidate_id)
    unresolved = []
    for row in rows:
        if row.candidate_id or row.excluded_because != 'blank_candidate':
            continue
        key = _name_key(row.candidate_name, row.state, row.district, row.office)
        if key in index:
            row.candidate_id = index[key]
            row.excluded_because = None
            row.resolved_via = 'name_index'
            continue
        matches = roster_matches(row.candidate_name, row.state, row.district, people)
        if len(matches) == 1 and matches[0]['fec_candidate_ids']:
            ids = matches[0]['fec_candidate_ids']
            if len(ids) == 1:
                row.candidate_id = ids[0]
                row.excluded_because = None
                row.resolved_via = 'roster'
                continue
        unresolved.append(row)
    return len(unresolved), unresolved


def per_candidate_cycle(rows: list[IeRow]) -> dict:
    """{(candidate_id, cycle): (support, oppose, total)} over counted rows."""
    totals: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    for row in rows:
        if not row.counted:
            continue
        entry = totals[(row.candidate_id, row.cycle)]
        if row.direction == 'S':
            entry[0] += row.cents
        elif row.direction == 'O':
            entry[1] += row.cents
        entry[2] += row.cents
    return {key: tuple(value) for key, value in totals.items()}


class Race:
    """One race-phase: who the spender backed, and what it spent against whom."""

    def __init__(self) -> None:
        self.backed: set[str] = set()
        self.backed_names: dict[str, str] = {}
        self.oppose_total = 0
        self.oppose_rows: list[IeRow] = []

    def add(self, row: IeRow) -> None:
        if row.direction == 'S' and row.candidate_id:
            self.backed.add(row.candidate_id)
            self.backed_names[row.candidate_id] = row.candidate_name
        elif row.direction == 'O':
            self.oppose_total += row.cents
            self.oppose_rows.append(row)

    def against_backed(self, backed_id: str) -> int:
        backed_name = self.backed_names[backed_id].upper()
        return sum(
            row.cents
            for row in self.oppose_rows
            if row.candidate_id == backed_id
            or (not row.candidate_id and row.candidate_name.upper() == backed_name)
        )


def opposition_credits(rows: list[IeRow], person_of: dict[str, str]) -> tuple[dict, dict, list]:
    """Opposition credit per (person_key, cycle), non-roster credit, and uncredited races.

    A race credits only when exactly one candidate was backed in it; the
    credit is all opposition spending in the race minus spending against
    the backed candidate themselves.
    """
    races: dict[tuple, Race] = defaultdict(Race)
    for row in rows:
        races[row.race_key].add(row)
    by_person: dict[tuple[str, int], int] = defaultdict(int)
    nonroster: dict[tuple[str, int], int] = defaultdict(int)
    uncredited = []
    for key, race in sorted(races.items()):
        if race.oppose_total <= 0:
            continue
        if len(race.backed) != 1:
            uncredited.append((key, len(race.backed), race.oppose_total))
            continue
        backed_id = next(iter(race.backed))
        creditable = race.oppose_total - race.against_backed(backed_id)
        person_key = person_of.get(backed_id)
        if person_key:
            by_person[(person_key, key[0])] += creditable
        else:
            nonroster[(backed_id, key[0])] += creditable
    return dict(by_person), dict(nonroster), uncredited
