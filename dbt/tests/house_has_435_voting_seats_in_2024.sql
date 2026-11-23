select count(*) as seats from {{ source('store', 'seats') }}
where chamber = 'House' and voting and map_first_election = 2024
having count(*) != 435
