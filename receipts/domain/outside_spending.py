"""Which independent expenditures count (methodology §4, §8).

The IE files hold tens of billions in bogus filings, so the filter is
part of the method: the spender must be a registered committee and the
candidate an identified one.
"""
from receipts.domain.one_copy import OneCopyEach

UNREGISTERED_COMMITTEE = 'unregistered_committee'
BLANK_CANDIDATE = 'blank_candidate'
CANDIDATE_NOT_IDENTIFIED = 'candidate_not_identified'


def latest_filings():
    """One row per expenditure: the latest receipt, then the highest file number."""
    def recency(expenditure):
        return (expenditure.received, expenditure.file_number)

    return OneCopyEach(lambda new, kept: recency(new) > recency(kept))


def exclusion(expenditure, registered_committees, identified_candidates):
    """Why an expenditure is left out, or None if it counts. First reason wins."""
    if expenditure.spender_id not in registered_committees:
        return UNREGISTERED_COMMITTEE
    if not expenditure.candidate_id:
        return BLANK_CANDIDATE
    if expenditure.candidate_id not in identified_candidates:
        return CANDIDATE_NOT_IDENTIFIED
    return None
