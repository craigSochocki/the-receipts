-- Committee contributions that count: not voided, not a repeat, from a registered committee.
select money.*, registry.committee_class, registry.kind
from {{ source('store', 'committee_contributions') }} as money
join {{ source('store', 'committees') }} as registry using (committee_id, cycle)
where money.excluded_because is null
