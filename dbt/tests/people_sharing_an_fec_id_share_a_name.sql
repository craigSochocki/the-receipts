-- Two roster entries may share an FEC ID only when they are the same person.
select a.candidate_id
from {{ source('store', 'person_candidate_ids') }} as a
join {{ source('store', 'person_candidate_ids') }} as b
    on a.candidate_id = b.candidate_id and a.person_key < b.person_key
join {{ source('store', 'people') }} as pa on pa.person_key = a.person_key
join {{ source('store', 'people') }} as pb on pb.person_key = b.person_key
where pa.full_name <> pb.full_name
