"""Matching people's names across sources: normalizing, splitting, nicknames."""

import re
import unicodedata


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z ]', '', s.lower()).strip()


NICK = {
    'bob': 'robert',
    'mike': 'michael',
    'jim': 'james',
    'dan': 'daniel',
    'dave': 'david',
    'joe': 'joseph',
    'tom': 'thomas',
    'bill': 'william',
    'chuck': 'charles',
    'hank': 'henry',
    'jerry': 'gerald',
    'rick': 'richard',
    'steve': 'steven',
    'chris': 'christopher',
    'andy': 'andrew',
    'matt': 'matthew',
    'sam': 'samuel',
    'ben': 'benjamin',
    'alex': 'alexander',
    'nick': 'nicholas',
    'rob': 'robert',
    'ron': 'ronald',
    'don': 'donald',
    'ray': 'raymond',
    'fred': 'frederick',
    'greg': 'gregory',
    'jeff': 'jeffrey',
    'jon': 'john',
    'johnny': 'john',
    'josh': 'joshua',
    'zach': 'zachary',
    'zack': 'zachary',
    'jake': 'jacob',
    'kat': 'katherine',
    'kate': 'katherine',
    'kathy': 'katherine',
    'lizzie': 'elizabeth',
    'liz': 'elizabeth',
    'beth': 'elizabeth',
    'susan': 'susan',
    'sue': 'susan',
    'debbie': 'deborah',
    'deb': 'deborah',
    'terri': 'teresa',
    'maggie': 'margaret',
    'peggy': 'margaret',
    'tony': 'anthony',
    'tim': 'timothy',
    'ed': 'edward',
    'pat': 'patrick',
    'randy': 'randall',
    'doug': 'douglas',
    'val': 'valerie',
    'ted': 'theodore',
    'pete': 'peter',
    'dick': 'richard',
    'jen': 'jennifer',
    'jess': 'jessica',
    'will': 'william',
    'gabe': 'gabriel',
    'al': 'alan',
    'herb': 'herbert',
    'lou': 'luis',
    'gil': 'gilbert',
    'jack': 'john',
    'bernie': 'bernard',
}

# Multiword last names: display name -> (first, last)


# Names the first/last split gets wrong: multiword last names, multiword first names.
KNOWN_SPLITS = {
    'Lisa Blunt Rochester': ('Lisa', 'Blunt Rochester'),
    'Chris Van Hollen': ('Chris', 'Van Hollen'),
    'Catherine Cortez Masto': ('Catherine', 'Cortez Masto'),
    'Debbie Wasserman Schultz': ('Debbie', 'Wasserman Schultz'),
    'Marie Gluesenkamp Perez': ('Marie', 'Gluesenkamp Perez'),
    'Beth Van Duyne': ('Beth', 'Van Duyne'),
    'Teresa Leger Fernandez': ('Teresa', 'Leger Fernandez'),
    'April McClain Delaney': ('April', 'McClain Delaney'),
    'Matt Van Epps': ('Matt', 'Van Epps'),
    'Darline Graham Nordone': ('Darline', 'Graham Nordone'),
    'La Shawn Ford': ('La Shawn', 'Ford'),
    'Mary Gay Scanlon': ('Mary Gay', 'Scanlon'),
    'Luz Maria Rivas': ('Luz Maria', 'Rivas'),
    'J.D. Ford': ('J.D.', 'Ford'),
    'Darializa Avila Chevalier': ('Darializa', 'Avila Chevalier'),
    'Katy Padilla Stout': ('Katy', 'Padilla Stout'),
    'Jessica Hart Steinmann': ('Jessica', 'Steinmann'),
    'Pablo Hernández Rivera': ('Pablo José', 'Hernández Rivera'),
    'Amata Coleman Radewagen': ('Amata Coleman', 'Radewagen'),
}


def split_name(full):
    """Return (first, last) for a display name; handles suffixes and known multiword names."""
    if full in KNOWN_SPLITS:
        return KNOWN_SPLITS[full]
    s = full.strip()
    for suf in (' Jr.', ' Sr.', ' III', ' II', ' IV'):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    parts = s.split()
    if len(parts) == 1:
        return parts[0], ''
    return ' '.join(parts[:-1]), parts[-1]


def slug(first, last, state, extra=''):
    base = norm(f'{first}-{last}-{state}-{extra}')
    return re.sub(r'[^a-z0-9]+', '-', base).strip('-')


# ---------- 119th base ----------


def first_names_agree(first, *known_names):
    """Nickname-aware agreement between a first name and any of a person's known names
    (e.g. Bernie/Bernard, Jack/John, Rick/Eric, Andy/Garland, French/J. French Hill,
    Lou/Luis Correa)."""
    wanted = [NICK.get(t, t) for t in norm(first).split()]
    known = set()
    for name in known_names:
        for t in norm(name).split():
            known.add(NICK.get(t, t))
            known.add(t)
    return any(t in known for t in wanted)
