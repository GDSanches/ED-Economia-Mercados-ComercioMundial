# Proposta Arquitetural: Projeto Economia Global (GEDP)

## 1. Visão Geral
A plataforma coleta automaticamente dados de diferentes instituições globais, mantém o histórico bruto, padroniza e valida a qualidade dos dados, transforma-os em modelos analíticos e os disponibiliza para consultas. O objetivo é fornecer uma visão integrada sobre mercados, macroeconomia e comércio internacional, permitindo a exploração das relações comerciais e a análise de indicadores financeiros entre países.

## 2. Requisitos do Sistema

### 2.1. Requisitos Funcionais (RF)
* **RF01:** O sistema deve coletar indicadores econômicos e comerciais de fontes públicas via APIs (ex: World Bank).
* **RF02:** O sistema deve preservar o dado bruto original, sem nenhuma alteração, garantindo o registro histórico da extração.
* **RF03:** O sistema deve padronizar identificadores (como códigos ISO de países), unidades de medida, moedas e formatos de data de diferentes fontes.
* **RF04:** O sistema deve validar a qualidade dos dados, impedindo a propagação de duplicatas e alertando sobre falhas de tipagem.
* **RF05:** O sistema deve cruzar indicadores de diferentes instituições em um modelo unificado (camada analítica).
* **RF06:** O sistema deve permitir a consulta de indicadores históricos através de uma API REST.
* **RF07:** O sistema deve fornecer abstrações para análises de grafos (Network Analysis), mapeando países como nós e fluxos de importação/exportação como arestas.
* **RF08:** O sistema deve expor os dados em uma interface web com visualizações interativas.

### 2.2. Requisitos Não Funcionais (RNF)
* **RNF01 — Idempotência:** A execução repetida de um mesmo pipeline de ingestão ou transformação não deve gerar dados duplicados.
* **RNF02 — Reprocessamento:** Deve ser possível reprocessar todo o histórico a partir da camada bruta (Bronze) caso haja mudanças nas regras de negócio ou falhas.
* **RNF03 — Rastreabilidade:** Qualquer dado servido na ponta final deve ter sua linhagem (linage) rastreável até o arquivo bruto de origem e o momento da extração.
* **RNF04 — Resiliência a Nulos:** O sistema deve suportar lacunas históricas (valores nulos em séries temporais) sem inferir valores falsos como zero.
* **RNF05 — Isolamento de Ambientes:** O motor de transformação (dbt) deve operar de forma isolada, não impactando a disponibilidade da API de leitura.

## 3. Estratégia de Dados e Atualização

O processamento é dividido no padrão Medallion (Bronze, Silver, Gold), com separação clara entre armazenamento de arquivos e o Data Warehouse relacional.

* **Bronze (Raw Data):** 
  * **Onde:** Object Storage (MinIO).
  * **Formato:** Original da fonte (ex: JSON, CSV).
  * **Estratégia:** *Append-only* com particionamento lógico (`fonte/dataset/ano/mes/dia/extracao.json`). Funciona como um repositório imutável (Data Lake).
* **Silver (Cleaned Data):**
  * **Onde:** PostgreSQL.
  * **Motor de Transformação:** dbt (data build tool).
  * **O que é feito:** "Achatamento" (flatten) de JSONs em formato tabular, tipagem forte, padronização de códigos de países (ISO-3), filtragem de regiões inválidas e aplicação de *upserts* baseados em chave primária (`iso3 + year + indicator_id`) para lidar com atualizações retroativas da fonte.
* **Gold (Analytics):**
  * **Onde:** PostgreSQL.
  * **Motor de Transformação:** dbt.
  * **O que é feito:** Tabelas fatos e dimensões, agregações, e views otimizadas para consumo de APIs e algoritmos analíticos (ex: matrizes de fluxos para análise de redes complexas).

## 4. Arquitetura do Projeto

```mermaid
flowchart TD
    subgraph Fontes
        WB[World Bank]
        ECB[ECB]
        WTO[UN Comtrade]
    end

    subgraph Ingestao
        PY[Scripts Python / Requests]
    end

    subgraph Armazenamento Físico
        MINIO[(MinIO - Data Lake)]
        PG[(PostgreSQL - Data Warehouse)]
    end

    subgraph Transformacao
        DBT[dbt]
    end

    subgraph Consumo
        API[FastAPI]
        WEB[React / Visualização]
        NET[Análise de Grafos]
    end

    %% Fluxo
    WB & ECB & WTO -->|Extração| PY
    PY -->|JSON Particionado\nAppend-only| MINIO
    
    MINIO -->|Cópia Bruta| PG
    PG -.->|Roda transformações\nvia| DBT
    DBT -.->|Cria Tabelas\nSilver e Gold| PG
    
    PG -->|Leitura| API
    PG -->|Leitura| NET
    API --> WEB

    classDef storage fill:#f9f,stroke:#333,stroke-width:2px;
    class MINIO,PG storage;