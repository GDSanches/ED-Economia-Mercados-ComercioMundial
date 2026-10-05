-- Observações do World Bank: o JSONB de cada página explodido em linhas.
-- Granularidade: uma linha por observação (entidade + indicador + ano), por run.
-- Todos os runs são mantidos; escolher o snapshot vigente é papel da Silver.

with pages as (

    -- Só páginas de indicador viram observações (o cadastro "countries" não tem indicador).
    select * from {{ ref('stg_world_bank__pages') }}
    where indicator_id is not null

),

exploded as (

    -- Cada elemento do array `records` vira uma linha.
    -- WITH ORDINALITY numera os elementos (1, 2, 3...) na ordem do JSON.
    select
        pages.run_id,
        pages.dataset,
        pages.indicator_id,
        pages.page_number,
        records.position_in_page,
        records.record,
        pages.source_url,
        pages.extracted_at,
        pages.loaded_at

    from pages
    cross join lateral jsonb_array_elements(pages.records)
        with ordinality as records(record, position_in_page)

),

typed as (

    select
        -- linhagem do run
        run_id,
        dataset,
        indicator_id,

        -- indicador segundo o próprio registro (deve bater com indicator_id)
        record -> 'indicator' ->> 'id'                       as record_indicator_id,
        record -> 'indicator' ->> 'value'                    as indicator_name,

        -- entidade: entity_wb_id (iso2) é a chave confiável para o cadastro.
        -- countryiso3code vem vazio para grupos de renda (ex.: "High income"),
        -- por isso fica só como informação bruta, e o entity_code final vem do cadastro.
        record -> 'country' ->> 'id'                         as entity_wb_id,
        nullif(record ->> 'countryiso3code', '')             as api_iso3_code,
        record -> 'country' ->> 'value'                      as entity_name,

        -- período: só aceita ano com 4 dígitos; outro formato vira NULL e é pego pelo teste
        case
            when record ->> 'date' ~ '^\d{4}$' then (record ->> 'date')::int
        end                                                  as year,

        -- valor medido: JSON null vira SQL NULL (ausência de observação, não zero)
        (record ->> 'value')::numeric                        as indicator_value,
        nullif(record ->> 'unit', '')                        as unit,
        nullif(record ->> 'obs_status', '')                  as obs_status,
        (record ->> 'decimal')::int                          as decimal_places,

        -- posição exata no bruto, para auditoria
        page_number,
        position_in_page,
        source_url,
        extracted_at,
        loaded_at

    from exploded

)

select * from typed
