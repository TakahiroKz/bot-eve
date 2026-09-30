"""Costos de ejecución y reglas de símbolo de Binance spot."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Costs:
    """Modelo de costos.

    Por defecto, Binance spot:
    fee_rate: comisión por lado sobre el valor de la operación (0.001 = 0.1%; 0.00075 con BNB).
    slippage: deslizamiento adverso por lado sobre el precio de ejecución (0.0005 = 0.05%).

    Para CFD (MetaTrader 5) se añaden, todos opcionales:
    entry_fee_rate / exit_fee_rate: comisión distinta al entrar o salir (None = `fee_rate`).
        Ej.: Libertex cobra 0.1% solo en la salida -> entry_fee_rate=0, exit_fee_rate=0.001.
    spread_pct: el precio de compra (ask) queda este % sobre el gráfico (que va a precio bid);
        la venta se hace a bid, sin costo extra.
    swap_pct_per_day: costo por mantener la posición larga, como % del valor por día natural.
    """

    fee_rate: float = 0.001
    slippage: float = 0.0005
    entry_fee_rate: float | None = None
    exit_fee_rate: float | None = None
    spread_pct: float = 0.0
    swap_pct_per_day: float = 0.0

    @property
    def entry_fee(self) -> float:
        return self.fee_rate if self.entry_fee_rate is None else self.entry_fee_rate

    @property
    def exit_fee(self) -> float:
        return self.fee_rate if self.exit_fee_rate is None else self.exit_fee_rate


@dataclass(frozen=True)
class SymbolRules:
    """Filtros del par (LOT_SIZE y NOTIONAL). En vivo se leen del exchange (Fase 4)."""

    step_size: float = 1e-5
    min_qty: float = 1e-5
    min_notional: float = 5.0

    def round_qty(self, qty: float) -> float:
        steps = math.floor(qty / self.step_size + 1e-9)
        return round(steps * self.step_size, 12)

    def is_valid(self, qty: float, price: float) -> bool:
        return qty >= self.min_qty and qty * price >= self.min_notional


DEFAULT_RULES: dict[str, SymbolRules] = {
    # CFD de Libertex (MetaTrader 5), según la especificación del símbolo. Sin min. notional.
    "BTCUSD": SymbolRules(step_size=0.01, min_qty=0.01, min_notional=0.0),
    "ETHUSD": SymbolRules(step_size=0.1, min_qty=0.1, min_notional=0.0),
    "BTCUSDT": SymbolRules(step_size=1e-5, min_qty=1e-5, min_notional=5.0),
    "ETHUSDT": SymbolRules(step_size=1e-4, min_qty=1e-4, min_notional=5.0),
    "BNBUSDT": SymbolRules(step_size=1e-3, min_qty=1e-3, min_notional=5.0),
}


def rules_for(symbol: str) -> SymbolRules:
    return DEFAULT_RULES.get(symbol, SymbolRules())
