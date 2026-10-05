-- Entidades do World Bank (países e agregados), do snapshot mais recente do cadastro.
-- Granularidade: uma linha por entidade.

with pages as (

    select * from {{ ref('stg_world_bank__pages') }}
    where dataset = 'countries'

),

latest_run as (

    -- O cadastro também segue a regra de snapshot: só o run mais recente vale.
    select run_id
    from pages
    group by run_id
    order by max(extracted_at) desc, run_id desc
    limit 1

),

entities as (

    select
        record ->> 'id'                                       as entity_code,
        record ->> 'iso2Code'                                 as wb_iso2_code,
        record ->> 'name'                                     as entity_name,
        -- a API manda alguns nomes de região com espaço no final; trim evita comparação falhar
        trim(record -> 'region' ->> 'value') = 'Aggregates'   as is_aggregate,
        nullif(record -> 'region' ->> 'id', '')               as region_code,
        nullif(record -> 'adminregion' ->> 'id', '')          as admin_region_code,
        nullif(record -> 'incomeLevel' ->> 'id', '')          as income_level_code,
        nullif(record -> 'lendingType' ->> 'id', '')          as lending_type_code

    from pages
    inner join latest_run using (run_id)
    cross join lateral jsonb_array_elements(pages.records) as r(record)

),

aggregate_roles as (

    -- Um agregado ganha um tipo quando algum país aponta para ele.
    -- UNION (sem ALL) remove repetições, ex.: SAS é region e adminregion ao mesmo tempo.
    select region_code       as entity_code, 'REGION'        as entity_type from entities where not is_aggregate
    union
    select admin_region_code,                'REGION'                       from entities where not is_aggregate
    union
    select income_level_code,                'INCOME_GROUP'                 from entities where not is_aggregate
    union
    select lending_type_code,                'LENDING_GROUP'                from entities where not is_aggregate

),

final as (

    select
        entities.entity_code,
        entities.wb_iso2_code,
        entities.entity_name,
        case
            when not entities.is_aggregate then 'COUNTRY'
            else coalesce(aggregate_roles.entity_type, 'OTHER_AGGREGATE')
        end                                                   as entity_type,
        case
            when not entities.is_aggregate then entities.entity_code
        end                                                   as iso3_code

    from entities
    left join aggregate_roles
        on aggregate_roles.entity_code = entities.entity_code

)

select * from final
