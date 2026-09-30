"""Validación de calidad de datos: duplicados, orden, huecos, OHLC inválido y outliers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from bot_eve.data.intervals import to_timedelta

PRICE_COLS = ["open", "high", "low", "close"]


@dataclass
class Gap:
    start: str  # primera vela que falta
    end: str  # última vela que falta
    missing: int


@dataclass
class ValidationReport:
    symbol: str
    interval: str
    rows: int
    first: str | None
    last: str | None
    duplicates: int = 0
    unordered: int = 0
    invalid_ohlc: int = 0
    non_positive_price: int = 0
    negative_volume: int = 0
    gaps: list[Gap] = field(default_factory=list)
    outliers: list[dict] = field(default_factory=list)

    @property
    def missing_candles(self) -> int:
        return sum(g.missing for g in self.gaps)

    @property
    def errors(self) -> list[str]:
        """Problemas que invalidan el dataset (los huecos y outliers son solo avisos)."""
        found = []
        for name in ("duplicates", "unordered", "invalid_ohlc", "non_positive_price",
                     "negative_volume"):  # fmt: skip
            if getattr(self, name):
                found.append(f"{name}={getattr(self, name)}")
        return found

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        data = asdict(self)
        data["missing_candles"] = self.missing_candles
        data["ok"] = self.ok
        return data


def validate_candles(
    df: pd.DataFrame,
    symbol: str,
    interval: str,
    max_jump: float = 0.20,
) -> ValidationReport:
    """Revisa un DataFrame de velas.

    `max_jump`: variación relativa máxima close-a-close antes de marcar un outlier.
    """
    report = ValidationReport(
        symbol=symbol,
        interval=interval,
        rows=len(df),
        first=_iso(df.index.min()) if len(df) else None,
        last=_iso(df.index.max()) if len(df) else None,
    )
    if df.empty:
        return report

    idx = df.index
    report.duplicates = int(idx.duplicated().sum())
    report.unordered = int((idx[1:] < idx[:-1]).sum())

    clean = df[~idx.duplicated(keep="first")].sort_index()

    prices = clean[PRICE_COLS]
    report.non_positive_price = int((prices <= 0).any(axis=1).sum())
    report.negative_volume = int((clean["volume"] < 0).sum())
    high_ok = clean["high"] >= clean[["open", "close", "low"]].max(axis=1)
    low_ok = clean["low"] <= clean[["open", "close", "high"]].min(axis=1)
    report.invalid_ohlc = int((~(high_ok & low_ok)).sum())

    step = to_timedelta(interval)
    diffs = clean.index.to_series().diff()
    for pos in np.flatnonzero(diffs.to_numpy() > step)[:]:
        prev_ts = clean.index[pos - 1]
        cur_ts = clean.index[pos]
        missing = int((cur_ts - prev_ts) / step) - 1
        report.gaps.append(Gap(_iso(prev_ts + step), _iso(cur_ts - step), missing))

    valid_prices = clean["close"].where(clean["close"] > 0)
    jumps = valid_prices.pct_change().abs()
    for ts in jumps[jumps > max_jump].index:
        report.outliers.append({"time": _iso(ts), "jump": round(float(jumps[ts]), 4)})
    return report


def _iso(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")
