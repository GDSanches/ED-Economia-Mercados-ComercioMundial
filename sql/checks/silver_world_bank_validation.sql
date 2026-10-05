-- Validação da Silver do World Bank após a expansão Brasil → mundo (GEDP-TD-001).
-- Uso: docker exec -i postgres psql -U app -d appdb < sql/checks/silver_world_bank_validation.sql
-- As seções "CHECK" devem devolver violacoes = 0 (ou nenhuma linha, quando indicado).

\echo '== 1. Métricas gerais'
SELECT
    count(DISTINCT entity_code)                                         AS total_entidades,
    count(DISTINCT entity_code) FILTER (WHERE entity_type = 'COUNTRY')  AS total_paises,
    count(DISTINCT entity_code) FILTER (WHERE entity_type <> 'COUNTRY') AS total_agregados,
    count(*)                                                            AS total_observacoes,
    count(indicator_value)                                              AS com_valor,
    count(*) - count(indicator_value)                                   AS sem_valor,
    min(year)                                                           AS ano_min,
    max(year)                                                           AS ano_max
FROM silver.world_bank_indicators;

\echo '== 2. Observações por indicador'
SELECT
    indicator_id,
    count(*)                                                   AS observacoes,
    count(DISTINCT entity_code)                                AS entidades,
    count(DISTINCT year)                                       AS anos,
    count(indicator_value)                                     AS com_valor,
    round(100.0 * count(indicator_value) / count(*), 1)        AS pct_preenchido,
    count(DISTINCT _run_id)                                    AS runs
FROM silver.world_bank_indicators
GROUP BY indicator_id
ORDER BY indicator_id;

\echo '== 3. Observações por entity_type'
SELECT
    entity_type,
    count(DISTINCT entity_code)                                AS entidades,
    count(*)                                                   AS observacoes,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)         AS pct_observacoes
FROM silver.world_bank_indicators
GROUP BY entity_type
ORDER BY observacoes DESC;

\echo '== 4. CHECK regra do iso3_code por entity_type (violacoes = 0)'
SELECT
    entity_type,
    count(*)                                                   AS observacoes,
    count(iso3_code)                                           AS iso3_preenchido,
    count(*) - count(iso3_code)                                AS iso3_nulo,
    CASE WHEN entity_type = 'COUNTRY' THEN 'iso3 preenchido' ELSE 'iso3 NULL' END AS regra,
    CASE
        WHEN entity_type = 'COUNTRY' THEN count(*) - count(iso3_code)
        ELSE count(iso3_code)
    END                                                        AS violacoes
FROM silver.world_bank_indicators
GROUP BY entity_type
ORDER BY entity_type;

\echo '== 5. CHECK iso3_code dos países tem 3 letras e é igual ao entity_code (violacoes = 0)'
SELECT count(*) AS violacoes
FROM silver.world_bank_indicators
WHERE entity_type = 'COUNTRY'
  AND (iso3_code !~ '^[A-Z]{3}$' OR iso3_code <> entity_code);

\echo '== 6. CHECK unicidade de entity_code + indicator_id + year (violacoes = 0)'
SELECT
    count(*)                                                   AS linhas,
    count(DISTINCT (entity_code, indicator_id, year))          AS chaves_distintas,
    count(*) - count(DISTINCT (entity_code, indicator_id, year)) AS violacoes
FROM silver.world_bank_indicators;

\echo '== 6b. Chaves duplicadas, se houver (esperado: nenhuma linha)'
SELECT entity_code, indicator_id, year, count(*) AS ocorrencias
FROM silver.world_bank_indicators
GROUP BY entity_code, indicator_id, year
HAVING count(*) > 1
LIMIT 20;

\echo '== 7. CHECK uma entidade tem um único tipo e um único nome (violacoes = 0)'
SELECT count(*) AS violacoes
FROM (
    SELECT entity_code
    FROM silver.world_bank_indicators
    GROUP BY entity_code
    HAVING count(DISTINCT entity_type) > 1 OR count(DISTINCT entity_name) > 1
) AS t;

\echo '== 8. CHECK grade completa: cada entidade tem todos os anos em cada indicador (violacoes = 0)'
WITH anos AS (
    SELECT indicator_id, count(DISTINCT year) AS anos_indicador
    FROM silver.world_bank_indicators
    GROUP BY indicator_id
)
SELECT count(*) AS violacoes
FROM (
    SELECT s.indicator_id, s.entity_code, count(*) AS anos_entidade, a.anos_indicador
    FROM silver.world_bank_indicators AS s
    JOIN anos AS a USING (indicator_id)
    GROUP BY s.indicator_id, s.entity_code, a.anos_indicador
    HAVING count(*) <> a.anos_indicador
) AS t;

\echo '== 9. CHECK reconciliação: Silver = run vigente no intermediário, por indicador (violacoes = 0)'
WITH silver AS (
    SELECT indicator_id, _run_id, count(*) AS linhas_silver
    FROM silver.world_bank_indicators
    GROUP BY indicator_id, _run_id
),
origem AS (
    SELECT indicator_id, run_id::text AS run_id, count(*) AS linhas_origem
    FROM analytics.int_world_bank_observations
    GROUP BY indicator_id, run_id
)
SELECT
    silver.indicator_id,
    silver.linhas_silver,
    origem.linhas_origem,
    (silver.linhas_silver <> coalesce(origem.linhas_origem, -1))::int AS violacoes
FROM silver
LEFT JOIN origem
    ON origem.indicator_id = silver.indicator_id
   AND origem.run_id = silver._run_id
ORDER BY silver.indicator_id;

\echo '== 10. CHECK cobertura do cadastro: toda entidade da Silver existe no cadastro (violacoes = 0)'
SELECT count(DISTINCT s.entity_code) AS violacoes
FROM silver.world_bank_indicators AS s
LEFT JOIN analytics.int_world_bank_entities AS e
    ON e.entity_code = s.entity_code
WHERE e.entity_code IS NULL;

\echo '== 11. Informativo: entidades do cadastro sem nenhuma observação na Silver'
SELECT e.entity_type, count(*) AS entidades_sem_dados, string_agg(e.entity_code, ', ' ORDER BY e.entity_code) AS codigos
FROM analytics.int_world_bank_entities AS e
LEFT JOIN (SELECT DISTINCT entity_code FROM silver.world_bank_indicators) AS s
    ON s.entity_code = e.entity_code
WHERE s.entity_code IS NULL
GROUP BY e.entity_type
ORDER BY e.entity_type;
