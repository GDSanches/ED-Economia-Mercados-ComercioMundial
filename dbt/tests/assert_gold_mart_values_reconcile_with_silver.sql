-- Para cada indicador, a Gold tem exatamente os mesmos valores não nulos que a Silver:
-- a transformação para o formato largo não perdeu nem duplicou nenhum valor.
-- O teste falha se esta consulta devolver alguma linha.
{%- set indicators = world_bank_indicator_columns() %}

with silver as (

    select indicator_id, count(indicator_value) as values_count
    from {{ ref('world_bank_indicators') }}
    group by indicator_id

),

gold as (

    {%- for indicator in indicators %}
    select '{{ indicator.indicator_id }}' as indicator_id, count({{ indicator.column }}) as values_count
    from {{ ref('mart_economic_overview') }}
    {{ "union all" if not loop.last }}
    {%- endfor %}

)

select
    gold.indicator_id,
    silver.values_count as silver_values,
    gold.values_count   as gold_values
from gold
left join silver using (indicator_id)
where gold.values_count is distinct from silver.values_count
