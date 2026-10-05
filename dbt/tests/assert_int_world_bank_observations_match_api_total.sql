-- A explosão não pode perder nem inventar linhas:
-- o total de observações de cada run tem que bater com o total informado pela API.
-- O teste falha se esta consulta devolver alguma linha.
with observed as (

    select run_id, count(*) as observations
    from {{ ref('int_world_bank_observations') }}
    group by run_id

),

expected as (

    select run_id, max(api_total_records) as api_total_records
    from {{ ref('stg_world_bank__pages') }}
    where indicator_id is not null   -- o cadastro (countries) não gera observações
    group by run_id

)

select
    expected.run_id,
    expected.api_total_records,
    coalesce(observed.observations, 0) as observations
from expected
left join observed on observed.run_id = expected.run_id
where coalesce(observed.observations, 0) <> expected.api_total_records
