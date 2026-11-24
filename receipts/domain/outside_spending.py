"""Which IEs count: the IE files hold bogus filings, so spender and candidate must be identified."""

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
