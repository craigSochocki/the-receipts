select person_key from {{ source('gold', 'other_committees_people') }}
where fec_candidate_ids <> ''
  and other_committees_total_career is distinct from party_committees_career + leadership_pacs_career + labor_pacs_career + trade_pacs_career + membership_pacs_career + cooperative_pacs_career + other_unclassified_career
