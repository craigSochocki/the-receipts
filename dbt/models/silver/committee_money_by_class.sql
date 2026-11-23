-- Counted committee money per candidate ID and cycle, by class and kind.
select candidate_id, cycle, committee_class, kind,
    sum(amount_cents)                                  as amount_cents,
    coalesce(sum(amount_cents) filter (is_earmark), 0) as earmark_cents
from {{ ref('counted_committee_money') }}
group by candidate_id, cycle, committee_class, kind
