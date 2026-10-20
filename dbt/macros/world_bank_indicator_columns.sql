{#
    Mapeamento indicador (Silver) → coluna (Gold). Fonte única usada pelo modelo
    mart_economic_overview e pelos testes dele. Nomes, unidades e o critério dos
    tipos: docs/data-contracts/gold-economic-overview.md (seções 3 e 5).

    Escala: 2 casas para US$ (centavos), 4 para pontos percentuais. A fonte publica
    1 casa (0 para PIB e RNB) e o resto do valor bruto é ruído de ponto flutuante.
    Precisão: dimensionada pelo maior valor observado de cada indicador, com folga.
#}
{% macro world_bank_indicator_columns() %}
    {{ return([
        {"indicator_id": "NY.GDP.MKTP.CD",    "column": "gdp_current_usd",              "data_type": "numeric(20, 2)"},
        {"indicator_id": "NY.GDP.PCAP.CD",    "column": "gdp_per_capita_current_usd",   "data_type": "numeric(12, 2)"},
        {"indicator_id": "NY.GDP.MKTP.KD.ZG", "column": "gdp_growth_annual_pct",        "data_type": "numeric(9, 4)"},
        {"indicator_id": "FP.CPI.TOTL.ZG",    "column": "inflation_cpi_annual_pct",     "data_type": "numeric(12, 4)"},
        {"indicator_id": "SL.UEM.TOTL.ZS",    "column": "unemployment_pct_labor_force", "data_type": "numeric(7, 4)"},
        {"indicator_id": "NE.EXP.GNFS.ZS",    "column": "exports_pct_gdp",              "data_type": "numeric(9, 4)"},
        {"indicator_id": "NE.IMP.GNFS.ZS",    "column": "imports_pct_gdp",              "data_type": "numeric(9, 4)"},
        {"indicator_id": "NY.GNP.PCAP.CD",    "column": "gni_per_capita_atlas_usd",     "data_type": "numeric(12, 2)"},
    ]) }}
{% endmacro %}
