"""senate_class re-derived from the legislators yaml for every row."""

from collections import Counter

from receipts.common.files import read_yaml
from receipts.common.settings import settings

# Senators whose class is pinned: continuing members of each class, special-election
# winners, and new senators who take the class of the seat's outgoing holder.
SPOT_CLASS_NAMES = [
    'Charles E. Schumer',
    'Mark Kelly',
    'Raphael G. Warnock',
    'Adam B. Schiff',
    'Andy Kim',
    'Jon Ossoff',
    'Sherrod Brown',
    'Ashley Moody',
    'Abdul El-Sayed',
    'Peggy Flanagan',
    'Annie Andrews',
]


def is_senator(r):
    return r['chamber_119'] == 'Senate' or r['chamber_120'] == 'Senate'


class SeatClasses:
    """Senate class from the legislators yaml: the person's own term serving into 2026,
    else the class of whoever held that state's seat during 2026."""

    def __init__(self, legislators, continuing):
        self.legislators = legislators
        self.continuing = continuing
        self.senate_terms = {
            e['id'].get('bioguide'): [t for t in e['terms'] if t.get('type') == 'sen']
            for e in legislators
        }

    def of(self, r):
        if not is_senator(r):
            return None
        own = [
            t
            for t in self.senate_terms.get(r['person_key'], [])
            if (t.get('end') or '') >= '2026-01-01'
        ]
        if own:
            return own[-1].get('class')
        holders = {
            t.get('class')
            for e in self.legislators
            for t in e['terms']
            if t.get('type') == 'sen'
            and t.get('state') == r['state']
            and (t.get('start') or '') <= '2026-12-31'
            and (t.get('end') or '') >= '2026-01-01'
            and e['id'].get('bioguide') not in self.continuing
        }
        return holders.pop() if len(holders) == 1 else None


def classes_rederive(audit, records):
    continuing = {
        r['person_key'] for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate'
    }
    classes = SeatClasses(
        read_yaml(settings().paths.source / 'legislators-current.yaml'), continuing
    )
    mism = sum(1 for r in records if classes.of(r) != r['senate_class'])
    audit.check(
        'senate_class re-derives from legislators-current.yaml (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )


def classes_in_range(audit, records):
    senators = [r for r in records if is_senator(r)]
    audit.check(
        'senate_class is None for all non-senators, 1/2/3 for all senators',
        all(r['senate_class'] is None for r in records if not is_senator(r))
        and all(r['senate_class'] in (1, 2, 3) for r in senators),
        f'{len(senators)} senator rows',
    )


def class_counts_120th(audit, records):
    s120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate']
    counts = Counter(r['senate_class'] for r in s120)
    audit.pin(
        '120th senator class counts',
        'senate_class.counts_120th',
        {str(senate_class): counts[senate_class] for senate_class in sorted(counts)},
    )
    audit.pin(
        'Class 3 Democrats in the 120th',
        'senate_class.class3_democrats_120th',
        sum(1 for r in s120 if r['party_120'] == 'Democrat' and r['senate_class'] == 3),
    )


def class_spot_cases(audit, records):
    by_name = {r['full_name']: r for r in records}
    audit.pin(
        'senate_class spot cases',
        'spot.senate_class',
        {name: by_name[name]['senate_class'] for name in SPOT_CLASS_NAMES},
    )


def senate_class(audit, dataset):
    """(n) senate_class: re-derived from the legislators yaml, independent of build_roster.py."""
    classes_rederive(audit, dataset.records)
    classes_in_range(audit, dataset.records)
    class_counts_120th(audit, dataset.records)
    class_spot_cases(audit, dataset.records)
