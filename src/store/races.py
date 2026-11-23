"""Who filed for which race in a cycle, from the store's weball summaries.

The race is the filing's own (office, state, district), not the roster's:
the Northern Mariana Islands delegate race is filed under district 01.
"""
from src.store.read import connect

SUMMARIES = ('SELECT candidate_id, office_state, office_district, total_receipts_cents '
             'FROM candidate_summaries WHERE cycle = ?')


def races_in(cycle):
    """(race_map, by_candidate): each race's [(candidate ID, receipts in cents)],
    and each candidate ID's race."""
    race_map, by_candidate = {}, {}
    with connect() as db:
        for candidate_id, state, district, receipts in db.execute(SUMMARIES, [cycle]).fetchall():
            race = (candidate_id[0], state, district)
            race_map.setdefault(race, []).append((candidate_id, receipts))
            by_candidate[candidate_id] = race
    return race_map, by_candidate
