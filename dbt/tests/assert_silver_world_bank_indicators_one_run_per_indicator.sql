-- A Silver deve conter exatamente um run (o mais recente) por indicador.
-- O teste falha se esta consulta devolver alguma linha.
select
    indicator_id,
    count(distinct _run_id) as runs
from {{ ref('world_bank_indicators') }}
group by indicator_id
having count(distinct _run_id) <> 1
