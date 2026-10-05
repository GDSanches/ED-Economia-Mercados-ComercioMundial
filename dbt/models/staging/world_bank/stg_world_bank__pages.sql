-- Staging das páginas do World Bank.
-- Granularidade: uma linha por página, por run (a mesma da fonte).
-- Aqui só renomeamos, tipamos e extraímos o cabeçalho do JSON.
-- Ainda NÃO explodimos os registros: isso fica para a camada Silver.

with source as (

    select * from {{ source('world_bank', 'pages') }}

),

renamed as (

    select
        -- identificação do run
        run_id,
        dataset,
        indicator_id,

        -- paginação registrada no manifest
        page_number,
        pages_expected,

        -- cabeçalho da resposta da API (payload -> 0)
        (payload -> 0 ->> 'page')::int                     as api_page,
        (payload -> 0 ->> 'pages')::int                    as api_pages,
        (payload -> 0 ->> 'per_page')::int                 as api_per_page,
        (payload -> 0 ->> 'total')::int                    as api_total_records,
        nullif(payload -> 0 ->> 'lastupdated', '')::date   as api_last_updated_on,

        -- registros da página (payload -> 1); a API devolve null quando não há dados
        case
            when jsonb_typeof(payload -> 1) = 'array' then payload -> 1
            else '[]'::jsonb
        end                                                as records,

        -- resposta original, preservada para auditoria
        payload,

        -- linhagem
        source,
        source_url,
        object_key,
        extracted_at,
        loaded_at

    from source

),

final as (

    select
        run_id,
        dataset,
        indicator_id,
        page_number,
        pages_expected,
        api_page,
        api_pages,
        api_per_page,
        api_total_records,
        api_last_updated_on,
        records,
        jsonb_array_length(records) as records_count,
        payload,
        source,
        source_url,
        object_key,
        extracted_at,
        loaded_at

    from renamed

)

select * from final
