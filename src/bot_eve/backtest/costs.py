"""Costos de ejecución y reglas de símbolo de Binance spot."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Costs:
    """Modelo de costos de Binance spot.

    fee_rate: comisión por lado sobre el valor de la operación (0.001 = 0.1%; 0.00075 con BNB).
    slippage: deslizamiento adverso por lado sobre el precio de ejecución (0.0005 = 0.05%).
    """

    fee_rate: float = 0.001
    slippage: float = 0.0005


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
    "BTCUSDT": SymbolRules(step_size=1e-5, min_qty=1e-5, min_notional=5.0),
    "ETHUSDT": SymbolRules(step_size=1e-4, min_qty=1e-4, min_notional=5.0),
    "BNBUSDT": SymbolRules(step_size=1e-3, min_qty=1e-3, min_notional=5.0),
}


def rules_for(symbol: str) -> SymbolRules:
    return DEFAULT_RULES.get(symbol, SymbolRules())
