{# An amount for a person with an FEC candidate ID; NULL (unknown) for one without. #}
{% macro known(amount) %}
    case when accepted.fec_candidate_ids <> '' then {{ amount }} end
{% endmacro %}
