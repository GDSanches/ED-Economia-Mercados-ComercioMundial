# Data Contract: UN Comtrade — Comércio bilateral de mercadorias (piloto)

> **Status:** contrato da fonte (GEDP-011.1). A pipeline ainda não foi implementada.
> Todas as afirmações marcadas como **observado** vêm de consultas reais feitas em 14/10/2026 ao endpoint público de pré-visualização (seção 11). As marcadas como **inferência** não foram confirmadas pela documentação oficial.

## 1. Visão geral e escopo do piloto

- **Fonte:** UN Comtrade (Divisão de Estatística das Nações Unidas, UNSD).
- **Domínio:** comércio internacional de mercadorias.
- **Objetivo do piloto:** obter registros bilaterais do tipo *Brasil → China*, *Brasil → EUA*, com o valor comercial de cada parceiro, como primeira matéria-prima para a futura rede de comércio mundial.

| Dimensão | Escopo inicial | Valor na API |
| :--- | :--- | :--- |
| Tipo de comércio | Mercadorias | `typeCode = C` |
| Frequência | Anual | `freqCode = A` |
| Classificação de produtos | Sistema Harmonizado (HS) | `clCode = HS` |
| País relator | Brasil | `reporterCode = 76` |
| Período | 2023 | `period = 2023` |
| Parceiros | Todos, reportados individualmente | `partnerCode` omitido (a API devolve todos) |
| Fluxos | Exportações e importações | `flowCode = X` e `flowCode = M`, em execuções separadas |
| Produto | Total agregado de mercadorias | `cmdCode = TOTAL` |

Este é um **piloto de ingestão**, não o escopo definitivo. A expansão (outros relatores, anos e produtos detalhados) muda os limites de volume e, portanto, a estratégia de acesso (seção 2.3).

## 2. Acesso à API

### 2.1 Endpoints

| Endpoint | Caminho | Chave de assinatura |
| :--- | :--- | :--- |
| **Pré-visualização** (usado no piloto) | `https://comtradeapi.un.org/public/v1/preview/{typeCode}/{freqCode}/{clCode}` | Não |
| Dados finais | `https://comtradeapi.un.org/data/v1/get/{typeCode}/{freqCode}/{clCode}` | Sim |
| Tabelas de referência | `https://comtradeapi.un.org/files/v1/app/reference/{tabela}.json` (ex.: `partnerAreas`, `Reporters`) | Não |

URL do piloto (exportações):
```
https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=76&period=2023&cmdCode=TOTAL&flowCode=X&partner2Code=0&customsCode=C00&motCode=0&includeDesc=true
```

### 2.2 Limites

| Limite | Pré-visualização (sem chave) | Fonte |
| :--- | :--- | :--- |
| Registros por chamada | **500** | Documentação oficial; **observado** (ver truncamento, seção 4.2) |
| Períodos por chamada | **1** | Documentação oficial; **observado**: `period=2022,2023` → HTTP 400 `"Maximum number of periods for preview is 1"` |
| Frequência de chamadas | Limitada por segundo, **compartilhada por todas as execuções da mesma origem** | **Observado**: chamadas seguidas → HTTP 429 com `Retry-After: 1`. Como as execuções concorrentes dividem esse limite: seção 8.6 |
| `maxRecords` | **Ignorado** | **Observado**: `maxRecords=10` devolveu os 228 registros |

Com chave gratuita (conta *Basic Individual*), a documentação oficial informa até 100 mil registros por chamada e 1 chamada por segundo.

### 2.3 Decisão: o piloto usa a pré-visualização

O escopo do piloto cabe com folga no limite: **228 registros** nas exportações e **225** nas importações, contra o teto de 500. Usar a pré-visualização evita gerenciar uma chave de assinatura nesta fase.

Essa decisão é **válida só enquanto cada consulta couber em 500 registros**, e o contrato não presume isso: a quantidade esperada é verificada antes de cada execução (seção 8.4). Ao ampliar o escopo (produtos detalhados, por exemplo: só o Brasil em 2023 com produtos de 2 dígitos tem **11.140** registros, observado), a migração para o endpoint de dados finais com chave passa a ser obrigatória.

## 3. Parâmetros da consulta

| Parâmetro | Valor | Significado | Observação |
| :--- | :--- | :--- | :--- |
| `typeCode` (caminho) | `C` | Mercadorias (`S` = serviços) | |
| `freqCode` (caminho) | `A` | Anual (`M` = mensal) | |
| `clCode` (caminho) | `HS` | Busca no Sistema Harmonizado, em qualquer versão | A resposta informa a versão efetivamente reportada em `classificationCode` (`H6` = HS 2022, observado). **Na pré-visualização, só `HS` devolve dados:** `H6`, `H5` e `H4` devolveram HTTP 200 com 0 registros e sem erro (observado), inclusive `H6`, a versão em que o Brasil reportou. Ver seção 5.3. |
| `reporterCode` | `76` | Brasil (tabela oficial `Reporters`) | |
| `period` | `2023` | Ano de referência | Um período por chamada |
| `partnerCode` | *(omitido)* | Todos os parceiros, inclusive `0` = World | |
| `partner2Code` | `0` | Segundo parceiro = World (total) | Informado explicitamente para não depender de padrão implícito |
| `cmdCode` | `TOTAL` | Total de todas as mercadorias | |
| `flowCode` | `X` ou `M` | Exportação ou importação | `X,M` numa chamada funciona (observado), mas o piloto separa os fluxos (seção 8.1) |
| `customsCode` | `C00` | Total de procedimentos aduaneiros | Informado explicitamente |
| `motCode` | `0` | Total de modos de transporte | Informado explicitamente |
| `includeDesc` | `true` | Inclui descrições textuais (`partnerDesc`, `flowDesc` etc.) | |

**Sobre os parâmetros explícitos:** sem informar `partner2Code`, `customsCode` e `motCode`, a API devolveu apenas os totais desses desdobramentos. Isso é um comportamento **observado**, não documentado. A consulta com os três valores explícitos devolveu **exatamente os mesmos 228 registros** (observado). O contrato fixa os valores explícitos para que a consulta não dependa de um padrão da API que pode mudar.

`breakdownMode=plus` não alterou o resultado neste recorte (observado).

## 4. Estrutura da resposta

### 4.1 Envelope

```json
{
  "elapsedTime": "0.15 secs",
  "count": 228,
  "data": [ { ...registro... }, ... ],
  "error": ""
}
```

| Campo | Significado |
| :--- | :--- |
| `count` | Quantidade de registros **devolvidos**, não a quantidade existente (seção 4.2) |
| `data` | Lista de registros. Com `countOnly=true`, vem como **objeto** (um registro modelo vazio), e não como lista (observado) |
| `error` | Texto vazio quando não há erro. Em erros, a mensagem vem aqui, acompanhada de HTTP 4xx |

### 4.2 Truncamento silencioso

**Esta é a diferença mais importante em relação ao World Bank.** Não há paginação: uma consulta é respondida numa única chamada, de até 500 registros. Quando a consulta tem mais registros que o limite, a API **corta a resposta sem avisar**:

| Consulta (observado) | `count` | Registros em `data` | `error` | Total real (`countOnly`) |
| :--- | :---: | :---: | :---: | :---: |
| Brasil 2023, exportações, produtos de 2 dígitos | 500 | 500 | `""` | **11.140** |

HTTP 200, `error` vazio e `count = 500`: a resposta é indistinguível de uma consulta que tem exatamente 500 registros. **O `count` da resposta não serve para verificar completude.**

### 4.3 Como saber o total: `countOnly`

Com `countOnly=true`, a API devolve no `count` a quantidade **total** de registros da consulta, sem os dados (observado: 228 para exportações e 225 para importações, iguais aos registros recebidos nas consultas completas; 11.140 para a consulta truncada).

### 4.4 Respostas de erro e casos especiais (observados)

| Situação | HTTP | `error` / cabeçalhos |
| :--- | :---: | :--- |
| Consulta válida | 200 | `""` |
| Consulta válida sem dados (ex.: `period=2030`) | 200 | `""`, `count = 0`, `data = []` |
| Valor de parâmetro inválido (ex.: `reporterCode=99999`) | 400 | `"Invalid parameter value"` |
| Mais de um período na pré-visualização | 400 | `"Maximum number of periods for preview is 1"` |
| Excesso de chamadas por segundo | 429 | `Retry-After: 1` |

## 5. Granularidade: o que representa uma linha

### 5.1 Evidência

Nas 228 linhas de exportações e 225 de importações, **todos os candidatos a dimensão adicional são constantes** (observado):

| Campo | Valor em todas as linhas |
| :--- | :--- |
| `partner2Code` | `0` (World) |
| `cmdCode` | `TOTAL` |
| `customsCode` | `C00` (total) |
| `motCode` | `0` (total) |
| `mosCode` | `"0"` |
| `classificationCode` | `H6` |

Os únicos campos que variam são o parceiro (`partnerCode`, `partnerISO`, `partnerDesc`), os valores (`primaryValue`, `fobvalue`, `cifvalue`, `netWgt`) e flags de estimativa. Não há dois registros com o mesmo `partnerCode` (observado).

### 5.2 Definição

> **Uma linha representa o valor de um fluxo comercial (exportação ou importação) de mercadorias, declarado por um país relator, com um parceiro comercial, num período e numa frequência, para um produto (no piloto, o total de todas as mercadorias), sob o total de segundo parceiro, procedimento aduaneiro e modo de transporte.**

### 5.3 Chave lógica

```
typeCode + freqCode + period + reporterCode + flowCode
  + partnerCode + partner2Code + classificationCode + cmdCode + customsCode + motCode
```

No piloto, só `partnerCode` (e `flowCode`, entre execuções) varia. Os demais campos entram na chave mesmo sendo constantes: **ao ampliar o escopo** (produtos detalhados, desdobramento por modo de transporte ou procedimento aduaneiro), eles passam a distinguir registros, e uma chave definida só com o parceiro geraria duplicatas.

#### Por que `classificationCode` está na chave

A versão anterior deste contrato deixava `classificationCode` fora da chave, como atributo, sob a hipótese de que um relator não aparece com o mesmo período em duas versões do HS. A decisão foi revista:

1. **O código de produto só tem significado dentro de uma versão da classificação.** A cada revisão do HS (2017 → 2022, por exemplo), códigos são criados, divididos e fundidos: o mesmo `cmdCode` pode cobrir conjuntos diferentes de mercadorias em `H5` e em `H6`. A identidade de um produto é o par `classificationCode + cmdCode`, e não o `cmdCode` sozinho. No piloto (`cmdCode = TOTAL`) isso é irrelevante, mas a chave é desenhada para os produtos detalhados.
2. **A hipótese que justificava deixá-lo de fora não é verificável neste endpoint.** Para observar se a API devolve o mesmo fluxo convertido para outra versão (`isOriginalClassification = false`), seria preciso consultar versões específicas, e na pré-visualização elas devolvem 0 registros (seção 3). Uma chave não deve depender de uma hipótese que não pode ser testada.
3. **O custo de incluir é nulo, o de não incluir é uma colisão silenciosa.** Hoje o campo é constante por relator e período (`H6` em todas as linhas). Se um dia a mesma série for ingerida em duas versões (a original e uma convertida, para comparar períodos), uma chave sem a classificação trataria registros diferentes como duplicatas.

Atributos relacionados, guardados sem entrar na chave:
- `classificationSearchCode` (`HS`): o que foi **pedido**, e já registrado em `request_params` no manifest.
- `isOriginalClassification` (`true` em todas as linhas, observado): se o dado está na versão em que o país reportou.

**Expectativa a testar na Silver:** no piloto, cada `reporterCode + period + flowCode` tem um único `classificationCode`, com `isOriginalClassification = true`. Se isso deixar de valer, não é um erro de chave, e sim um sinal de que a ingestão passou a trazer séries convertidas, o que precisa ser uma decisão explícita.

**Consequência da seção 3:** como uma versão específica devolve resultado vazio sem erro, o `clCode` é parte do contrato da consulta. Trocar `HS` por `H6` faria todas as execuções terminarem `completed` com 0 registros. O teste de expectativa de volume na Silver (seção 8.4) é o que protege contra isso.

## 6. Dicionário de dados

Campos retornados com `includeDesc=true` (45 campos). Os relevantes para o projeto:

### 6.1 Identificação do registro

| Campo | Exemplo | Significado | Observações |
| :--- | :--- | :--- | :--- |
| `typeCode` | `C` | Tipo de comércio | |
| `freqCode` | `A` | Frequência | |
| `period` | `"2023"` | Período de referência (texto) | |
| `refYear` | `2023` | Ano de referência (inteiro) | |
| `refMonth` | `52` | Mês de referência | **`52` é o código para "ano inteiro"** em dados anuais (observado em todas as linhas). Não é um mês. |
| `refPeriodId` | `20230101` | Identificador numérico do período | |

### 6.2 Relator e parceiro

| Campo | Exemplo | Significado | Observações |
| :--- | :--- | :--- | :--- |
| `reporterCode` | `76` | País que declarou o dado | **Código numérico próprio do Comtrade**, não o ISO 3166 numérico (seção 6.6) |
| `reporterISO` | `BRA` | ISO alfa-3 do relator | |
| `reporterDesc` | `Brazil` | Nome do relator | |
| `partnerCode` | `156` | País ou área com que ocorreu o comércio | `0` = World (total). Também usa códigos próprios do Comtrade. |
| `partnerISO` | `CHN` | ISO alfa-3 do parceiro | Áreas especiais usam pseudo-códigos, **alguns com espaço no final** (`"_X "`), ver 6.5 |
| `partnerDesc` | `China` | Nome do parceiro | |
| `partner2Code` / `partner2ISO` / `partner2Desc` | `0` / `W00` / `World` | Segundo parceiro (ex.: país de consignação) | Sempre o total no piloto |

### 6.3 Fluxo, produto e desdobramentos

| Campo | Exemplo | Significado | Observações |
| :--- | :--- | :--- | :--- |
| `flowCode` / `flowDesc` | `X` / `Export` | Direção do fluxo | `M` / `Import` nas importações |
| `cmdCode` / `cmdDesc` | `TOTAL` / `All Commodities` | Produto | No piloto, sempre o total |
| `aggrLevel` | `0` | Nível de agregação do produto | `0` = total |
| `isLeaf` | `false` | Se o produto é o nível mais detalhado | |
| `classificationCode` | `H6` | Versão da classificação em que o país reportou | `H6` = HS 2022 |
| `customsCode` / `customsDesc` | `C00` / `TOTAL CPC` | Procedimento aduaneiro | Sempre o total no piloto |
| `motCode` / `motDesc` | `0` / `TOTAL MOT` | Modo de transporte | Sempre o total no piloto |

### 6.4 Valores, quantidades e flags

| Campo | Exportações | Importações | Significado e observações |
| :--- | :--- | :--- | :--- |
| `primaryValue` | = `fobvalue` | = `cifvalue` | **Valor principal, em US$.** É o FOB nas exportações e o CIF nas importações (observado: igualdade em todas as linhas). Preenchido e positivo em todas as linhas. |
| `fobvalue` | preenchido | preenchido | Valor FOB (*free on board*): sem frete e seguro internacionais |
| `cifvalue` | **sempre `null`** | preenchido | Valor CIF (*cost, insurance and freight*). Nas importações, FOB < CIF em 222 de 225 linhas. |
| `qty`, `altQty` | `0.0` | `0.0` | **Zero significa "não se aplica", não "zero unidades":** `qtyUnitCode = -1` e `qtyUnitAbbr = "N/A"`. Quantidade não faz sentido para o total de todas as mercadorias (unidades diferentes não se somam). |
| `netWgt`, `grossWgt` | `0.0` | `0.0` (3 linhas com `null`) | Peso indisponível para o total. Mistura de `0.0` e `null` com o mesmo significado. |
| `isAggregate` | `true` | `true` | **Não indica parceiro agregado.** É `true` em todas as linhas, inclusive China e EUA. **Inferência:** refere-se ao produto (`TOTAL` é uma soma calculada a partir dos produtos detalhados). Para identificar o total "World", usar `partnerCode = 0`. |
| `isReported` | `false` | `false` | **Inferência:** o valor não foi enviado diretamente pelo país nessa forma; o total é calculado pela UNSD a partir dos registros detalhados. |
| `legacyEstimationFlag` | `0` ou `4` | `0` ou `4` | **Inferência** (documento de métodos da UNSD): `0` = sem estimativa, `4` = só o peso líquido estimado. Irrelevante no piloto, já que os pesos não estão disponíveis. |

**Moeda e unidade:** os valores comerciais estão em **US$ correntes**, a unidade padrão do UN Comtrade. O valor de exportações do Brasil com o World em 2023 (US$ 339,70 bilhões, observado) é coerente com o total oficial publicado para o ano.

**Decisão para as camadas seguintes:** o valor comercial do projeto é o `primaryValue`. Quantidade e peso **não** entram no modelo do piloto. `0.0` em quantidade ou peso deve ser tratado como ausência, nunca como zero (mesmo princípio do RNF04).

### 6.5 Classificação dos parceiros: economias, áreas e grupos

Fonte: tabela oficial `partnerAreas` (310 entradas, analisada por completo) e respostas reais.

#### Por que "país" não é a categoria certa

Um parceiro do Comtrade é uma **área de comércio** (*trade area*), e nem sempre corresponde a um país soberano:
- **Territórios dependentes** com estatística própria: Hong Kong (`344`), Macau (`446`), Groenlândia (`304`), Aruba (`533`), Wallis e Futuna (`876`). Vários aparecem nas respostas do Brasil.
- **Áreas compostas:** França (`251`, "France, Monaco"), Bélgica-Luxemburgo (`58`, até 1998).
- **Entidades históricas:** Tchecoslováquia (`200`), as duas Alemanhas (`278` e `280`), Tanganyika (`835`). Há 36 entradas com `entryExpiredDate` preenchida.
- **Economias sem ISO alfa-2:** Kosovo (`412`, pseudo-ISO `_KS`), Ilhas do Canal (`830`), Ilha Wake (`872`) e outras 10.

Por isso o contrato usa **economia** (país ou território com estatística de comércio própria), e não "país".

#### As quatro categorias

| Categoria | Regra (aplicada à tabela `partnerAreas`) | Entradas na tabela | Exemplos | É nó da rede bilateral? |
| :--- | :--- | :---: | :--- | :---: |
| `WORLD` | `isGroup = true` | 1 | `0` World (`W00`) | Não: é o **total** de todos os parceiros |
| `SPECIAL_CATEGORY` | Código em `837`, `838`, `839` | 3 | Bunkers, Free Zones, Special Categories | Não: categoria de comércio, sem localização geográfica |
| `UNSPECIFIED_AREA` | Nome terminado em `", nes"` **e** nota com "not elsewhere specified" | 16 | `899` Areas, nes; `490` Other Asia, nes; `129` Caribbean, nes; `473` LAIA, nes | Não: comércio que o relator não atribuiu a uma economia |
| `ECONOMY` | Todas as demais | 290 | `156` China, `842` USA, `344` Hong Kong, `412` Kosovo | **Sim** |

- **As duas marcas de "nes" concordam em 100% das 310 entradas** (nome terminado em `, nes` e nota "not elsewhere specified"; 0 divergências). A regra usa as duas, e uma divergência futura deve ser tratada como erro de classificação.
- **A lista de categorias especiais é fechada** (3 códigos, todos com pseudo-ISO iniciado por `X`). Um código novo da tabela que não se encaixe nas regras cai em `ECONOMY`; por isso, na Silver, o teste de cobertura deve alertar sobre **códigos novos** na tabela, para que alguém confirme a categoria.
- **`490` "Other Asia, nes"** é tratada como área não especificada, como a fonte a declara. Na prática, é como Taiwan aparece no Comtrade; tratá-la como economia seria uma decisão analítica explícita, fora deste contrato.

#### Por que o ISO alfa-2 não serve como critério

A versão anterior deste contrato usava "tem ISO alfa-2" para separar países de áreas especiais. A análise da tabela completa mostrou que a regra erra nos dois sentidos:
- classificaria como "área especial" **13 economias reais sem alfa-2**, como Kosovo e Ilhas do Canal;
- não distingue território, entidade histórica e área composta, que também têm alfa-2.

O alfa-2 continua útil como **atributo** (para cruzar com outras fontes), mas não como critério de categoria.

#### Atributos adicionais de cada economia

| Atributo | Origem | Uso |
| :--- | :--- | :--- |
| `is_historical` | `entryExpiredDate` preenchida | Entidades extintas não devem aparecer em períodos posteriores ao fim da vigência |
| `iso2` / `iso3` | `PartnerCodeIsoAlpha2` / `PartnerCodeIsoAlpha3` (com `trim`) | Integração com outras fontes. **Os pseudo-códigos têm espaço no final** (`"_X "`, `"Channel Islands "` no nome), por isso o `trim` é obrigatório. |

#### Uso nas camadas seguintes

- **Rede bilateral:** só arestas entre `ECONOMY` e `ECONOMY`.
- **Reconciliação:** `WORLD` = soma de **todas** as outras categorias (`ECONOMY` + `UNSPECIFIED_AREA` + `SPECIAL_CATEGORY`). As áreas não especificadas não entram na rede, mas entram na conta: excluí-las da soma faria o total parecer inconsistente.
- **Classificação a partir da tabela oficial, não da resposta:** a resposta traz só código, ISO e nome. A categoria vem da tabela `partnerAreas`, que deve ser ingerida como dado de referência (como o cadastro de entidades do World Bank).

No piloto: exportações = 1 `WORLD` + 225 `ECONOMY` + 2 `UNSPECIFIED_AREA` (`490` e `899`); importações = 1 + 222 + 2.

#### Nota sobre relatores

O lado do relator também tem grupos: a tabela `Reporters` marca como `isGroup` a **União Europeia** (`97`), a **ASEAN** (`975`) e "Other Asia, nes" (`490`). No piloto o relator é o Brasil, mas, na expansão, um relator agrupado ao lado dos seus membros contaria o mesmo comércio duas vezes. A seleção de relatores deve excluir grupos (ou tratá-los numa análise separada).

### 6.6 Códigos numéricos não são ISO

O Comtrade usa códigos numéricos próprios, baseados no M49, que **diferem do ISO 3166 numérico** em alguns países (observado):

| País | Código Comtrade | ISO 3166 numérico | Observação na tabela oficial |
| :--- | :---: | :---: | :--- |
| Estados Unidos | `842` | 840 | |
| França | `251` | 250 | "France, Monaco" |
| Índia | `699` | 356 | |

**Consequência:** a integração com o World Bank (que usa ISO alfa-3) deve ser feita por **ISO alfa-3** (`reporterISO`, `partnerISO`), e não pelo código numérico. Algumas áreas do Comtrade agregam territórios (ex.: França inclui Mônaco), e isso precisa ser considerado ao cruzar as fontes.

## 7. Regras de qualidade (observadas no piloto e a aplicar na ingestão)

| Regra | Resultado no piloto |
| :--- | :--- |
| Registros recebidos = total informado por `countOnly` | 228 = 228 (X); 225 = 225 (M) |
| Total da consulta abaixo do limite da pré-visualização (500) | 228 e 225 |
| Uma linha por chave lógica (seção 5.3) | 0 duplicatas |
| Exatamente uma linha com `partnerCode = 0` (World) | Sim |
| World = soma dos demais parceiros | Diferença de **US$ 0,00** nos dois fluxos |
| `primaryValue` preenchido e positivo | Todas as linhas |
| Exportações: `cifvalue` nulo e `primaryValue = fobvalue`; importações: `primaryValue = cifvalue` | Sim |
| Todo `partnerCode` existe na tabela oficial `partnerAreas` e recebe uma das 4 categorias da seção 6.5 | Sim |

## 8. Estratégia de execução

O padrão de rastreabilidade do World Bank (snapshot imutável por `run_id`, manifest, só runs `completed` avançam) é **reaproveitado**. Os detalhes seguem a fonte nova.

### 8.1 Datasets

| Dataset | Consulta |
| :--- | :--- |
| `goods_exports_by_partner` | `flowCode = X` |
| `goods_imports_by_partner` | `flowCode = M` |

Os nomes descrevem o conteúdo e o grão (mercadorias, fluxo, por parceiro). Exportações e importações são **execuções lógicas independentes**: uma falha ao obter as exportações não invalida uma execução de importações bem-sucedida. Isso também mantém cada execução com uma única consulta à API, sem depender do comportamento de `flowCode=X,M` diante do limite de 500.

### 8.2 Unidade de execução e `run_id`

- **Uma execução = um dataset × um relator × um período = uma chamada de dados à API.**
- `run_id`: UUID v4 gerado no início da execução, como no World Bank.

### 8.3 Armazenamento no MinIO (Bronze)

```
s3://bronze/un_comtrade/{dataset}/reporter={reporterCode}/period={period}/year=YYYY/month=MM/day=DD/run_id={uuid}/
├── manifest.json
├── count.json        ← resposta bruta da consulta countOnly
└── response.json     ← resposta bruta da consulta de dados
```

- `reporter=` e `period=` entram no caminho porque, ao ampliar o escopo, cada relator e cada período vira uma execução própria, e o caminho já permite localizar os snapshots de um país num ano.
- `year=/month=/day=` é a data da **ingestão**, como no World Bank.
- **Não há páginas:** a resposta inteira é um único arquivo, `response.json`, gravado **exatamente como recebido** (bytes do corpo HTTP), com os metadados de objeto `source-url` e `extracted-at`, como no World Bank.
- `count.json` também é preservado: é a evidência de completude da execução.

### 8.4 Fluxo da execução e manifest

```
2. Consulta countOnly           → expected_count
   2a. expected_count = 0        → EMPTY (o snapshot anterior continua valendo), sem consultar os dados
   2b. expected_count > 500      → FAILED ("excede o limite da pré-visualização"), sem consultar os dados
3. Consulta de dados            → response.json
4. Validar:
   - HTTP 200, envelope em objeto JSON e error == ""
   - data é uma lista
   - len(data) == expected_count
   - cada registro tem os campos usados pela plataforma, com o tipo esperado
   - cada registro repete os parâmetros pedidos (reporterCode, period, flowCode, cmdCode,
     partner2Code, customsCode, motCode)
5. Tudo válido 
```

```json
{
  "run_id": "uuid",
  "source": "un_comtrade",
  "dataset": "goods_exports_by_partner",
  "status": "completed",
  "started_at": "2026-10-14T12:00:00+00:00",
  "completed_at": "2026-10-14T12:00:03+00:00",
  "endpoint": "public/v1/preview/C/A/HS",
  "request_params": {
    "reporterCode": "76", "period": "2023", "cmdCode": "TOTAL", "flowCode": "X",
    "partner2Code": "0", "customsCode": "C00", "motCode": "0", "includeDesc": "true"
  },
  "record_limit": 500,
  "expected_count": 228,
  "received_count": 228,
  "error": null
}
```

- **`request_params`** registra os parâmetros exatos da consulta, para que qualquer snapshot possa ser reproduzido.
- **`record_limit`** registra o limite vigente no endpoint usado, para que a regra de completude fique auditável quando o endpoint mudar.
- **Consulta sem dados** (`expected_count = 0`): status **`empty`**, com `received_count = 0`. Uma resposta vazia **nunca** vira `completed`: como a Silver usa o snapshot `completed` mais recente, um run vazio apagaria todos os parceiros de um snapshot válido. Com o status `empty`, o snapshot anterior continua valendo, e o manifest registra que a consulta foi feita e não trouxe dados (o país pode não ter reportado o período, ou um parâmetro pode ter produzido um resultado vazio silencioso, como um `clCode` específico). Para o piloto, cujo escopo tem dados conhecidos, `empty` também faz a task do orquestrador falhar, para que alguém investigue.

**Status possíveis do manifest:**

| Status | Significado | O loader carrega? |
| :--- | :--- | :---: |
| `started` | Execução em andamento, ou interrompida sem atualizar o manifest | Não |
| `completed` | Todas as validações passaram | **Sim** |
| `failed` | Erro da API, limite excedido, contagem divergente ou registro inválido | Não |
| `empty` | A consulta foi feita e não tem registros | Não |

### 8.5 Erros, limites e respostas incompletas

| Situação | Comportamento |
| :--- | :--- |
| HTTP 429 | Repetir respeitando `Retry-After` (retry com backoff, como no `cliente.py` do World Bank) |
| HTTP 5xx ou timeout | Repetir com backoff exponencial |
| HTTP 400 | **Não repetir**: o erro é determinístico (parâmetro inválido). Falhar com a mensagem de `error`. |
| Corpo que não é JSON | Falhar |
| `expected_count` acima do limite | Falhar antes de baixar os dados. **Nunca gravar uma resposta truncada como `completed`.** |
| `len(data) != expected_count` | Falhar. Pode indicar truncamento ou dados alterados entre as duas consultas; o retry do orquestrador gera um novo run. |
| Ritmo de chamadas | Uma execução por vez em toda a plataforma, e intervalo mínimo entre as chamadas de uma execução (seção 8.6) |
| `expected_count = 0` | Status `empty`, sem baixar os dados. O snapshot anterior continua valendo. |
| Registro sem campo obrigatório, com tipo inválido ou com parâmetro diferente do pedido | Falhar com a lista dos primeiros problemas. Não gravar o snapshot como `completed`. |

### 8.6 Limite de chamadas entre execuções concorrentes

#### O limite é da origem, não da execução

O limite por segundo vale para **todas as chamadas feitas a partir da mesma origem**, e não para cada execução isoladamente:
- **Pré-visualização (sem chave):** não há credencial que identifique o cliente, então o limite só pode ser aplicado por endereço de origem (**inferência**). Todas as execuções que saem da mesma máquina ou rede, inclusive testes manuais no terminal, dividem o mesmo limite.
- **Endpoint com chave:** a documentação associa os limites à assinatura (1 chamada por segundo e cota diária no plano gratuito). Todas as execuções que usam a mesma chave dividem o limite.

**Consequência:** "esperar 1 segundo entre chamadas" dentro de cada execução **não basta**. Duas execuções concorrentes (exportações e importações em paralelo, por exemplo), cada uma respeitando o próprio intervalo, somam 2 chamadas por segundo para a API. Isso também ajuda a explicar o 429 observado com 2 segundos entre chamadas sequenciais (seção 11): a API não informa a janela exata, e o contrato não deve presumir uma.

#### Quantas chamadas uma execução consome

| Chamadas por execução | Origem |
| :--- | :--- |
| 1 | `countOnly` (expectativa de volume) |
| 1 | Consulta de dados |
| + retries | Cada repetição por 429, 5xx ou timeout é uma chamada a mais |

O piloto (2 datasets × 1 relator × 1 período) consome 4 chamadas por rodada sem retries. Na expansão, `datasets × relatores × períodos × 2` precisa caber na cota diária do plano usado.

#### Estratégia: serializar no orquestrador

1. **Uma execução por vez, em toda a plataforma.** Todas as tasks de ingestão do UN Comtrade usam um **Pool do Airflow com 1 vaga** (`un_comtrade_api`). O Pool é o mecanismo certo porque vale entre tasks, execuções e DAGs diferentes, enquanto `max_active_tis_per_dagrun` (usado no World Bank) limita só uma task dentro de uma execução. Exportações e importações continuam sendo **execuções independentes** (cada uma com seu `run_id`, seu manifest e seu resultado); elas só deixam de rodar ao mesmo tempo.
2. **Intervalo mínimo dentro da execução:** pelo menos 1 segundo entre o `countOnly` e a consulta de dados, com margem de segurança.
3. **429 como rede de segurança, não como controle de fluxo:** se ainda assim vier um 429, o cliente espera o `Retry-After` e repete. Esgotadas as tentativas, a execução termina `failed` com o motivo registrado no manifest. A falha de um fluxo não afeta o outro.
4. **Execuções fora do orquestrador** (scripts no terminal) não passam pelo Pool. Elas não devem rodar ao mesmo tempo que a DAG; se rodarem, o tratamento do 429 evita dados incorretos, ao custo de execuções mais lentas ou falhas por limite.

## 9. Pressupostos do World Bank que não valem aqui

| World Bank | UN Comtrade |
| :--- | :--- |
| Paginação: cabeçalho com `page`, `pages`, `total` | Sem paginação: uma chamada de até 500 registros |
| Resposta incompleta é detectável pelo cabeçalho | **Truncamento silencioso**: exige `countOnly` |
| Erro na resposta: lista com um objeto `message` | HTTP 4xx com o texto em `error` |
| Valor ausente = `null` | Quantidade e peso ausentes = `0.0` (com unidade `N/A`) ou `null` |
| Entidade identificada por ISO alfa-3 / código WB | Código numérico próprio do Comtrade, diferente do ISO numérico |
| Agregados identificados pelo cadastro (`region = Aggregates`) | Só o World é grupo; áreas "nes" e categorias especiais não são grupos nem economias (seção 6.5) |
| Um indicador = uma série | Um registro = uma combinação de várias dimensões (seção 5.3) |

## 10. Fora do escopo e riscos conhecidos

- **Assimetria das estatísticas espelhadas:** as exportações do Brasil para a China, declaradas pelo Brasil, não são iguais às importações da China vindas do Brasil, declaradas pela China (FOB × CIF, datas de registro, país de origem × de consignação). Na construção da rede mundial será preciso decidir qual perspectiva usar. O piloto usa só a perspectiva do relator.
- **Revisões:** os países revisam dados já publicados. O armazenamento por snapshot (`run_id`) preserva o histórico dessas revisões, como no World Bank.
- **Produtos detalhados, outros relatores e outros anos:** exigem o endpoint com chave (seção 2.3), a gestão dessa chave como segredo e um plano de chamadas compatível com o limite diário.
- **Camadas seguintes (raw_staging, Silver):** a definir no próximo ticket, a partir deste contrato.

## 11. Evidências: consultas realizadas (14/10 e 19/10/2026)

| Consulta | Resultado |
| :--- | :--- |
| Brasil 2023, `TOTAL`, exportações | HTTP 200, 228 registros, World = US$ 339,70 bi. Maiores parceiros: China (104,3 bi), EUA (37,5 bi), Argentina (16,7 bi), Países Baixos (12,1 bi), México (8,6 bi) |
| Brasil 2023, `TOTAL`, importações | HTTP 200, 225 registros, World = US$ 252,71 bi. Maiores parceiros: China (56,0 bi), EUA (40,2 bi), Alemanha (13,6 bi), Argentina (12,4 bi), Rússia (11,1 bi) |
| Mesma consulta, `partner2Code`/`customsCode`/`motCode` explícitos | Resultado idêntico |
| Mesma consulta, `breakdownMode=plus` | Resultado idêntico |
| `flowCode=X,M` | 453 registros (228 + 225) |
| Produtos de 2 dígitos (`cmdCode=AG2`) | **Truncada** em 500; `countOnly` = 11.140 |
| `countOnly=true` (X e M) | `count` = 228 e 225; `data` como objeto |
| `period=2030` | HTTP 200, 0 registros |
| `period=2022,2023` | HTTP 400 |
| `reporterCode=99999` | HTTP 400 |
| Chamadas em sequência | HTTP 429, `Retry-After: 1` |
| `clCode=H6`, `H5` e `H4` (total e produto `8517`), 19/10/2026 | HTTP 200, 0 registros, sem erro |
| Tabela `partnerAreas` completa (310 entradas), 19/10/2026 | 290 economias, 16 áreas não especificadas, 3 categorias especiais, 1 World; 13 economias sem ISO alfa-2; 36 entradas históricas |
| Tabela `Reporters` (255 entradas), 19/10/2026 | 3 relatores agrupados: União Europeia, ASEAN, Other Asia, nes |

## Referências

- Planos de assinatura e limites: [uncomtrade.org/docs/subscriptions](https://uncomtrade.org/docs/subscriptions/)
- Portal da API e documentação: [comtradeplus.un.org/ApiDocs](https://comtradeplus.un.org/ApiDocs)
- Pacote oficial de chamadas: [github.com/uncomtrade/comtradeapicall](https://github.com/uncomtrade/comtradeapicall)
- Tabelas de referência: `https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json` e `Reporters.json`
- Métodos de processamento da UNSD (flags de estimativa): [UNSD Method trade data processing](https://comtradeapi.un.org/files/v1/app/wiki/UNSD_Method_trade_data_processing_v6-17_Jun_2019.pdf)
