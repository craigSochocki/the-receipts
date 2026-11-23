select seat_id, count(*) as members from {{ source('store', 'terms') }}
where congress = 120
group by seat_id
having count(*) > 1
