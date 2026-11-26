"""Corrected figures (Variant A) from the square-one derivation, for the pipeline.

Loads data/intermediate/square_one/derived.json (written by
`python3 -m receipts.square_one.derive`, which runs as a rebuild step)
and exposes the corrected per-person per-cycle figures the store steps
substitute for cycles 2022-2026: AIPAC direct, pro-Israel direct, and
transfers from/to. Variant A is the headline (methodology §8 item 24):
JFC shares count as direct. Transfers are substituted in every cycle
the derivation covers, not just the API cycles: the derivation's
transfer dedup (shared committees, one kept view) runs over the whole
career, while the AIPAC and pro-Israel corrections only exist for
2022-2026. Earlier cycles keep the bulk figures for AIPAC and
pro-Israel; the accessors return None for them so callers fall through
to the store.

The figures are exact integer cents. A person's corrected total for a
cycle is carried on one candidate ID — the kept view (methodology §8
item 25): the §8 item 15 record's kept ID where one exists for that
cycle, else the ID whose office matches the person's current chamber.
The per-cycle sums, career totals, verdicts and counts are exact under
that rule; the per-candidate-ID split of a corrected total is an
accounting carry, not a traced committee figure.
"""

from receipts.common.files import read_json
from receipts.common.settings import settings

API_CYCLES = (2022, 2024, 2026)
OFFICE_LETTERS = {'House': 'H', 'Senate': 'S'}


def derived_path():
    return settings().paths.intermediate / 'square_one' / 'derived.json'


def office_map():
    """Candidate ID -> office letter, from the committee master, latest cycle wins.

    This is the derivation's office source
    (receipts.square_one.transfers.candidate_offices): the master can
    list a House candidate ID under office 'S' where the ID was
    redesignated, and the kept choice follows the master, not the ID's
    first letter.
    """
    from receipts.square_one import parsers

    bulk = settings().paths.raw
    offices = {}
    for cycle in sorted(API_CYCLES):
        for row in parsers.candidate_rows(bulk, cycle):
            offices[row.candidate_id] = row.office
    return offices


def kept_candidate_id(person, cycle, dedup_records, offices=None):
    """The candidate ID that carries a person's corrected figure in a cycle.

    The §8 item 15 record's kept ID wins where one exists for that
    cycle; otherwise the ID whose office (committee master, latest
    cycle) matches the person's current chamber, first in roster order;
    last resort the last ID in roster order. Mirrors
    receipts.square_one.transfers.shared_committee_groups.
    """
    for record in dedup_records:
        if record['person_key'] == person['person_key'] and record['cycle'] == cycle:
            return record['kept_id']
    ids = list(person['fec_candidate_ids'] or [])
    if not ids:
        return None
    if offices is None:
        offices = office_map()
    current = person.get('chamber_120') or person.get('chamber_119')
    for candidate_id in ids:
        if offices.get(candidate_id) == OFFICE_LETTERS.get(current or ''):
            return candidate_id
    return ids[-1]


def distribute(corrected_cents, kept_id, candidate_ids):
    """Split a corrected person-cycle total across the person's candidate IDs.

    The kept ID carries the whole corrected total; every other ID
    carries zero for that field. The per-cycle sum is the corrected
    total exactly.
    """
    return {cid: (corrected_cents if cid == kept_id else 0) for cid in candidate_ids}


class Corrected:
    """The derivation's corrected figures, in cents, under Variant A."""

    def __init__(self, output):
        self.snapshot = output['snapshot']
        self.aipac = {
            (key.split('|')[0], int(key.split('|')[1])): entry['aipac_a_cents']
            for key, entry in output['corrected_per_cycle'].items()
        }
        self.pro_israel = {
            (key.split('|')[0], int(key.split('|')[1])): entry['pro_israel_a_cents']
            for key, entry in output['corrected_per_cycle'].items()
        }
        self.transfers_from = {
            (key.split('|')[0], int(key.split('|')[1])): cents
            for key, cents in output['transfers_from_corrected'].items()
        }
        if 'transfers_to_corrected' not in output:
            raise SystemExit(
                'derived.json has no transfers_to_corrected; '
                're-run `python3 -m receipts.square_one.derive`'
            )
        self.transfers_to = {
            (key.split('|')[0], int(key.split('|')[1])): cents
            for key, cents in output['transfers_to_corrected'].items()
        }
        self.counts = output['counts']['A']

    def aipac_cents(self, person_key, cycle):
        """Corrected AIPAC direct for a cycle, in cents; None before 2022.

        Absent from the merge means the API shows $0 for that cycle, so
        an API cycle with no entry corrects to zero, not to the pas2
        figure — that is the derivation's rule (a lower bound for 2022,
        where only AIPAC and the main conduits were pulled).
        """
        if cycle not in API_CYCLES:
            return None
        return self.aipac.get((person_key, cycle), 0)

    def pro_israel_cents(self, person_key, cycle):
        """Corrected pro-Israel direct for a cycle, in cents; None before 2022."""
        if cycle not in API_CYCLES:
            return None
        return self.pro_israel.get((person_key, cycle), 0)

    def transfers_cents(self, person_key, cycle):
        """Corrected transfers from/to for a cycle, in cents.

        The derivation dedups transfers in every cycle, so a pair is
        returned for any cycle the derivation covers. An API cycle with
        no entry corrects to zero; any other cycle with no entry is
        untouched (None) — the derivation has no figure for it.
        """
        if (person_key, cycle) in self.transfers_from:
            return (
                self.transfers_from[(person_key, cycle)],
                self.transfers_to.get((person_key, cycle), 0),
            )
        if cycle in API_CYCLES:
            return (0, 0)
        return None

    @property
    def transfer_cycles(self):
        """Every cycle the derivation's transfer figures cover."""
        return sorted({cycle for (_, cycle) in self.transfers_from})


def load():
    """The corrected figures, guarded on the staged snapshot."""
    output = read_json(derived_path())
    if output.get('snapshot') != settings().data_as_of:
        raise SystemExit(
            f'derived.json is from snapshot {output.get("snapshot")}, '
            f'but data_as_of is {settings().data_as_of}; '
            're-run `python3 -m receipts.square_one.derive`'
        )
    return Corrected(output)


def _claim(claims, person, cycle, value, label, dedup_records, offices):
    """Record one nonzero corrected figure's claim on its kept (candidate, cycle).

    Two people can share a candidate ID: each row takes its claim, never
    a later person's zero, and two different nonzero claims on one row
    fail loudly.
    """
    key = person['person_key']
    kept = kept_candidate_id(person, cycle, dedup_records, offices)
    if kept is None:
        raise SystemExit(f'{key} {cycle}: corrected {label} {value} but no FEC IDs')
    pair = (kept, cycle)
    if pair in claims and claims[pair] != value:
        raise SystemExit(
            f'{key} {cycle}: corrected {label} {value} conflicts with '
            f'{claims[pair]} already claimed for {pair}'
        )
    claims[pair] = value


def substitute_aipac(counted, filed, people, dedup_records, corrected, columns, offices=None):
    """Replace aipac_pac_direct in accepted-money rows with the corrected figures.

    `counted` maps (candidate_id, cycle) to {column: Money} and `filed` is
    the set of (candidate_id, cycle) with anything filed, as built by the
    store. For every API cycle the person's entries are set so they sum
    to the corrected Variant A total: the kept ID carries it, the other
    IDs carry zero. A cycle with a corrected total but no entry gains
    one on the kept ID (other columns zero), and the kept pair counts
    as filed — otherwise accepted_by_person drops the row and the money
    vanishes from the dataset. Returns (counted, filed) with new dicts.
    The earmark column is untouched (still pas2). `offices` is the
    committee-master office map; it is read from the staged bulk files
    when not given.

    Two people can share a candidate ID, so the substitution runs in
    two passes: first every nonzero corrected figure claims its kept
    (candidate, cycle), then each row takes its claim or zero. A later
    person's zero never overwrites an earlier person's money on a
    shared ID, and two different nonzero claims on one row fail loudly.
    """
    from receipts.domain.money import Money

    counted = dict(counted)
    filed = set(filed)
    if offices is None:
        offices = office_map()
    claims = {}
    for person in people:
        key = person['person_key']
        for cycle in API_CYCLES:
            cents = corrected.aipac_cents(key, cycle)
            if not cents:
                continue
            _claim(claims, person, cycle, cents, 'AIPAC', dedup_records, offices)
    for person in people:
        key = person['person_key']
        ids = list(person['fec_candidate_ids'] or [])
        for cycle in API_CYCLES:
            cents = corrected.aipac_cents(key, cycle)
            if cents is None:
                continue
            present = [cid for cid in ids if (cid, cycle) in counted]
            if not present:
                if cents == 0:
                    continue
                kept = kept_candidate_id(person, cycle, dedup_records, offices)
                counted[(kept, cycle)] = {c: Money(0) for c in columns}
                counted[(kept, cycle)]['aipac_pac_direct'] = Money(cents)
                filed.add((kept, cycle))
                continue
            if cents != 0:
                kept = kept_candidate_id(person, cycle, dedup_records, offices)
                if (kept, cycle) not in counted:
                    counted[(kept, cycle)] = {c: Money(0) for c in columns}
                filed.add((kept, cycle))
            for cid in [c for c in ids if (c, cycle) in counted]:
                row = dict(counted[(cid, cycle)])
                row['aipac_pac_direct'] = Money(claims.get((cid, cycle), 0))
                counted[(cid, cycle)] = row
    return counted, filed


def substitute_transfers(finances, people, dedup_records, corrected, offices=None):
    """Replace transfers from/to in weball finances with the deduped figures.

    `finances` maps (candidate_id, cycle) to CampaignFinances. The
    derivation dedups transfers in every cycle it covers, so every
    covered cycle is substituted here, not just the API cycles: the
    person's entries are set so they sum to the corrected totals, the
    kept ID carrying them and the other IDs zero. A cycle with
    corrected transfers but no weball row is a derivation/store
    disagreement and fails loudly. Where the kept committee filed no
    weball row that cycle, the money stays on the filing ID — the
    person-cycle total is exact either way, and fabricating a weball
    row would corrupt the cash stocks. Returns a new dict. `offices`
    is the committee-master office map; it is read from the staged
    bulk files when not given. Claims work as in substitute_aipac: a
    shared candidate ID's row takes its nonzero claim, never a later
    person's zero.
    """
    from dataclasses import replace

    from receipts.domain.money import Money

    finances = dict(finances)
    if offices is None:
        offices = office_map()
    claims = {}
    for person in people:
        key = person['person_key']
        for cycle in corrected.transfer_cycles:
            pair = corrected.transfers_cents(key, cycle)
            if pair is None or pair == (0, 0):
                continue
            _claim(claims, person, cycle, pair, 'transfers', dedup_records, offices)
    for person in people:
        key = person['person_key']
        ids = list(person['fec_candidate_ids'] or [])
        for cycle in corrected.transfer_cycles:
            pair = corrected.transfers_cents(key, cycle)
            if pair is None:
                continue
            from_cents, to_cents = pair
            present = [cid for cid in ids if (cid, cycle) in finances]
            if not present:
                if from_cents == 0 and to_cents == 0:
                    continue
                raise SystemExit(
                    f'{key} {cycle}: corrected transfers '
                    f'({from_cents}, {to_cents}) but no weball row'
                )
            kept = kept_candidate_id(person, cycle, dedup_records, offices)
            target = kept if kept in present else present[0]
            for cid in present:
                row = finances[(cid, cycle)]
                if (cid, cycle) in claims:
                    claim_from, claim_to = claims[(cid, cycle)]
                    finances[(cid, cycle)] = replace(
                        row,
                        transfers_from_auth=Money(claim_from),
                        transfers_to_auth=Money(claim_to),
                    )
                elif cid == target:
                    finances[(cid, cycle)] = replace(
                        row,
                        transfers_from_auth=Money(from_cents),
                        transfers_to_auth=Money(to_cents),
                    )
                else:
                    finances[(cid, cycle)] = replace(
                        row, transfers_from_auth=Money(0), transfers_to_auth=Money(0)
                    )
    return finances
