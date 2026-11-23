-- Cash on hand and debts owed by are stocks: the latest cycle with a weball row, not a sum.
with latest as (
    select person_key, cast(cycle as varchar) as cycle,
        sum(cash_on_hand) as cash_on_hand, sum(debts_owed_by) as debts_owed_by
    from {{ source('gold', 'self_funding_per_cycle') }}
    group by person_key, cycle
)
select people.person_key
from {{ source('gold', 'self_funding_people') }} as people
left join latest on latest.person_key = people.person_key
    and latest.cycle = people.cash_on_hand_cycle
where people.fec_candidate_ids <> '' and (
    people.cash_on_hand_career is distinct from latest.cash_on_hand
    or people.debts_owed_by_career is distinct from latest.debts_owed_by
    or people.self_funding_career
        is distinct from people.candidate_contributions_career + people.candidate_loans_career
)
