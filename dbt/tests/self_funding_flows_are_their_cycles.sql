{{ career_mismatches(source('gold', 'self_funding_people'), source('gold', 'self_funding_per_cycle'), [
    ['candidate_contributions_career', 'candidate_contributions'],
    ['candidate_loans_career', 'candidate_loans'],
    ['loan_repayments_career', 'loan_repayments'],
    ['total_receipts_career', 'total_receipts'],
    ['total_disbursements_career', 'total_disbursements'],
    ['transfers_from_auth_career', 'transfers_from_auth'],
    ['transfers_to_auth_career', 'transfers_to_auth'],
]) }}
