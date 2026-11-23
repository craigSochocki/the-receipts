{# People (with an FEC ID) whose career column is not the sum of their per-cycle rows.
   `columns` is a list of [career column, per-cycle column] pairs. #}
{% macro career_mismatches(people, cycles, columns) %}
    with sums as (
        select person_key,
            {% for career, cycle in columns %}
            coalesce(sum({{ cycle }}), 0) as {{ career }}{% if not loop.last %},{% endif %}
            {% endfor %}
        from {{ cycles }}
        group by person_key
    )
    select people.person_key
    from {{ people }} as people
    left join sums using (person_key)
    where people.fec_candidate_ids <> '' and (
        {% for career, cycle in columns %}
        people.{{ career }} is distinct from coalesce(sums.{{ career }}, 0)
        {% if not loop.last %} or {% endif %}
        {% endfor %}
    )
{% endmacro %}
