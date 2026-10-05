-- O indicador dentro de cada registro deve ser o mesmo que a página pediu à API.
-- O teste falha se esta consulta devolver alguma linha.
select
    run_id,
    indicator_id,
    record_indicator_id,
    year
from {{ ref('int_world_bank_observations') }}
where record_indicator_id is distinct from indicator_id
