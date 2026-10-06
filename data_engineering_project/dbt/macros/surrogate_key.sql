{#- Deterministic hash key over one or more columns (null-safe). -#}
{% macro surrogate_key(columns) -%}
    md5(
        {%- for column in columns %}
        coalesce(cast({{ column }} as varchar), '_null_')
        {%- if not loop.last %} || '|' || {% endif -%}
        {%- endfor %}
    )
{%- endmacro %}
