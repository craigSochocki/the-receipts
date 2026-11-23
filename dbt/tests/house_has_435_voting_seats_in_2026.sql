select count(*) as seats from {{ source('store', 'seats') }}
where chamber = 'House' and voting and seat_id in ({{ seats_in_force(2026) }})
having count(*) != 435
