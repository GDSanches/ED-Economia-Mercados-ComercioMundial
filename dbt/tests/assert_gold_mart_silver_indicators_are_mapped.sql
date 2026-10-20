-- Aviso quando a Silver tem um indicador que não foi mapeado para a Gold
-- (por exemplo, um indicador novo ingerido e esquecido aqui).
-- É warn, não error: nem todo indicador da Silver precisa ir para este mart.
{{ config(severity='warn') }}
{%- set indicators = world_bank_indicator_columns() %}

select distinct silver.indicator_id
from {{ ref('world_bank_indicators') }} as silver
where silver.indicator_id not in (
    {%- for indicator in indicators %}
    '{{ indicator.indicator_id }}'{{ "," if not loop.last }}
    {%- endfor %}
)
