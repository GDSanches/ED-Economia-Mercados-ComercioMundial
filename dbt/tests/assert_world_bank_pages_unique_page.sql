-- Granularidade da fonte: uma página de um run aparece uma única vez.
-- O teste falha se esta consulta devolver alguma linha.
select
    run_id,
    dataset,
    page_number,
    count(*) as ocorrencias
from {{ source('world_bank', 'pages') }}
group by run_id, dataset, page_number
having count(*) > 1
