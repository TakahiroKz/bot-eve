"""Almacenamiento en Parquet: una partición por símbolo, intervalo y mes.

Estructura: <root>/<SYMBOL>/<interval>/<YYYY-MM>.parquet
Las velas usan un índice `open_time` (DatetimeIndex UTC, sin duplicados, ordenado).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CANDLE_COLUMNS = ["open", "high", "low", "close", "volume", "quote_volume", "trades"]


class CandleStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _dir(self, symbol: str, interval: str) -> Path:
        return self.root / symbol / interval

    def path(self, symbol: str, interval: str, month: str) -> Path:
        return self._dir(symbol, interval) / f"{month}.parquet"

    def months(self, symbol: str, interval: str) -> list[str]:
        directory = self._dir(symbol, interval)
        if not directory.exists():
            return []
        return sorted(p.stem for p in directory.glob("*.parquet"))

    def has_month(self, symbol: str, interval: str, month: str) -> bool:
        return self.path(symbol, interval, month).exists()

    def write_month(self, symbol: str, interval: str, month: str, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError(f"No se guarda una partición vacía: {symbol} {interval} {month}")
        target = self.path(symbol, interval, month)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".parquet.tmp")
        df.to_parquet(tmp)
        tmp.replace(target)  # escritura atómica: nunca queda un archivo a medias

    def read_month(self, symbol: str, interval: str, month: str) -> pd.DataFrame:
        return pd.read_parquet(self.path(symbol, interval, month))

    def read(
        self,
        symbol: str,
        interval: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Lee todas las particiones (opcionalmente recortadas a [start, end])."""
        frames = [self.read_month(symbol, interval, m) for m in self.months(symbol, interval)]
        if not frames:
            return pd.DataFrame(columns=CANDLE_COLUMNS, index=_empty_index())
        df = pd.concat(frames)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        if start is not None:
            df = df[df.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end, tz="UTC")]
        return df


def _empty_index() -> pd.DatetimeIndex:
    return pd.DatetimeIndex([], tz="UTC", name="open_time")
