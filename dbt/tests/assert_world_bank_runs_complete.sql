-- Todo run carregado deve ter todas as páginas que o manifest prometeu.
-- O teste falha se esta consulta devolver alguma linha.
select
    run_id,
    dataset,
    count(*)            as paginas_carregadas,
    max(pages_expected) as paginas_esperadas
from {{ source('world_bank', 'pages') }}
group by run_id, dataset
having count(*) <> max(pages_expected)
