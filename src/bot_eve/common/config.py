"""Carga de configuración desde YAML y variables de entorno."""

from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

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


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: Path | None = Path("logs/bot_eve.log")


class Config(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


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
