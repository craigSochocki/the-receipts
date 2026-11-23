{# Seat IDs contested in an election year: every Senate seat, plus each state's
   House seats on the map in force that year (a new map replaces the old one). #}
{% macro seats_in_force(year) %}
    select seat_id from {{ source('store', 'seats') }}
    where chamber = 'Senate' or map_first_election = {{ year }}
       or (map_first_election < {{ year }}
           and state not in (select state from {{ source('store', 'seats') }}
                             where map_first_election = {{ year }}))
{% endmacro %}
