"""Roster input for the square-one re-derivation.

The roster — who is in the tracker, and which FEC candidate IDs belong to
each person — is a committed input, taken from the committed dataset JSON.
Only the roster fields are read from it; no money figure is ever taken
from the dataset. The §8 item 15 double-count record is likewise an input:
the derivation re-derives the double-count decisions from the weball files
and checks them against this record, never the other way round.
"""

import json
from pathlib import Path

ROSTER_FIELDS = (
    'person_key',
    'full_name',
    'chamber_119',
    'chamber_120',
    'state',
    'district_119',
    'district_120',
    'party_119',
    'party_120',
    'in_119th',
    'in_120th',
    'fec_candidate_ids',
    'senate_class',
    'verdict_cycle',
)


def load_roster(dataset_path: Path) -> list[dict]:
    """One dict per roster person, roster fields only (no money)."""
    with open(dataset_path, encoding='utf-8') as f:
        rows = json.load(f)
    people = []
    for row in rows:
        person = {field: row.get(field) for field in ROSTER_FIELDS}
        person['fec_candidate_ids'] = list(row.get('fec_candidate_ids') or [])
        people.append(person)
    return people


def person_of(people: list[dict]) -> dict[str, str]:
    """FEC candidate ID -> person_key (first person wins on a shared ID)."""
    found: dict[str, str] = {}
    for person in people:
        for candidate_id in person['fec_candidate_ids']:
            found.setdefault(candidate_id, person['person_key'])
    return found


def load_dedup_applied(path: Path) -> list[dict]:
    """The recorded §8 item 15 double-count decisions, as data."""
    with open(path, encoding='utf-8') as f:
        return json.load(f)
