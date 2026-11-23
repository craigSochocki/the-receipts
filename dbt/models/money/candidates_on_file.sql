-- Candidate IDs that appear anywhere in weball or pas2.
select candidate_id from {{ source('store', 'candidate_summaries') }}
union
select candidate_id from {{ source('store', 'committee_contributions') }}
