"""Reglas de riesgo que la estrategia no puede saltarse.

Fase 4 incluye lo mínimo indispensable para operar en demo: toda posición lleva stop,
el tamaño sale del riesgo aceptado, hay un límite de pérdida diaria y un interruptor de
emergencia. La Fase 5 ampliará esto (límite semanal, apalancamiento, etc.).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from bot_eve.backtest.costs import SymbolRules
from bot_eve.common.config import RiskConfig
from bot_eve.data.intervals import to_timedelta


@dataclass(frozen=True)
class Decision:
    ok: bool
    reason: str = ""


class RiskManager:
    def __init__(self, cfg: RiskConfig, kill_file: Path) -> None:
        self.cfg = cfg
        self.kill_file = Path(kill_file)

    # --- interruptor de emergencia ---------------------------------------------------
    def kill_requested(self) -> bool:
        return self.kill_file.exists()

    # --- tamaño --------------------------------------------------------------------------
    def stop_pct_for(self, strategy_stop_pct: float | None) -> float:
        """Toda posición tiene stop: si la estrategia no lo da, se usa el de emergencia."""
        valid = strategy_stop_pct is not None and math.isfinite(strategy_stop_pct)
        pct = strategy_stop_pct if valid and strategy_stop_pct > 0 else self.cfg.default_stop_pct
        return min(pct, 0.5)

    def position_size(
        self,
        equity: float,
        price: float,
        stop_pct: float,
        capital_fraction: float,
        rules: SymbolRules,
        available_quote: float,
    ) -> float:
        """Cantidad a comprar: limitada por el riesgo por operación, la fracción de capital
        asignada a la estrategia y el saldo disponible (con margen para la comisión)."""
        if min(equity, price, stop_pct, capital_fraction) <= 0:
            return 0.0
        by_risk = equity * self.cfg.risk_per_trade / (price * stop_pct)
        by_capital = equity * capital_fraction / price
        by_cash = available_quote / (price * 1.002)
        qty = rules.round_qty(min(by_risk, by_capital, by_cash))
        return qty if rules.is_valid(qty, price) else 0.0

    def stop_prices(self, entry_price: float, stop_pct: float) -> tuple[float, float]:
        """(precio de activación, precio límite) del stop en el exchange."""
        stop = entry_price * (1 - stop_pct)
        return stop, stop * (1 - self.cfg.stop_limit_buffer)

    # --- permisos --------------------------------------------------------------------------
    def can_open(self, equity: float, day_start_equity: float) -> Decision:
        if self.kill_requested():
            return Decision(False, "interruptor de emergencia activo")
        if day_start_equity > 0:
            change = equity / day_start_equity - 1
            if change <= -self.cfg.max_daily_loss:
                return Decision(False, f"pérdida diaria {change:.2%} alcanzó el límite")
        return Decision(True)

    def is_stale(self, last_candle: pd.Timestamp, interval: str, now: pd.Timestamp) -> bool:
        """¿La última vela cerrada es demasiado vieja? (datos caídos o retrasados)."""
        step = to_timedelta(interval)
        age = now - (last_candle + step)
        return age > step * self.cfg.max_data_age_candles
