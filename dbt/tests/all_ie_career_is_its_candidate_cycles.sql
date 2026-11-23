-- A person's all-IE career totals are the sums over their candidate IDs and cycles.
with sums as (
    select ids.person_key,
        coalesce(sum(spending.all_ie_support), 0) as support,
        coalesce(sum(spending.all_ie_oppose), 0) as oppose,
        coalesce(sum(spending.all_ie_total), 0) as total
    from {{ source('store', 'person_candidate_ids') }} as ids
    left join {{ source('gold', 'all_ie_per_candidate_cycle') }} as spending using (candidate_id)
    group by ids.person_key
)
select people.person_key
from {{ source('gold', 'all_ie_people') }} as people
left join sums using (person_key)
where people.fec_candidate_ids <> '' and (
    people.all_ie_support_career is distinct from coalesce(sums.support, 0)
    or people.all_ie_oppose_career is distinct from coalesce(sums.oppose, 0)
    or people.all_ie_total_career is distinct from coalesce(sums.total, 0)
)
