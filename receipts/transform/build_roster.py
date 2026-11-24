#!/usr/bin/env python3
"""Build union roster 119th + 120th Congress.
Sources:
 - 119th: unitedstates/congress-legislators legislators-current.yaml (fetched 2026-11-12)
 - 120th: Wikipedia '120th United States Congress' (crawled 2026-11-12 11:26 UTC),
   transcribed to 120th_roster.json; new-members page cross-checked.
 - Returning former members: legislators-historical.yaml via historical_lookup.json
 - Facts neither source carries (special elections, uncalled seats, leadership):
   data/source/roster_facts.yaml
"""

import collections
from typing import NamedTuple

from receipts.common.files import read_json, read_yaml, write_json
from receipts.common.settings import settings
from receipts.domain.names import first_names_agree, norm, slug, split_name

PARTY_NOTES = {
    'DFL': 'Party listed as DFL (Minnesota Democratic-Farmer-Labor, Democratic affiliate).',
    'PPD': 'Resident Commissioner; party PPD (caucuses with Democrats).',
}


def member(**fields):
    """A roster row: every field, in output order, with defaults for the ones not given."""
    row = {
        'person_key': '',
        'full_name': '',
        'first_name': '',
        'last_name': '',
        'chamber_119': '',
        'chamber_120': '',
        'state': '',
        'district_119': '',
        'district_120': '',
        'party_119': '',
        'party_120': '',
        'leadership_119': '',
        'leadership_120': 'TBD',
        'fec_candidate_ids': [],
        'in_119th': 'no',
        'in_120th': 'no',
        'notes': '',
        '_bioguide': None,
        '_fec_source': '',
    }
    row.update(fields)
    return row


class Seat120(NamedTuple):
    """One seat of the 120th roster (120th_roster.json)."""

    name: str
    state: str
    district: str | None
    party: str
    chamber: str

    @property
    def district_120(self):
        return '' if self.chamber == 'Senate' else str(self.district)

    @property
    def party_120(self):
        return 'Democrat' if self.party == 'DFL' else self.party


def seats_120th(r120):
    for s in r120['senate']:
        yield Seat120(s['name'], s['state'], None, s['party'], 'Senate')
    for h in r120['house'] + r120['delegates']:
        yield Seat120(h['name'], h['state'], h['district'], h['party'], 'House')


class FormerMembers:
    """legislators-historical.yaml, keyed by normalized name (historical_lookup.json)."""

    def __init__(self, lookup):
        self.lookup = lookup

    def named(self, name):
        return self.lookup[norm(name)]

    def returning(self, name, state):
        """The former member a 120th seat-holder is, if any. Guards against namesakes
        from long ago: requires service in the same state ending in 2000 or later."""
        first, last = split_name(name)
        for key in (norm(f'{first} {last}'), norm(name)):
            if key in self.lookup:
                last_term = self.lookup[key].get('last_term') or {}
                if last_term.get('state') == state and (last_term.get('end') or '') >= '2000':
                    return self.lookup[key]
        return None


class Roster:
    """Everyone who serves in the 119th or the 120th Congress, keyed by person_key."""

    def __init__(self, legislators):
        self.legislators = legislators
        self.rows = {}
        for p in legislators:
            bioguide = p['id'].get('bioguide')
            term = p['terms'][-1]
            name = p['name']
            full = (
                name.get('official_full')
                or f'{name.get("first", "")} {name.get("last", "")}'.strip()
            )
            self.rows[bioguide] = member(
                person_key=bioguide,
                full_name=full,
                first_name=name.get('first', ''),
                last_name=name.get('last', ''),
                chamber_119='House' if term['type'] == 'rep' else 'Senate',
                state=term.get('state', ''),
                district_119='' if term['type'] == 'sen' else str(term.get('district', '')),
                party_119=term.get('party', ''),
                fec_candidate_ids=list(p['id'].get('fec') or []),
                in_119th='yes',
                _bioguide=bioguide,
                _fec_source='repo-current',
                _nickname=name.get('nickname', ''),
                _official=full,
            )
        self.by_state_last = collections.defaultdict(list)
        for row in self.rows.values():
            self.by_state_last[(row['state'], norm(row['last_name']))].append(row)

    def note(self, key, text):
        row = self.rows[key]
        row['notes'] = (row['notes'] + '; ' if row['notes'] else '') + text

    def matching(self, fields):
        return [
            key for key, row in self.rows.items() if all(row[f] == v for f, v in fields.items())
        ]

    @staticmethod
    def known_as(first, row):
        return first_names_agree(
            first, row['first_name'], row.get('_nickname', ''), row.get('_official', '')
        )

    def sitting_member(self, name, state):
        """The 119th member a 120th seat-holder is: same state and last name, and a first
        name that agrees (nickname-aware), so same-state namesakes stay apart."""
        first, last = split_name(name)
        return next(
            (
                row
                for row in self.by_state_last.get((state, norm(last)), [])
                if self.known_as(first, row)
            ),
            None,
        )

    def seat_120th(self, seats, former):
        """Mark sitting members who serve in the 120th; add returning and brand-new members."""
        newcomers = []
        for seat in seats:
            row = self.sitting_member(seat.name, seat.state)
            if row is not None:
                row.update(
                    chamber_120=seat.chamber,
                    district_120=seat.district_120,
                    party_120=seat.party_120,
                    in_120th='yes',
                )
                if seat.party in PARTY_NOTES:
                    self.note(row['person_key'], PARTY_NOTES[seat.party])
                continue
            first, last = split_name(seat.name)
            joins = dict(
                full_name=seat.name,
                first_name=first,
                last_name=last,
                chamber_120=seat.chamber,
                state=seat.state,
                district_120=seat.district_120,
                party_120=seat.party_120,
                in_120th='yes',
            )
            past = former.returning(seat.name, seat.state)
            if past is not None:
                key = past['bioguide'] or slug(first, last, seat.state, seat.chamber)
                term = past['last_term']
                self.rows[key] = member(
                    person_key=key,
                    **joins,
                    fec_candidate_ids=list(past.get('fec') or []),
                    notes=f'Returning former member; last served {term.get("type")} {term.get("state")} ending {term.get("end")} (prior service, not 119th).',
                    _bioguide=past.get('bioguide'),
                    _fec_source='repo-historical',
                )
                newcomers.append(('returning', seat.name, seat.state))
            else:
                key = slug(first, last, seat.state, seat.chamber)
                self.rows[key] = member(
                    person_key=key,
                    **joins,
                    notes='New member of the 120th Congress (first term in Congress).',
                    _fec_source='none-fec-api-pending',
                )
                newcomers.append(('brand-new', seat.name, seat.state))
        return newcomers

    def apply_facts(self, facts, former):
        for fields in facts['added_members']:
            fields = dict(fields)
            history = former.named(fields.pop('fec_from_history'))
            self.rows[fields['person_key']] = member(
                fec_candidate_ids=list(history.get('fec') or []), **fields
            )
        self.add_notes(facts['notes'])
        for key, row in self.rows.items():
            if row['in_119th'] != 'yes':
                continue
            seat = next(
                (s for s in facts['unknown_in_120th'] if key in self.matching(s['match'])), None
            )
            if seat:
                row['in_120th'] = 'unknown'
                self.note(key, '120th membership UNKNOWN: ' + seat['note'])
        self.add_notes(facts['late_notes'])

    def add_notes(self, notes):
        for fact in notes:
            keys = [fact['person_key']] if 'person_key' in fact else self.matching(fact['match'])
            for key in keys:
                self.note(key, fact['note'])

    def mark_leadership_119(self, roles):
        for row in self.rows.values():
            if row['in_119th'] != 'yes':
                continue
            for name, role in roles.get(row['chamber_119'], {}).items():
                first, last = split_name(name)
                if norm(last) == norm(row['last_name']) and self.known_as(first, row):
                    row['leadership_119'] = role

    def note_unverified_leadership_120(self, roles):
        for key, row in self.rows.items():
            if row['full_name'] in roles and row['in_120th'] == 'yes':
                self.note(
                    key,
                    f'UNVERIFIED 120th leadership: Wikipedia 120th Congress page (Nov 12, 2026) lists as {roles[row["full_name"]]}; leadership elections are Nov 18-19, 2026, so role is TBD pending confirmation.',
                )

    def note_successors(self, r120):
        """Outgoing members: who holds the seat in the 120th. House: the same state and
        district; Senate: the state's senators who are new in the 120th."""
        house_by_seat = {(h['state'], str(h['district'])): h for h in r120['house']}
        senators_by_state = collections.defaultdict(list)
        for s in r120['senate']:
            senators_by_state[s['state']].append(s['name'])
        for key, row in self.rows.items():
            if not (row['in_119th'] == 'yes' and row['in_120th'] == 'no'):
                continue
            if (
                row['chamber_119'] == 'House'
                and (row['state'], row['district_119']) in house_by_seat
            ):
                holder = house_by_seat[(row['state'], row['district_119'])]
                self.note(
                    key,
                    f'Not in 120th; {row["state"]}-{row["district_119"]} in the 120th is held by {holder["name"]} ({holder["party"]}).',
                )
            elif row['chamber_119'] == 'Senate':
                new_senators = [
                    name
                    for name in senators_by_state[row['state']]
                    if not any(
                        r['full_name'] == name and r['in_119th'] == 'yes'
                        for r in self.rows.values()
                    )
                ]
                if new_senators:
                    self.note(
                        key,
                        f'Not in 120th; new senator(s) from {row["state"]} in the 120th: {", ".join(new_senators)}.',
                    )

    def assign_senate_classes(self):
        """Senate class (1/2/3) for every senator row, from the legislators yaml: each
        Senate term carries its class directly. A person holding a Senate seat into 2026
        takes their own latest term's class; a new senator (no Senate term of their own)
        takes the class of whoever held that seat during 2026 (the appointee or outgoing
        holder, whose term carries the seat's class). Render-time derivation from FEC
        cycles was tested and fails (every senator fundraises every cycle; special-election
        winners break the cycle-mod-6 pattern), so it is computed here, not on the page."""
        senate_terms = {
            p['id'].get('bioguide'): [t for t in p['terms'] if t.get('type') == 'sen']
            for p in self.legislators
        }
        continuing = {
            r['person_key']
            for r in self.rows.values()
            if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate'
        }

        def senate_class(row):
            if row['chamber_119'] != 'Senate' and row['chamber_120'] != 'Senate':
                return None
            own = [
                t
                for t in senate_terms.get(row.get('_bioguide') or row['person_key'], [])
                if (t.get('end') or '') >= '2026-01-01'
            ]
            if own:
                return own[-1].get('class')
            holders = {
                t.get('class')
                for p in self.legislators
                for t in p['terms']
                if t.get('type') == 'sen'
                and t.get('state') == row['state']
                and (t.get('start') or '') <= '2026-12-31'
                and (t.get('end') or '') >= '2026-01-01'
                and p['id'].get('bioguide') not in continuing
            }
            return holders.pop() if len(holders) == 1 else None

        for row in self.rows.values():
            row['senate_class'] = senate_class(row)

    def unmatched(self, seats):
        """120th seats with no row, and with more than one (nickname-aware)."""
        missing, duplicated = [], []
        for seat in seats:
            first, last = split_name(seat.name)
            hits = [
                r['full_name']
                for r in self.rows.values()
                if r['in_120th'] == 'yes'
                and r['state'] == seat.state
                and r['chamber_120'] == seat.chamber
                and norm(r['last_name']) == norm(last)
                and self.known_as(first, r)
            ]
            if not hits:
                missing.append(seat)
            elif len(hits) > 1:
                duplicated.append((seat, hits))
        return missing, duplicated

    def print_summary(self, newcomers):
        rows = list(self.rows.values())

        def count(in_119th, in_120th):
            return sum(1 for r in rows if r['in_119th'] in in_119th and r['in_120th'] in in_120th)

        print('total rows:', len(rows))
        print('in 119th:', count({'yes'}, {'yes', 'no', 'unknown'}))
        print('in 120th:', count({'yes', 'no'}, {'yes'}))
        print('in 120th unknown:', count({'yes', 'no'}, {'unknown'}))
        print('in both:', count({'yes'}, {'yes'}))
        print('119th only:', count({'yes'}, {'no'}))
        print('120th only:', count({'no'}, {'yes'}))
        print(
            'new persons (returning/brand-new):',
            collections.Counter(kind for kind, *_ in newcomers),
        )
        for kind in ('brand-new', 'returning'):
            print(f'{kind} list:')
            for _, name, state in (n for n in newcomers if n[0] == kind):
                print('  ', name, state)
        print(
            'UNKNOWN rows:',
            [
                (r['full_name'], r['state'], r['chamber_119'], r['district_119'])
                for r in rows
                if r['in_120th'] == 'unknown'
            ],
        )


def build(legislators, historical_lookup, r120, facts):
    """(roster, the 120th seats, who is new) from the parsed sources and curated facts."""
    roster = Roster(legislators)
    former = FormerMembers(historical_lookup)
    seats = list(seats_120th(r120))
    newcomers = roster.seat_120th(seats, former)
    roster.apply_facts(facts, former)
    roster.mark_leadership_119(facts['leadership_119'])
    roster.note_unverified_leadership_120(facts['unverified_leadership_120'])
    roster.note_successors(r120)
    roster.assign_senate_classes()
    return roster, seats, newcomers


def main():
    """Build the roster from the legislators file, the 120th roster and the curated facts."""
    paths = settings().paths
    roster, seats, newcomers = build(
        read_yaml(paths.source / 'legislators-current.yaml'),
        read_json(paths.source / 'historical_lookup.json'),
        read_json(paths.source / '120th_roster.json'),
        read_yaml(paths.roster_facts),
    )
    write_json(paths.roster_intermediate, list(roster.rows.values()))
    roster.print_summary(newcomers)
    missing, duplicated = roster.unmatched(seats)
    if missing or duplicated:
        raise SystemExit(f'120th seats with no row: {missing}; with more than one: {duplicated}')


if __name__ == '__main__':
    main()
