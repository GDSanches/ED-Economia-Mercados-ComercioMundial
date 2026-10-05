-- O cabeçalho que a API devolveu precisa concordar com o que o manifest registrou.
-- O teste falha se esta consulta devolver alguma linha.
select
    run_id,
    dataset,
    page_number,
    api_page,
    pages_expected,
    api_pages
from {{ ref('stg_world_bank__pages') }}
where api_page <> page_number
   or api_pages <> pages_expected
