select count(*) as seats from {{ source('store', 'seats') }}
where chamber = 'Senate'
having count(*) != 100
