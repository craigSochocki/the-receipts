-- Competition ranks (1 + how many have more); unknown amounts get no rank.
select person_key,
    {{ competition_rank('total_accepted') }} as rank_total_accepted,
    {{ competition_rank('individual') }} as rank_individual,
    {{ competition_rank('corporate_pac') }} as rank_corporate_pac,
    {{ competition_rank('aipac_direct') }} as rank_aipac_direct,
    {{ competition_rank('udp_support') }} as rank_udp_support,
    {{ competition_rank('udp_opposing_opponents') }} as rank_udp_opposing_opponents,
    {{ competition_rank('udp_total_benefit') }} as rank_udp_total_benefit,
    {{ competition_rank('self_funding') }} as rank_self_funding,
    {{ competition_rank('all_ie_support') }} as rank_all_ie_support,
    {{ competition_rank('all_ie_oppose') }} as rank_all_ie_oppose,
    {{ competition_rank('all_ie_total') }} as rank_all_ie_total,
    {{ competition_rank('other_committees_total') }} as rank_other_committees_total
from {{ ref('person_money') }}
