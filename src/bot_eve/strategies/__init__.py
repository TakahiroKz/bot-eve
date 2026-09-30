"""Registro de estrategias disponibles."""

from __future__ import annotations

from bot_eve.strategies.base import Strategy
from bot_eve.strategies.sma_cross import SmaCross

REGISTRY: dict[str, type[Strategy]] = {SmaCross.name: SmaCross}


def build_strategy(name: str, **params) -> Strategy:
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Estrategia desconocida: {name!r}. Disponibles: {sorted(REGISTRY)}"
        ) from None
    return cls(**params)
