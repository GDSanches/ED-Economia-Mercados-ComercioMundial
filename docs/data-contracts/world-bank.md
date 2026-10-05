# Data Contract: World Bank - Indicadores Econômicos (PIB)

## 1. Visão Geral
- **Fonte:** World Bank (Banco Mundial)
- **Domínio:** Economia
- **Dataset Específico:** GDP (Current US$) - Produto Interno Bruto em Dólares Atuais.
- **Indicator ID:** `NY.GDP.MKTP.CD`
- **Endpoint da API:** `https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=1000`

## 2. Granularidade, Entidades e Chaves
O World Bank não retorna apenas países isolados, mas também agregados econômicos e geográficos (ex: "Arab World", "Euro area"). Utilizar exclusivamente um código ISO-3 como chave primária é conceitualmente incorreto.

- **O que representa uma linha?** O valor de um indicador para uma entidade (país ou região) em um ano específico.
- **Granularidade:** Entidade-Ano-Indicador.
- **Modelo de Entidades:** Adotaremos um modelo genérico de `entity`.
  - `entity_code`: O código fornecido pelo World Bank (ex: `BRA`, `ARB`).
  - `entity_type`: Classificação lógica (ex: `COUNTRY`, `REGION`, `INCOME_GROUP`).
  - `iso3_code`: O código ISO-3 real, que será preenchido para países e `NULL` para agregados.
- **Chave Lógica (Primary Key):** `entity_code` + `year` + `indicator_id`

### 2.1 Resolução de entidades (cadastro do World Bank)
As entidades são resolvidas pelo cadastro oficial do World Bank (`/v2/country`), ingerido como o dataset `countries` pelo mesmo fluxo dos indicadores (MinIO → `raw_staging` → dbt `int_world_bank_entities`).

- **Chave de ligação:** o `country.id` de cada observação (2 caracteres, ex.: `BR`, `XD`) é igual ao `iso2Code` do cadastro. O `countryiso3code` das observações **não** é usado como chave: ele vem vazio para os grupos de renda (ex.: `High income`).
- **`entity_code`:** o `id` do cadastro (ex.: `BRA`, `HIC`, `EAS`).
- **`entity_type`:**
  - `COUNTRY`: entidade cuja região não é `Aggregates`;
  - `REGION`: agregado citado como `region` ou `adminregion` por algum país;
  - `INCOME_GROUP`: agregado citado como `incomeLevel` por algum país;
  - `LENDING_GROUP`: agregado citado como `lendingType` por algum país;
  - `OTHER_AGGREGATE`: demais agregados (ex.: `WLD`, `ARB`, `EUU`).
- **Snapshot:** vale o run `completed` mais recente do cadastro.
- **Entidade desconhecida:** uma observação cujo `country.id` não exista no cadastro reprova o teste `relationships` e impede a construção da Silver.
- **Limitação conhecida:** o World Bank usa códigos que não são ISO-3 oficiais para alguns países (ex.: `XKX` Kosovo, `CHI` Ilhas do Canal); eles aparecem em `iso3_code` como estão no cadastro.

## 3. Estratégia de Paginação
A ingestão não assumirá que o dataset inteiro cabe em uma única requisição. 
1. O script Python fará a requisição da página 1.
2. Lerá os metadados do cabeçalho da resposta para identificar o parâmetro `pages` (total de páginas).
3. Executará um loop iterando sobre todas as páginas disponíveis.
4. Cada página será salva independentemente na camada Bronze antes de qualquer união ou transformação, garantindo a fidelidade absoluta da extração original.

## 4. Estratégia de Ingestão e Controle de Execução
Adotaremos a **Estratégia de Preservação de Snapshots (Run-based)**.

- **Caminho Bronze:** `s3://bronze/world_bank/{dataset}/year=YYYY/month=MM/day=DD/run_id=UUID/page=N.json`
- Cada indicador configurado é ingerido como um dataset independente. Para este contrato de PIB, `{dataset}` é `gdp`; os demais indicadores usam seus próprios nomes de dataset definidos em `src/ingestion/world_bank/config.py`.
- **Controle de Execução (Run Manifest):** Existirá um arquivo `manifest.json` (ou tabela de controle na orquestração) acompanhando o diretório, que registrará o status da extração (ex: `started`, `failed`, `completed`).
- **Justificativa:** Dados macroeconômicos sofrem revisões retroativas constantes. Sobrescrever um arquivo inviabiliza a auditoria de *quando* o Banco Mundial alterou o passado. Criar um diretório particionado por `run_id` isola cada execução, gerando snapshots imutáveis. Isso permite o reprocessamento rastreável de qualquer ponto no tempo. A idempotência, por sua vez, ocorrerá na ingestão da camada Silver: reprocessar ou reingerir um mesmo `run_id` não duplicará os registros graças ao *Upsert* (merge) na chave lógica.
- **Regra de Avanço:** Somente *runs* cujo manifest/status for explicitamente `completed` (onde todas as páginas foram extraídas sem erros) poderão alimentar as camadas seguintes.

## 5. Fluxo de Transformação e Responsabilidades
- **Ingestão (Python):** Extrai da API com paginação e salva os arquivos JSON crus no MinIO (Bronze) registrando o manifest.
- **Carga (Python/Polars):** Lê o snapshot do MinIO referente ao `run_id` mais recente com status `completed` e faz um *Copy* para a tabela `raw_staging` no PostgreSQL.
  - **O que representa uma linha em `raw_staging`:** Uma linha corresponde estritamente a um objeto JSON retornado no array da API armazenado em uma coluna `JSONB` (ou texto bruto), acrescida apenas das colunas de linhagem (`_run_id`, `_page`), sem nenhuma tipagem relacional ou aplicação de regras de negócio.
- **Transformação (dbt):** Atua exclusivamente dentro do PostgreSQL. O dbt lê a tabela `raw_staging`, aplica o "achatamento" do JSON, a tipagem, a separação de entidades (`entity_type`) e executa a estratégia de *Upsert* para materializar a tabela final da camada Silver.

## 6. Dicionário de Dados e Contrato (Camada Silver)

Os dados na camada Silver são estritamente divididos entre dados de negócio (observações) e dados de linhagem (metadados da engenharia).

### 6.1. Dados de Observação (Business Data)
| Campo | Tipo de Dado | Obrigatório? | Descrição |
| :--- | :--- | :---: | :--- |
| `entity_code` | VARCHAR(10) | Sim | Código identificador da entidade no WB (ex: BRA, ARB). *[Chave]* |
| `entity_name` | VARCHAR(255)| Sim | Nome oficial da entidade retornado pela API. |
| `entity_type` | VARCHAR(50) | Sim | Classificação da entidade (`COUNTRY`, `REGION`, etc). |
| `iso3_code` | VARCHAR(3)  | Não | Código ISO-3 real. |
| `indicator_id` | VARCHAR(50) | Sim | Código do indicador no WB (ex: NY.GDP.MKTP.CD). *[Chave]* |
| `year` | INTEGER | Sim | Ano de referência da medição. *[Chave]* |
| `indicator_value`| NUMERIC(38,15)| Não | Valor numérico medido. Mantido como `NULL` (e não `0`) em anos sem reporte. Escala de 15 casas para não arredondar indicadores percentuais (ex.: inflação `8.73914352329393`). |

### 6.2. Dados de Linhagem e Metadados (Lineage/Metadata)
| Campo | Tipo de Dado | Obrigatório? | Descrição |
| :--- | :--- | :---: | :--- |
| `_run_id` | VARCHAR(36) | Sim | UUID da execução do pipeline que gerou esta linha. |
| `_extracted_at` | TIMESTAMPTZ | Sim | Data e hora exatas da extração da API (com fuso horário; a ingestão registra em UTC). |
| `_source_url` | TEXT | Sim | URL exata da API (incluindo paginação) que forneceu o dado. |

## 7. Regras de Qualidade e Exceções
*   **Tratamento de Nulos:** Ausência de dados em `indicator_value` permanecerá como `NULL` no banco, mantendo a semântica correta de "ausência de observação".
*   **Controle de Duplicidade:** A restrição de chave única na Silver (`entity_code`, `year`, `indicator_id`) impedirá que múltiplas extrações do mesmo snapshot gerem linhas duplicadas no banco relacional. Falhas de tipagem bloquearão a execução do dbt.
*   **Integridade de Entidades:** Se `entity_type` for igual a `'COUNTRY'`, o campo `iso3_code` **deve ser NOT NULL**. Se `entity_type` for diferente de `'COUNTRY'` (ex: `'REGION'`), o campo `iso3_code` **deve ser estritamente NULL**.