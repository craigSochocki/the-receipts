{# 1 + the number of people with a larger amount; NULL for an unknown amount. #}
{% macro competition_rank(column) %}
    case when {{ column }} is not null then rank() over (order by {{ column }} desc nulls last) end
{% endmacro %}
