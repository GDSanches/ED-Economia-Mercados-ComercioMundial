{#
    Por padrão, o dbt junta o schema do profile com o schema customizado
    (analytics + silver = "analytics_silver"). Esta versão usa o schema
    customizado exatamente como escrito, e o do profile quando não há nenhum.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
