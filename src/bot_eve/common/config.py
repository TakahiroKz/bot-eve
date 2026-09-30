"""Carga de configuración desde YAML y variables de entorno."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_CONFIG = Path("config/default.yaml")


class DataConfig(BaseModel):
    dir: Path = Path("data_store")
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    start: str = "2020-01"
    base_interval: str = "1m"
    resample: list[str] = Field(default_factory=lambda: ["5m", "15m", "1h", "4h"])
    download_workers: int = 4
    base_url: str = "https://data.binance.vision"

    @field_validator("start")
    @classmethod
    def _check_start(cls, v: str) -> str:
        year, month = v.split("-")
        if not (len(year) == 4 and 1 <= int(month) <= 12):
            raise ValueError("start debe tener el formato YYYY-MM")
        return v


class BacktestConfig(BaseModel):
    fee_rate: float = 0.001  # 0.1% por lado (0.00075 pagando con BNB)
    slippage: float = 0.0005  # 0.05% adverso por lado
    initial_cash: float = 1000.0
    size_fraction: float = 1.0
    # El tramo desde esta fecha se reserva y no se toca hasta la evaluación final.
    holdout_start: str = "2025-07-01"
    reports_dir: Path = Path("reports")


STAGES = ("backtest", "demo", "live")


class StrategyConfig(BaseModel):
    """Configuración de una estrategia. El nombre es la clave en `strategies:`."""

    enabled: bool = False  # si participa en el bot (demo/live); en backtest siempre se puede usar
    stage: Literal["backtest", "demo", "live"] = "backtest"  # etapa máxima autorizada
    capital_fraction: float = Field(0.0, ge=0, le=1)  # parte del capital asignada en vivo
    symbols: list[str] | None = None  # None = todos los de `data.symbols`
    intervals: list[str] = Field(default_factory=lambda: ["15m"])
    params: dict = Field(default_factory=dict)

    def allowed_in(self, mode: str) -> bool:
        """¿Puede operar en `mode`? Requiere estar activada y haber alcanzado esa etapa."""
        return self.enabled and STAGES.index(self.stage) >= STAGES.index(mode)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: Path | None = Path("logs/bot_eve.log")


class Config(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    strategies: dict[str, StrategyConfig] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @model_validator(mode="after")
    def _check_capital(self) -> Config:
        for mode in ("demo", "live"):
            total = sum(c.capital_fraction for c in self.strategies.values() if c.allowed_in(mode))
            if total > 1 + 1e-9:
                raise ValueError(f"capital_fraction suma {total:.2f} > 1 para el modo {mode}")
        return self

    def active_strategies(self, mode: str) -> dict[str, StrategyConfig]:
        """Estrategias que pueden operar en `mode` ('demo' o 'live')."""
        return {n: c for n, c in self.strategies.items() if c.allowed_in(mode)}


def load_config(path: Path | str | None = None) -> Config:
    """Lee el YAML (o usa valores por defecto si no existe) y carga `.env`."""
    load_dotenv()
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        if path:
            raise FileNotFoundError(f"No existe el archivo de configuración: {cfg_path}")
        return Config()
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return Config.model_validate(raw)
