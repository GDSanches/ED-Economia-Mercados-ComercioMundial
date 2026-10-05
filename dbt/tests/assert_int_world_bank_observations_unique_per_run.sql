-- Granularidade: dentro de um run, cada entidade + indicador + ano aparece uma vez.
-- O teste falha se esta consulta devolver alguma linha.
select
    run_id,
    indicator_id,
    entity_wb_id,
    year,
    count(*) as ocorrencias
from {{ ref('int_world_bank_observations') }}
group by run_id, indicator_id, entity_wb_id, year
having count(*) > 1
