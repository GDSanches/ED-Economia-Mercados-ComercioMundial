-- Silver: indicadores do World Bank no contrato final.
-- Granularidade: uma linha por entidade + indicador + ano (chave lógica do contrato).
-- Regra de snapshot: para cada indicador, vale o run completo mais recente.

with observations as (

    select * from {{ ref('int_world_bank_observations') }}

),

runs as (

    -- Um run por indicador, com o momento da extração.
    select
        indicator_id,
        run_id,
        max(extracted_at) as run_extracted_at
    from observations
    group by indicator_id, run_id

),

ranked_runs as (

    -- 1 = run mais recente do indicador. run_id desempata extrações simultâneas.
    select
        indicator_id,
        run_id,
        row_number() over (
            partition by indicator_id
            order by run_extracted_at desc, run_id desc
        ) as run_rank
    from runs

),

current_observations as (

    select observations.*
    from observations
    inner join ranked_runs
        on  ranked_runs.run_id = observations.run_id
        and ranked_runs.run_rank = 1

),

entities as (

    select * from {{ ref('int_world_bank_entities') }}

),

final as (

    select
        entities.entity_code::varchar(10)                     as entity_code,
        entities.entity_name::varchar(255)                    as entity_name,
        entities.entity_type::varchar(50)                     as entity_type,
        entities.iso3_code::varchar(3)                        as iso3_code,
        obs.indicator_id::varchar(50)                         as indicator_id,
        obs.year::integer                                     as year,
        obs.indicator_value::numeric(38, 15)                  as indicator_value,
        obs.run_id::varchar(36)                               as _run_id,
        obs.extracted_at                                      as _extracted_at,
        obs.source_url                                        as _source_url

    from current_observations as obs
    -- LEFT JOIN de propósito: entidade ausente do cadastro fica com entity_code NULL
    -- e a constraint NOT NULL derruba o build, em vez de a linha sumir em silêncio.
    -- A chave é o código de 2 caracteres (country.id = iso2Code), o único sempre presente.
    left join entities
        on entities.wb_iso2_code = obs.entity_wb_id

)

select * from final
