-- Career money per tracked person, in cents. NULL means unknown: with no FEC candidate ID
-- there is nothing to search, so every amount is unknown rather than zero.
with credits as (
    select credited_to as person_key, sum(credit) as credit
    from {{ source('gold', 'opposition_credits') }}
    group by credited_to
),
money as (
    select people.person_key, people.roster_position,
        {{ known('accepted.individual_contribution_total_career') }} as individual,
        {{ known('accepted.corporate_pac_career') }} as corporate_pac,
        {{ known('accepted.aipac_pac_direct_career') }} as aipac_direct,
        {{ known('udp.udp_ie_support_career') }} as udp_support,
        {{ known('coalesce(credits.credit, 0)') }} as udp_opposing_opponents,
        {{ known('self_funding.self_funding_career') }} as self_funding,
        {{ known('ie.all_ie_support_career') }} as all_ie_support,
        {{ known('ie.all_ie_oppose_career') }} as all_ie_oppose,
        {{ known('ie.all_ie_total_career') }} as all_ie_total,
        {{ known('committees.other_committees_total_career') }} as other_committees_total
    from {{ ref('tracked_people') }} as people
    join {{ source('gold', 'accepted_money_people') }} as accepted using (person_key)
    join {{ source('gold', 'udp_people') }} as udp using (person_key)
    join {{ source('gold', 'self_funding_people') }} as self_funding using (person_key)
    join {{ source('gold', 'all_ie_people') }} as ie using (person_key)
    join {{ source('gold', 'other_committees_people') }} as committees using (person_key)
    left join credits using (person_key)
)
select *,
    individual + corporate_pac + aipac_direct as total_accepted,
    udp_support + udp_opposing_opponents as udp_total_benefit,
    corporate_pac + aipac_direct + udp_support + udp_opposing_opponents as dirty
from money
