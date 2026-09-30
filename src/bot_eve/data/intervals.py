"""Utilidades para intervalos de velas ('1m', '5m', '1h', '4h', '1d')."""

from __future__ import annotations

import re

import pandas as pd

_UNITS = {"m": "min", "h": "h", "d": "D"}
_PATTERN = re.compile(r"^(\d+)([mhd])$")


def parse_interval(interval: str) -> tuple[int, str]:
    match = _PATTERN.match(interval)
    if not match or int(match.group(1)) <= 0:
        raise ValueError(f"Intervalo inválido: {interval!r} (ejemplos: 1m, 5m, 1h, 4h)")
    return int(match.group(1)), match.group(2)


def to_timedelta(interval: str) -> pd.Timedelta:
    n, unit = parse_interval(interval)
    return pd.Timedelta(n, unit=_UNITS[unit])


def to_pandas_rule(interval: str) -> str:
    n, unit = parse_interval(interval)
    return f"{n}{_UNITS[unit]}"
