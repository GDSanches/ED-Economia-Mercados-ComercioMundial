-- Todo indicador mapeado para a Gold precisa existir na Silver.
-- Um indicator_id digitado errado não quebra o SQL: gera uma coluna inteira nula, em silêncio.
-- O teste falha se esta consulta devolver alguma linha.
{%- set indicators = world_bank_indicator_columns() %}

with mapped as (

    {%- for indicator in indicators %}
    select '{{ indicator.indicator_id }}' as indicator_id
    {{ "union all" if not loop.last }}
    {%- endfor %}

),

silver as (

    select distinct indicator_id
    from {{ ref('world_bank_indicators') }}

)

select mapped.indicator_id
from mapped
left join silver using (indicator_id)
where silver.indicator_id is null
