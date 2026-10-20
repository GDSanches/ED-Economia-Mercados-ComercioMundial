-- Nenhuma linha da Gold pode ter todos os indicadores nulos (seção 4.4 do contrato).
-- O teste falha se esta consulta devolver alguma linha.
{%- set indicators = world_bank_indicator_columns() %}

select entity_code, year
from {{ ref('mart_economic_overview') }}
where num_nonnulls(
    {%- for indicator in indicators %}
    {{ indicator.column }}{{ "," if not loop.last }}
    {%- endfor %}
) = 0
