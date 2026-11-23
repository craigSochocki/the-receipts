select count(*) as seats from {{ source('store', 'seats') }}
where not voting
having count(*) != 6
