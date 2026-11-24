"""senate_class re-derived from the legislators yaml for every row."""

from collections import Counter

from receipts.common.files import read_yaml
from receipts.common.settings import settings

SPOT_CLASSES = [
    ('Charles E. Schumer', 3),
    ('Mark Kelly', 3),
    ('Raphael G. Warnock', 3),
    ('Adam B. Schiff', 1),
    ('Andy Kim', 1),
    ('Jon Ossoff', 2),
    ('Sherrod Brown', 3),
    ('Ashley Moody', 3),
    ('Abdul El-Sayed', 2),
    ('Peggy Flanagan', 2),
    ('Annie Andrews', 2),
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
    cls = Counter(r['senate_class'] for r in s120)
    audit.check(
        '120th senator class counts: C1 33 / C2 32 / C3 34',
        cls == {1: 33, 2: 32, 3: 34},
        f'got {dict(cls)}',
    )
    c3d = [r for r in s120 if r['party_120'] == 'Democrat' and r['senate_class'] == 3]
    audit.check(
        'Class 3 Democrats in the 120th = 16',
        len(c3d) == 16,
        f'got {len(c3d)}: {[r["full_name"] for r in c3d]}',
    )


def class_spot_cases(audit, records):
    by_name = {r['full_name']: r for r in records}
    bad = [
        (n, by_name[n]['senate_class'], want)
        for n, want in SPOT_CLASSES
        if by_name[n]['senate_class'] != want
    ]
    audit.check(
        'senate_class spot cases (Schumer/Kelly/Warnock 3, Schiff/Kim 1, '
        'Ossoff/Brown/Moody 3/3/3, El-Sayed/Flanagan/Andrews 2)',
        bad == [],
        f'got {bad}',
    )


def senate_class(audit, dataset):
    """(n) senate_class: re-derived from the legislators yaml, independent of build_roster.py."""
    classes_rederive(audit, dataset.records)
    classes_in_range(audit, dataset.records)
    class_counts_120th(audit, dataset.records)
    class_spot_cases(audit, dataset.records)
