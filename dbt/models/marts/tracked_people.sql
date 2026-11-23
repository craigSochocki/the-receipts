-- The tracker's rows, in roster order. A person entered twice in the roster (two keys,
-- one FEC ID, one name) is one row, under the Bioguide-style key (a letter and six digits).
with roster as (
    select person_key, full_name, roster_position
    from {{ source('store', 'people') }}
    where roster_position is not null
),
keyed as (
    select person_key, candidate_id,
        (case when regexp_full_match(person_key, '[A-Za-z][0-9]{6}') then '0' else '1' end)
            || person_key as preference
    from {{ source('store', 'person_candidate_ids') }}
    where person_key in (select person_key from roster)
),
second_entries as (
    select later.person_key
    from keyed as later
    join keyed as kept on kept.candidate_id = later.candidate_id
        and kept.preference < later.preference
)
select * from roster
where person_key not in (select person_key from second_entries)
