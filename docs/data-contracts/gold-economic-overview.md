# Data Contract: Gold — `gold.mart_economic_overview`

## 1. Objetivo
Primeiro data mart da plataforma. Reúne os 8 indicadores macroeconômicos da Silver numa linha por entidade e ano, no formato que dashboards e APIs consomem: o perfil econômico de uma entidade num ano, numa única consulta.

| | Silver (`silver.world_bank_indicators`) | Gold (`gold.mart_economic_overview`) |
| :--- | :--- | :--- |
| Formato | Longo: uma linha por indicador | Largo: uma coluna por indicador |
| Grão | entidade + indicador + ano | **entidade + ano** |
| Pensado para | Catálogo flexível; novos indicadores sem mudar o schema | Consumo: perfil econômico, comparações, gráficos |

O formato longo continua sendo a fonte da verdade. A Gold é uma **projeção** dele para consumo e não acrescenta dado novo.

## 2. Grão e chave
- **Uma linha por entidade econômica e ano de referência.** "Entidade" inclui países e agregados (regiões, grupos de renda etc.), por isso o nome do modelo não fala em "país".
- **Chave primária:** `entity_code` + `year`.

## 3. Indicadores: significado, unidade e nome da coluna

A API do World Bank devolve o campo `unit` **vazio** para os 8 indicadores; a unidade só aparece no nome oficial. Por isso os nomes das colunas carregam a unidade, e onde existe mais de uma metodologia possível, a metodologia também.

**Padrão de nomes:** `<medida>_<unidade>`.

| `indicator_id` | Nome oficial (World Bank) | Coluna na Gold | Unidade |
| :--- | :--- | :--- | :--- |
| `NY.GDP.MKTP.CD` | GDP (current US$) | `gdp_current_usd` | US$ correntes |
| `NY.GDP.PCAP.CD` | GDP per capita (current US$) | `gdp_per_capita_current_usd` | US$ correntes por habitante |
| `NY.GDP.MKTP.KD.ZG` | GDP growth (annual %) | `gdp_growth_annual_pct` | % ao ano, a preços constantes |
| `FP.CPI.TOTL.ZG` | Inflation, consumer prices (annual %) | `inflation_cpi_annual_pct` | % ao ano, pelo índice de preços ao consumidor |
| `SL.UEM.TOTL.ZS` | Unemployment, total (% of total labor force) (modeled ILO estimate) | `unemployment_pct_labor_force` | % da força de trabalho (estimativa modelada da OIT) |
| `NE.EXP.GNFS.ZS` | Exports of goods and services (% of GDP) | `exports_pct_gdp` | % do PIB (bens e serviços) |
| `NE.IMP.GNFS.ZS` | Imports of goods and services (% of GDP) | `imports_pct_gdp` | % do PIB (bens e serviços) |
| `NY.GNP.PCAP.CD` | GNI per capita, Atlas method (current US$) | `gni_per_capita_atlas_usd` | US$ correntes, método Atlas |

### Diferenças em relação à proposta inicial

| Proposta | Definitivo | Motivo |
| :--- | :--- | :--- |
| `gdp_per_capita_usd` | `gdp_per_capita_current_usd` | O World Bank publica PIB per capita em US$ correntes, constantes e PPC. Sem "current", a coluna seria ambígua e inconsistente com `gdp_current_usd`. |
| `gni_per_capita_usd` | `gni_per_capita_atlas_usd` | O indicador usa o **método Atlas** (câmbio médio de 3 anos), que é diferente da conversão pelo câmbio do ano. É o valor que o World Bank usa para classificar países por renda, e não é comparável com uma RNB convertida de outra forma. |
| `gdp_growth_pct` | `gdp_growth_annual_pct` | Deixa explícito que é a variação anual. |
| `inflation_pct` | `inflation_cpi_annual_pct` | Existe outra medida de inflação no World Bank (deflator do PIB, `NY.GDP.DEFL.KD.ZG`). O nome indica qual é esta. |
| `unemployment_pct` | `unemployment_pct_labor_force` | Explicita a base do percentual (força de trabalho, não população). |

### Convenção dos percentuais
Os valores `_pct` estão em **pontos percentuais**, como a fonte publica: `4.37` significa 4,37%, e não 0,0437. Valores negativos são legítimos (recessão em `gdp_growth_annual_pct`, deflação em `inflation_cpi_annual_pct`).

## 4. Lógica da transformação

```
silver.world_bank_indicators          (uma linha por entidade + indicador + ano)
        │
        │ 1. manter só os indicadores mapeados na seção 3
        ▼
        │ 2. agrupar só pela chave do grão: entity_code + year
        ▼
        │ 3. em cada grupo, cada indicador vira uma coluna:
        │    "o valor da linha cujo indicator_id é X"
        ▼
        │ 4. buscar nome, tipo e iso3 no modelo canônico de entidades
        │    (int_world_bank_entities)
        ▼
        │ 5. descartar entidade/ano sem nenhum dos 8 valores
        ▼
gold.mart_economic_overview           (uma linha por entidade + ano)
```

### 4.1 Decisão: agregação condicional

Para cada coluna, o valor é escolhido dentro do grupo entidade/ano por uma agregação com filtro. O formato do SQL, apenas como ilustração:

```sql
select
    entity_code, year,
    max(indicator_value) filter (where indicator_id = 'NY.GDP.MKTP.CD') as gdp_current_usd,
    max(indicator_value) filter (where indicator_id = 'NY.GDP.PCAP.CD') as gdp_per_capita_current_usd,
    -- ... uma linha por indicador
from silver.world_bank_indicators
group by entity_code, year
```

**Por que `max`, se não há nada para maximizar?** Num `group by`, toda coluna que não está no agrupamento precisa de uma função de agregação. Aqui o `max` funciona só como **seletor**: a chave primária da Silver (`entity_code + indicator_id + year`) garante que, dentro de um grupo entidade/ano, existe **no máximo uma** linha para cada indicador. O filtro deixa passar uma única linha, e o `max` de um valor só é o próprio valor. Nada é escolhido entre alternativas e nada é perdido. `min` daria o mesmo resultado; `max` é só a convenção mais comum.

**Alternativas consideradas e descartadas:**

| Alternativa | Por que não |
| :--- | :--- |
| Um `join` por indicador (8 joins da Silver com ela mesma) | Lê a Silver 8 vezes e fica verboso. Com `inner join`, uma entidade/ano sem um dos indicadores **desapareceria** em silêncio; com `left join`, é preciso escolher uma "tabela base", e as entidades fora dela somem. |
| `crosstab` (extensão `tablefunc` do PostgreSQL) | Exige instalar uma extensão, a lista de colunas continua fixa, e o resultado não se encaixa bem num contrato do dbt. |
| `dbt_utils.pivot` | Acrescenta um pacote, e na forma comum descobre as colunas consultando os valores da Silver em tempo de execução. Um indicador novo na Silver criaria uma coluna nova na Gold **sem ninguém decidir**, quebrando o contrato. |

A agregação condicional lê a Silver uma vez, não depende de extensão nem de pacote, e deixa **explícita** a relação indicador → coluna.

### 4.2 Decisão: o mapeamento indicador → coluna é definido uma única vez

A relação da seção 3 fica numa lista no próprio modelo dbt (Jinja), e as 8 colunas são geradas a partir dela. Assim o mapeamento não é repetido no SQL, e mudar um indicador significa mudar **uma linha**.

**Duas proteções, porque o mapeamento é a parte mais frágil:**
1. **Todo indicador mapeado existe na Silver** (teste com severidade `error`). Um `indicator_id` digitado errado não quebra o SQL: produz uma coluna **inteira nula**, em silêncio.
2. **Todo indicador da Silver está mapeado** (teste com severidade `warn`). Um indicador novo ingerido e esquecido na Gold gera aviso. É `warn` porque nem todo indicador da Silver precisa necessariamente ir para este mart.

### 4.3 Decisão: atributos da entidade vêm do modelo canônico, não do agrupamento

O `group by` usa **só a chave do grão** (`entity_code`, `year`). Assim o modelo tem uma linha por entidade e ano **por construção**, qualquer que seja o conteúdo das colunas descritivas.

`entity_name`, `entity_type` e `iso3_code` são buscados depois, num `join` com `int_world_bank_entities`, o cadastro canônico do World Bank, que tem uma linha por entidade (testes `unique` em `entity_code`). Esse é o mesmo cadastro que a Silver usa para classificar as entidades.

**Por que não agrupar também pelos atributos:** se uma entidade aparecesse com dois nomes em indicadores diferentes (`Brazil` num, `Brasil` noutro), o agrupamento geraria **duas linhas** para a mesma entidade/ano, quebrando o grão. A chave primária física barraria a tabela, mas o pipeline inteiro pararia por causa de um atributo descritivo. Com os atributos vindos de uma fonte única, a divergência não chega a existir na Gold.

**Onde cada garantia está implementada:**

| Garantia | Onde | Como foi verificada |
| :--- | :--- | :--- |
| O `join` não duplica linhas | Testes `unique` e `not_null` em `entity_code` no cadastro (`_int_world_bank__models.yml`), que rodam antes da Gold no `dbt build` | 296 entidades, 296 códigos distintos |
| Entidade ausente do cadastro não passa | O `left join` mantém a linha com atributos nulos; o **contrato do dbt** cria a tabela com `NOT NULL` físico em `entity_name` e `entity_type` antes do `INSERT` | Simulação com o cadastro sem `BRA`: `null value in column "entity_name" ... violates not-null constraint` |
| Uma linha por entidade e ano | `group by entity_code, year` (por construção) e chave primária física | 15.183 linhas, 15.183 chaves distintas |

O `left join` em si **não falha**. Ele é escolhido justamente para **revelar** a entidade ausente (como uma linha com atributos nulos, que o contrato rejeita), em vez de descartá-la em silêncio, como faria um `inner join`.

### 4.4 Decisão: entidade/ano sem nenhum valor fica de fora

Na Silver, a grade é completa: toda entidade tem uma linha para cada ano e indicador, com `NULL` onde não houve medição. Na Gold, uma linha com os 8 indicadores nulos não traz informação. A **ausência da linha** comunica o mesmo ("não há dados para esta entidade neste ano") sem gerar ruído em dashboards e APIs.

Linhas com **pelo menos um** valor são mantidas, e os indicadores ausentes continuam `NULL`, nunca `0` (RNF04).

Na primeira versão (outubro de 2026), a regra removeu **2.373** das 17.556 combinações entidade/ano da Silver, e a Gold ficou com **15.183** linhas, das quais 6.558 têm os 8 indicadores preenchidos.

### 4.5 Decisão: linhagem e atualização

Na Silver, cada indicador vem do seu próprio snapshot (`_run_id`). Uma linha da Gold reúne 8 indicadores, que podem vir de **runs diferentes**: depois de uma ingestão parcial, por exemplo, o desemprego mantém o snapshot anterior enquanto os demais são atualizados. Por isso a Gold **não tem um `_run_id` único**.

- **Coluna `_oldest_extracted_at`:** a extração **mais antiga** entre as linhas da Silver daquela entidade/ano. Responde "quão atualizada está esta linha, no pior caso?".
  - Como a grade da Silver é completa, o cálculo cobre normalmente os 8 indicadores, **inclusive os que vieram nulos**: a ausência do valor também foi extraída naquele run.
  - **Não é indicador de completude.** Na primeira versão, 8.625 das 15.183 linhas (57%) tinham pelo menos um indicador sem valor. Para saber quais indicadores estão disponíveis, olhe as colunas nulas da linha.
- **Rastreabilidade até o bruto (RNF03):** um valor da Gold é localizado na Silver pela chave `entity_code + year + indicator_id`. Lá estão `_run_id`, `_extracted_at` e `_source_url`, que levam ao arquivo no MinIO.

## 5. Contrato

| Campo | Tipo | Obrigatório? | Descrição |
| :--- | :--- | :---: | :--- |
| `entity_code` | VARCHAR(10) | Sim | Código da entidade no World Bank. *[Chave]* |
| `entity_name` | VARCHAR(255) | Sim | Nome oficial da entidade. |
| `entity_type` | VARCHAR(50) | Sim | `COUNTRY`, `REGION`, `INCOME_GROUP`, `LENDING_GROUP` ou `OTHER_AGGREGATE`. |
| `iso3_code` | VARCHAR(3) | Não | Preenchido se e somente se `entity_type = 'COUNTRY'`. |
| `year` | INTEGER | Sim | Ano de referência. *[Chave]* |
| `gdp_current_usd` | NUMERIC(20,2) | Não | Ver seção 3. |
| `gdp_per_capita_current_usd` | NUMERIC(12,2) | Não | Ver seção 3. |
| `gdp_growth_annual_pct` | NUMERIC(9,4) | Não | Ver seção 3. |
| `inflation_cpi_annual_pct` | NUMERIC(12,4) | Não | Ver seção 3. |
| `unemployment_pct_labor_force` | NUMERIC(7,4) | Não | Ver seção 3. |
| `exports_pct_gdp` | NUMERIC(9,4) | Não | Ver seção 3. |
| `imports_pct_gdp` | NUMERIC(9,4) | Não | Ver seção 3. |
| `gni_per_capita_atlas_usd` | NUMERIC(12,2) | Não | Ver seção 3. |
| `_oldest_extracted_at` | TIMESTAMPTZ | Sim | Extração mais antiga entre os indicadores da linha. |

- **Materialização:** tabela, no schema `gold`, reconstruída a cada `dbt build` (mesma estratégia da Silver).
- **Contrato do dbt aplicado** (`contract: enforced`), com chave primária (`entity_code`, `year`) e a mesma regra de `iso3_code` da Silver como `CHECK`.
### 5.1 Critério dos tipos numéricos

A Silver guarda o valor como a fonte entregou (`NUMERIC(38,15)`), para preservar a linhagem. A Gold é a camada de consumo, e cada coluna tem uma precisão escolhida para o que ela representa:

- **Escala (casas decimais):**
  - **US$: 2 casas** (centavos). O maior erro de arredondamento observado foi de meio centavo, num PIB de até 118 trilhões.
  - **Pontos percentuais: 4 casas.** O maior erro observado foi de 0,00005 p.p. A fonte declara 1 casa de exibição (campo `decimal` da API), e o restante do valor bruto é ruído de ponto flutuante (ex.: `0.600000000000065`). Com 4 casas, só 1 entre cerca de 57 mil valores não nulos vira zero (uma inflação de 0,0000011%); com 2 casas seriam 8.
- **Precisão (total de dígitos):** dimensionada pelo maior valor observado de cada indicador, com folga para o crescimento natural da série:

| Coluna | Maior valor observado | Tipo | Limite |
| :--- | :--- | :--- | :--- |
| `gdp_current_usd` | 1,18 × 10¹⁴ (World, 15 dígitos) | NUMERIC(20,2) | até 10¹⁸ |
| `gdp_per_capita_current_usd` | 288.001 | NUMERIC(12,2) | até 10¹⁰ |
| `gni_per_capita_atlas_usd` | 139.370 | NUMERIC(12,2) | até 10¹⁰ |
| `gdp_growth_annual_pct` | entre −64 e 150 | NUMERIC(9,4) | ±99.999 |
| `inflation_cpi_annual_pct` | 23.773 (hiperinflação) | NUMERIC(12,4) | ±99.999.999 |
| `unemployment_pct_labor_force` | 38,8 (limitado a 100 por definição) | NUMERIC(7,4) | ±999 |
| `exports_pct_gdp` / `imports_pct_gdp` | 434 | NUMERIC(9,4) | ±99.999 |

O valor da Gold é, portanto, `round(valor da Silver, escala da coluna)`. Um valor maior que o limite faz o build falhar (`numeric field overflow`), em vez de ser truncado em silêncio.

## 6. Regras de qualidade
- **Chave única** `entity_code + year` (constraint de chave primária).
- **Reconciliação com a Silver:** para cada indicador, a quantidade de valores não nulos na Gold é igual à da Silver. Garante que a transformação não perdeu nem duplicou nenhum valor. Na primeira versão, também foi feita uma comparação célula a célula (`gold = round(silver, escala)`): 121.464 células, 0 divergências.
- **Cobertura do mapeamento:** os dois testes da seção 4.2.
- **Linha não vazia:** nenhuma linha da Gold tem os 8 indicadores nulos (seção 4.4).

## 7. Fora do escopo desta versão
- **Métricas derivadas**, como balança comercial (`exports_pct_gdp - imports_pct_gdp`) ou variações calculadas. Elas exigem definições próprias (por exemplo, o que fazer quando um dos lados é nulo) e entram num modelo posterior, sobre esta Gold.
- **Indicadores de outras fontes** (IMF, UN Comtrade). O mart foi desenhado para receber novas colunas via mapeamento, mas a integração entre fontes é outro ticket.
- **Classificação histórica das entidades:** `entity_type` reflete o cadastro atual do World Bank (ver GEDP-TD-001).
