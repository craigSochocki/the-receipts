-- Until the dataset is assembled from these marts, they must agree with it to the cent.
with published as (
    select person_key,
        round(try_cast(total_accepted_career as double) * 100) as total_accepted,
        round(try_cast(dirty_career as double) * 100) as dirty,
        rank_total_accepted, rank_individual, rank_corporate_pac, rank_aipac_direct, rank_udp_support, rank_udp_opposing_opponents, rank_udp_total_benefit, rank_self_funding, rank_all_ie_support, rank_all_ie_oppose, rank_all_ie_total, rank_other_committees_total
    from read_json_auto('{{ env_var("RECEIPTS_DATASET", "congress-money-tracker.json") }}')
)
select coalesce(published.person_key, money.person_key) as person_key
from published
full outer join {{ ref('person_money') }} as money using (person_key)
left join {{ ref('person_ranks') }} as ranks using (person_key)
where published.person_key is null or money.person_key is null
   or published.total_accepted is distinct from money.total_accepted
   or published.dirty is distinct from money.dirty
   or published.rank_total_accepted is distinct from ranks.rank_total_accepted
   or published.rank_individual is distinct from ranks.rank_individual
   or published.rank_corporate_pac is distinct from ranks.rank_corporate_pac
   or published.rank_aipac_direct is distinct from ranks.rank_aipac_direct
   or published.rank_udp_support is distinct from ranks.rank_udp_support
   or published.rank_udp_opposing_opponents is distinct from ranks.rank_udp_opposing_opponents
   or published.rank_udp_total_benefit is distinct from ranks.rank_udp_total_benefit
   or published.rank_self_funding is distinct from ranks.rank_self_funding
   or published.rank_all_ie_support is distinct from ranks.rank_all_ie_support
   or published.rank_all_ie_oppose is distinct from ranks.rank_all_ie_oppose
   or published.rank_all_ie_total is distinct from ranks.rank_all_ie_total
   or published.rank_other_committees_total is distinct from ranks.rank_other_committees_total
