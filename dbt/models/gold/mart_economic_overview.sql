-- Gold: perfil econômico por entidade e ano.
-- Granularidade: uma linha por entidade + ano (formato largo: uma coluna por indicador).
-- Lógica e decisões: docs/data-contracts/gold-economic-overview.md (seção 4).

{%- set indicators = world_bank_indicator_columns() %}

with indicators as (

    -- 1. Só os indicadores mapeados para este mart.
    select *
    from {{ ref('world_bank_indicators') }}
    where indicator_id in (
        {%- for indicator in indicators %}
        '{{ indicator.indicator_id }}'{{ "," if not loop.last }}
        {%- endfor %}
    )

),

pivoted as (

    -- 2 e 3. Um grupo por entidade + ano; cada indicador vira uma coluna.
    -- O group by usa só a chave do grão: o resultado tem uma linha por entidade + ano
    -- por construção, mesmo que atributos descritivos divirjam entre indicadores.
    -- O max() só seleciona: a chave da Silver (entity_code + indicator_id + year)
    -- garante no máximo uma linha por indicador dentro de cada grupo.
    select
        entity_code,
        year,
        {%- for indicator in indicators %}
        max(indicator_value) filter (
            where indicator_id = '{{ indicator.indicator_id }}'
        )                                               as {{ indicator.column }},
        {%- endfor %}
        -- Cada indicador pode vir de um run diferente: a extração mais antiga entre
        -- as linhas da Silver do grupo diz quão atualizada a linha está no pior caso.
        -- Indicadores nulos também contam (a ausência foi extraída naquele run).
        -- Não indica completude: uma linha pode ter indicadores sem valor.
        min(_extracted_at)                              as _oldest_extracted_at

    from indicators
    group by entity_code, year

),

entities as (

    -- Atributos descritivos vêm do modelo canônico de entidades (uma linha por entidade),
    -- e não das linhas de cada indicador.
    select * from {{ ref('int_world_bank_entities') }}

),

final as (

    select
        pivoted.entity_code::varchar(10)                as entity_code,
        entities.entity_name::varchar(255)              as entity_name,
        entities.entity_type::varchar(50)               as entity_type,
        entities.iso3_code::varchar(3)                  as iso3_code,
        pivoted.year,
        {%- for indicator in indicators %}
        -- O cast arredonda para a escala escolhida para a coluna (ver a macro).
        pivoted.{{ indicator.column }}::{{ indicator.data_type }} as {{ indicator.column }},
        {%- endfor %}
        pivoted._oldest_extracted_at

    from pivoted
    -- LEFT JOIN: uma entidade ausente do cadastro fica com atributos nulos, em vez de a
    -- linha sumir em silêncio. O join em si não falha: quem barra é o contrato do dbt
    -- (_gold__models.yml), que cria a tabela com NOT NULL físico em entity_name e
    -- entity_type antes do INSERT. A unicidade de entity_code no cadastro (que impede
    -- este join de duplicar linhas) é testada em _int_world_bank__models.yml.
    left join entities
        on entities.entity_code = pivoted.entity_code
    -- 4. Entidade/ano sem nenhum dos indicadores não traz informação.
    where num_nonnulls(
        {%- for indicator in indicators %}
        pivoted.{{ indicator.column }}{{ "," if not loop.last }}
        {%- endfor %}
    ) > 0

)

select * from final
