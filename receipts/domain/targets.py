"""Primary targets: incoming members whose seat is up next cycle and who took dirty money."""

from receipts.domain.seats import regular_senate_class
from receipts.domain.term import term_record

DIRTY_UNDER = {
    'strict': lambda record: (record['dirty'] or 0) > 0,
    'balanced': lambda record: record['tier_balanced'] == 'dirty',
    'lenient': lambda record: record['tier_lenient'] == 'dirty',
}


HEADLINE = ('clean', 'dirty', 'tier_balanced', 'tier_lenient')


def latest_record(person):
    """The term the headline verdict judges, with that verdict; None when no cycle was up."""
    if person['verdict_cycle'] is None:
        return None
    term = term_record(person['cycles'], person['verdict_cycle'])
    return {**term, **{k: person[k] for k in HEADLINE}}


def seat_up_in(person, cycle):
    """Every House seat is up each cycle; a Senate seat when its class is."""
    if person['chamber_120'] == 'House':
        return True
    return person['chamber_120'] == 'Senate' and person['senate_class'] == regular_senate_class(
        cycle
    )


def is_primary_target(person, preset, cycle):
    """An incoming member, any party, up in `cycle`, dirty under `preset` in their latest election."""
    record = latest_record(person)
    return (
        person['in_120th'] == 'yes'
        and seat_up_in(person, cycle)
        and record is not None
        and DIRTY_UNDER[preset](record)
    )


def primary_targets(people, preset, cycle):
    """The targets for `cycle` under `preset`, dirtiest first."""
    targets = [p for p in people if is_primary_target(p, preset, cycle)]
    return sorted(targets, key=lambda p: -latest_record(p)['dirty'])
