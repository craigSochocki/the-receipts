"""Who filed for which race, keyed by the filing's own race (the MP delegate files under 01)."""

from receipts.store.read import connect

SUMMARIES = (
    'SELECT candidate_id, office_state, office_district, total_receipts_cents '
    'FROM candidate_summaries WHERE cycle = ?'
)


def races_in(cycle):
    """(race_map, by_candidate): each race's candidates with receipts, and each candidate's race."""
    race_map, by_candidate = {}, {}
    with connect() as db:
        for candidate_id, state, district, receipts in db.execute(SUMMARIES, [cycle]).fetchall():
            race = (candidate_id[0], state, district)
            race_map.setdefault(race, []).append((candidate_id, receipts))
            by_candidate[candidate_id] = race
    return race_map, by_candidate
