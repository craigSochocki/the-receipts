-- The money columns of total_accepted, per candidate ID and cycle.
-- individual_filed is weball as filed; individual counts each summary once.
with committee_money as (
    select candidate_id, cycle,
        sum(amount_cents) filter (committee_class = 'aipac')                    as aipac_pac_direct,
        sum(amount_cents) filter (committee_class = 'aipac' and is_earmark)     as aipac_earmark_transmitted,
        sum(amount_cents) filter (committee_class = 'corporate')                as corporate_pac,
        sum(amount_cents) filter (committee_class = 'corporate' and is_earmark) as corporate_earmark_transmitted
    from {{ ref('counted_committee_money') }}
    group by candidate_id, cycle
)
select candidate_id, cycle,
    coalesce(filed.individual_contributions_cents, 0)   as individual_filed,
    coalesce(summary.individual_contributions_cents, 0) as individual,
    coalesce(money.aipac_pac_direct, 0)                 as aipac_pac_direct,
    coalesce(money.aipac_earmark_transmitted, 0)        as aipac_earmark_transmitted,
    coalesce(money.corporate_pac, 0)                    as corporate_pac,
    coalesce(money.corporate_earmark_transmitted, 0)    as corporate_earmark_transmitted
from {{ source('store', 'counted_summaries') }} as summary
join {{ source('store', 'candidate_summaries') }} as filed using (candidate_id, cycle)
full outer join committee_money as money using (candidate_id, cycle)
