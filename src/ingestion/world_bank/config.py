from dataclasses import dataclass


COUNTRY = "all"
PER_PAGE = 1000
SOURCE = "2"
TIMEOUT = (10, 120)

BUCKET = "bronze"


@dataclass(frozen=True)
class DatasetConfig:
	name: str
	path: str
	indicator_id: str | None = None

	@property
	def params(self) -> dict:
		# Indicadores vêm da fonte WDI (source=2); o cadastro de entidades não tem fonte.
		return {"source": SOURCE} if self.indicator_id else {}


def indicator(name: str, indicator_id: str) -> DatasetConfig:
	return DatasetConfig(name, f"country/{COUNTRY}/indicator/{indicator_id}", indicator_id)


DATASETS = (
	# Cadastro de entidades (países e agregados): usado para classificar as observações.
	DatasetConfig("countries", "country"),
	indicator("gdp", "NY.GDP.MKTP.CD"),
	indicator("gdp_per_capita", "NY.GDP.PCAP.CD"),
	indicator("gdp_growth", "NY.GDP.MKTP.KD.ZG"),
	indicator("inflation", "FP.CPI.TOTL.ZG"),
	indicator("unemployment", "SL.UEM.TOTL.ZS"),
	indicator("exports_pct_gdp", "NE.EXP.GNFS.ZS"),
	indicator("imports_pct_gdp", "NE.IMP.GNFS.ZS"),
	indicator("gni_per_capita", "NY.GNP.PCAP.CD"),
)