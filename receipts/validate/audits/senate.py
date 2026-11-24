"""senate_class re-derived from the legislators yaml for every row."""

from collections import Counter

from receipts.common.files import read_yaml
from receipts.common.settings import settings


def senate_class(audit, dataset):
    """(n) senate_class: re-derived from the legislators yaml, independent
    of build_roster.py — own latest Senate term's class field where
    the person holds a seat into 2026, else the class of whoever held
    that seat during 2026 (appointee/outgoing holder, same state).
    """
    leg = read_yaml(settings().paths.source / 'legislators-current.yaml')
    leg_terms = {
        e['id'].get('bioguide'): [t for t in e['terms'] if t.get('type') == 'sen'] for e in leg
    }
    cont_sen = {
        r['person_key']
        for r in dataset.records
        if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate'
    }

    def rederive_class(r):
        if r['chamber_119'] != 'Senate' and r['chamber_120'] != 'Senate':
            return None
        own = [
            t for t in leg_terms.get(r['person_key'], []) if (t.get('end') or '') >= '2026-01-01'
        ]
        if own:
            return own[-1].get('class')
        holders = set()
        for e in leg:
            for t in e['terms']:
                if (
                    t.get('type') == 'sen'
                    and t.get('state') == r['state']
                    and (t.get('start') or '') <= '2026-12-31'
                    and (t.get('end') or '') >= '2026-01-01'
                    and e['id'].get('bioguide') not in cont_sen
                ):
                    holders.add(t.get('class'))
        return holders.pop() if len(holders) == 1 else None

    mism = sum(1 for r in dataset.records if rederive_class(r) != r['senate_class'])
    audit.check(
        'senate_class re-derives from legislators-current.yaml (0 mismatches)',
        mism == 0,
        f'{mism} mismatches',
    )
    senators = [
        r for r in dataset.records if r['chamber_119'] == 'Senate' or r['chamber_120'] == 'Senate'
    ]
    sen_keys = {r['person_key'] for r in senators}
    audit.check(
        'senate_class is None for all non-senators, 1/2/3 for all senators',
        all(r['senate_class'] is None for r in dataset.records if r['person_key'] not in sen_keys)
        and all(r['senate_class'] in (1, 2, 3) for r in senators),
        f'{len(senators)} senator rows',
    )
    s120 = [r for r in dataset.records if r['in_120th'] == 'yes' and r['chamber_120'] == 'Senate']
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
    by_name = {r['full_name']: r for r in dataset.records}
    spot = [
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
    bad = [
        (n, by_name[n]['senate_class'], want)
        for n, want in spot
        if by_name[n]['senate_class'] != want
    ]
    audit.check(
        'senate_class spot cases (Schumer/Kelly/Warnock 3, Schiff/Kim 1, '
        'Ossoff/Brown/Moody 3/3/3, El-Sayed/Flanagan/Andrews 2)',
        bad == [],
        f'got {bad}',
    )
