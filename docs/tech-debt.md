# Dívidas Técnicas

Registro de dívidas técnicas do projeto: o problema, o impacto, a decisão tomada e o status.

---

## GEDP-TD-001 — Generalização do modelo de entidades para o escopo global

- **Status:** Resolvida (2026-10-05)
- **Aberta em:** 2026-10-04

### Problema
A ingestão estava restrita ao Brasil (`COUNTRY = "BRA"`), e a Silver classificava as entidades com um seed manual (`world_bank_entities.csv`) que só continha `BRA,COUNTRY`. Ao mudar para `country=all`:

1. Toda entidade fora do seed ficaria com `entity_type` nulo e derrubaria o build da Silver.
2. O `entity_code` vinha de `countryiso3code`, que a API devolve **vazio** para os grupos de renda (`High income`, `Low income`, `Lower middle income`, `Upper middle income`, `Not classified`). O teste `not_null` falharia antes mesmo do join com o seed.

O suporte a `COUNTRY`, `REGION` e `INCOME_GROUP` estava modelado no contrato, mas não implementado.

### Decisão
Usar o cadastro oficial do World Bank (`/v2/country`) como fonte das entidades, ingerido como o dataset `countries` pelo mesmo fluxo dos indicadores:

- **Ingestão:** `DatasetConfig` passou a guardar o caminho da URL (`path`); o dataset `countries` não tem `indicator_id`.
- **raw_staging:** migration `002_world_bank_pages_nullable_indicator.sql` torna `indicator_id` opcional.
- **dbt:** novo modelo `int_world_bank_entities` (cadastro explodido e classificado). A Silver liga observação e entidade por `country.id` = `iso2Code`, a única chave sempre presente. O seed foi removido.
- **Classificação derivada do próprio cadastro:** um agregado recebe o tipo do papel em que os países o citam (`region`/`adminregion` → `REGION`, `incomeLevel` → `INCOME_GROUP`, `lendingType` → `LENDING_GROUP`); os demais ficam `OTHER_AGGREGATE`.

Regras detalhadas: [data contract, seção 2.1](data-contracts/world-bank.md).

### Resultado da validação
- Cadastro: 295 entidades (217 países, 12 regiões, 4 grupos de renda, 3 grupos de empréstimo, 59 outros agregados).
- Silver global: 139.920 linhas = 8 indicadores × 265 entidades com dados × 66 anos. `dbt build`: 33/33 PASS.

### Achado durante a resolução
Com ~18 páginas por indicador, timeouts momentâneos da API derrubaram 2 de 8 runs na primeira ingestão global. O manifest marcou os dois como `failed`, e o loader os ignorou, como previsto. Foi adicionado retry com backoff exponencial em `cliente.py` (5 tentativas; 429 e 5xx; timeouts de leitura). Na reingestão, os dois runs completaram.

### Pendências relacionadas (não bloqueantes)
- `OTHER_AGGREGATE` reúne agregados geográficos fora da hierarquia oficial (ex.: `ARB`, `EUU`). Se for necessário distingui-los, criar um seed de exceções.
- A classificação reflete o cadastro atual; mudanças históricas (ex.: país que mudou de grupo de renda) não são preservadas.
