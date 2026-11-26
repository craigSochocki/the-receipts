"""Opposition credit: what a spender's attacks on a rival are worth to the backed candidate.

Split out of ie.py: the race rule (exactly one backed candidate per race)
is its own method, separate from the IE row derivation and blank-ID
resolution.
"""

from collections import defaultdict

from receipts.square_one.ie import IeRow, per_candidate_cycle, resolve_blank_ids


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


def pro_israel_support_and_credits(
    rows: list[IeRow], listed_spenders: list[str], people: list[dict], person_of: dict[str, str]
) -> tuple[dict, dict]:
    """Pro-Israel IE support and opposition credit per (person_key, cycle).

    Per listed spender: blank candidate IDs are resolved by name, then
    support is the S rows and the credit is the exactly-one-backed-candidate
    race rule. Support here is the pro-Israel IE layer only — not all IE.
    """
    roster_ids = {cid for p in people for cid in p['fec_candidate_ids']}
    support: dict[tuple, int] = defaultdict(int)
    credit: dict[tuple, int] = defaultdict(int)
    for spender in listed_spenders:
        spender_rows = [r for r in rows if r.spender_id == spender]
        resolve_blank_ids(spender_rows, people)
        for (cid, cycle), totals in per_candidate_cycle(spender_rows).items():
            if cid in roster_ids:
                person_key = person_of[cid]
                support[(person_key, cycle)] += totals[0]
        for (person_key, cycle), cents in opposition_credits(spender_rows, person_of)[0].items():
            credit[(person_key, cycle)] += cents
    return dict(support), dict(credit)


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
