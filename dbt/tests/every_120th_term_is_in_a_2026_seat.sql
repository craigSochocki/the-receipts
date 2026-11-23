select * from {{ source('store', 'terms') }}
where congress = 120 and seat_id not in ({{ seats_in_force(2026) }})
