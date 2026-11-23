"""The people the tracker follows, and their FEC candidate IDs."""

from collections import defaultdict


def candidate_ids(person):
    return person.get('fec_candidate_ids') or []


class Roster:
    def __init__(self, people):
        self.people = people
        self._people_by_candidate = defaultdict(list)
        for person in people:
            for candidate_id in candidate_ids(person):
                self._people_by_candidate[candidate_id].append(person['person_key'])

    def __contains__(self, candidate_id):
        return candidate_id in self._people_by_candidate

    def others_sharing_an_id_with(self, person):
        return sorted(
            {
                key
                for candidate_id in candidate_ids(person)
                for key in self._people_by_candidate[candidate_id]
                if key != person['person_key']
            }
        )

    def shared_id_note(self, person):
        """The data note for a person listed twice under one FEC ID, or None."""
        others = self.others_sharing_an_id_with(person)
        return 'duplicate roster entry: FEC ID shared with ' + ', '.join(others) if others else None
