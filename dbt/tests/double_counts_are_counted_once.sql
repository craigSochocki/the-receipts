-- Each recorded double count: the dropped copy counts $0 of individual money, the kept copy the
-- recorded amount.
select double_counts.person_key, double_counts.cycle, double_counts.dropped_id
from {{ source('store', 'double_counts') }} as double_counts
left join {{ source('gold', 'accepted_money_per_cycle') }} as dropped
    on dropped.person_key = double_counts.person_key
    and dropped.cycle = double_counts.cycle
    and dropped.candidate_id = double_counts.dropped_id
left join {{ source('gold', 'accepted_money_per_cycle') }} as kept
    on kept.person_key = double_counts.person_key
    and kept.cycle = double_counts.cycle
    and kept.candidate_id = double_counts.kept_id
where dropped.individual is distinct from 0
    or kept.individual is distinct from double_counts.amount_cents
