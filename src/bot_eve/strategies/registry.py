"""Registro de estrategias: añadir una es crear un archivo con `@register`; quitarla, borrarlo."""

from __future__ import annotations

from typing import TypeVar

from bot_eve.strategies.base import Strategy

REGISTRY: dict[str, type[Strategy]] = {}

T = TypeVar("T", bound=type[Strategy])


def register(cls: T) -> T:
    """Decorador de clase: registra la estrategia bajo su atributo `name`."""
    name = cls.name
    if name in REGISTRY and REGISTRY[name] is not cls:
        raise ValueError(f"Ya existe una estrategia registrada con el nombre {name!r}")
    REGISTRY[name] = cls
    return cls


def build_strategy(name: str, **params) -> Strategy:
    try:
        cls = REGISTRY[name]
    except KeyError:
        available = sorted(REGISTRY)
        raise ValueError(f"Estrategia desconocida: {name!r}. Disponibles: {available}") from None
    return cls(**params)
