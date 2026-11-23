-- The double-count record is a source file; a change to it is a methodology change.
with groups as (
    select distinct person_key, cycle, kept_id, amount_cents
    from {{ source('store', 'double_counts') }}
)
select count(*) as group_count, sum(amount_cents) as amount_cents
from groups
having count(*) <> 90 or sum(amount_cents) <> 45177601534
