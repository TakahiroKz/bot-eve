"""Descarga de velas de spot desde data.binance.vision (datos públicos, sin API key).

- Archivos mensuales para meses cerrados; diarios cuando el mensual aún no existe
  (mes en curso o recién terminado).
- Desde 2025 los timestamps de spot vienen en microsegundos; aquí se normalizan.
- La sincronización es reanudable: los meses completos ya descargados se omiten.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import httpx
import pandas as pd

from bot_eve.data.resample import resample_ohlcv
from bot_eve.data.store import CANDLE_COLUMNS, CandleStore

log = logging.getLogger(__name__)

_RAW_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]  # fmt: skip
_RETRIES = 4


def month_url(base_url: str, symbol: str, interval: str, month: str) -> str:
    return (
        f"{base_url}/data/spot/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"
    )


def daily_url(base_url: str, symbol: str, interval: str, day: date) -> str:
    return (
        f"{base_url}/data/spot/daily/klines/{symbol}/{interval}/"
        f"{symbol}-{interval}-{day.isoformat()}.zip"
    )


def parse_klines_zip(content: bytes) -> pd.DataFrame:
    """Convierte un zip de klines de Binance en un DataFrame con índice `open_time` UTC."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        with zf.open(zf.namelist()[0]) as fh:
            raw = pd.read_csv(fh, header=None, names=_RAW_COLUMNS, dtype=str)
    # Algunos archivos traen fila de encabezado.
    raw = raw[pd.to_numeric(raw["open_time"], errors="coerce").notna()]
    if raw.empty:
        return _empty_candles()
    ts = raw["open_time"].astype("int64")
    unit = "us" if ts.max() > 10**14 else "ms"
    df = raw[CANDLE_COLUMNS].apply(pd.to_numeric)
    df["trades"] = df["trades"].astype("int64")
    df.index = pd.DatetimeIndex(pd.to_datetime(ts, unit=unit, utc=True), name="open_time")
    df.index = df.index.as_unit("ms")
    return df[~df.index.duplicated(keep="last")].sort_index()


def _empty_candles() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz="UTC", name="open_time")
    return pd.DataFrame(columns=CANDLE_COLUMNS, index=idx)


def _get(client: httpx.Client, url: str) -> bytes | None:
    """GET con reintentos. Devuelve None si el archivo no existe (404)."""
    for attempt in range(_RETRIES):
        try:
            resp = client.get(url)
        except httpx.HTTPError as exc:
            error: Exception = exc
        else:
            if resp.status_code == 404:
                return None
            if resp.status_code == 200:
                return resp.content
            error = RuntimeError(f"HTTP {resp.status_code}")
        if attempt == _RETRIES - 1:
            raise RuntimeError(f"Falló la descarga de {url}: {error}") from error
        time.sleep(2**attempt)
    return None  # inalcanzable


def _month_bounds(month: str) -> tuple[date, date]:
    first = datetime.strptime(month, "%Y-%m").date()
    nxt = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return first, nxt - timedelta(days=1)


def iter_months(start: str, end: str) -> Iterator[str]:
    """Meses 'YYYY-MM' desde `start` hasta `end` inclusive."""
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


class KlineDownloader:
    def __init__(
        self,
        store: CandleStore,
        base_url: str = "https://data.binance.vision",
        interval: str = "1m",
        workers: int = 4,
        client: httpx.Client | None = None,
    ) -> None:
        self.store = store
        self.base_url = base_url.rstrip("/")
        self.interval = interval
        self.workers = workers
        self.client = client or httpx.Client(timeout=60, follow_redirects=True)

    def _is_complete(self, symbol: str, month: str, today: date) -> bool:
        """Un mes ya cerrado y guardado se considera completo si llega hasta su último día."""
        first, last = _month_bounds(month)
        if last >= today or not self.store.has_month(symbol, self.interval, month):
            return False
        df = self.store.read_month(symbol, self.interval, month)
        end = pd.Timestamp(last, tz="UTC") + timedelta(days=1)
        return bool(df.index.max() >= end - timedelta(days=1))

    def _fetch_month(self, symbol: str, month: str, today: date) -> pd.DataFrame:
        first, last = _month_bounds(month)
        if last < today:
            content = _get(self.client, month_url(self.base_url, symbol, self.interval, month))
            if content is not None:
                return parse_klines_zip(content)
        # Mes en curso o mensual aún no publicado: archivos diarios.
        days = [first + timedelta(days=i) for i in range((min(last, today) - first).days + 1)]
        urls = [daily_url(self.base_url, symbol, self.interval, d) for d in days]
        with ThreadPoolExecutor(self.workers) as pool:
            contents = list(pool.map(lambda u: _get(self.client, u), urls))
        frames = [parse_klines_zip(c) for c in contents if c is not None]
        return pd.concat(frames).sort_index() if frames else _empty_candles()

    def sync(
        self,
        symbol: str,
        start: str,
        resample: list[str] | None = None,
        today: date | None = None,
    ) -> list[str]:
        """Descarga los meses que falten y regenera los intervalos remuestreados.

        Devuelve la lista de meses escritos.
        """
        today = today or datetime.now(UTC).date()
        end_month = today.strftime("%Y-%m")
        written: list[str] = []
        for month in iter_months(start, end_month):
            if self._is_complete(symbol, month, today):
                continue
            df = self._fetch_month(symbol, month, today)
            if df.empty:
                log.warning("%s %s: sin datos disponibles", symbol, month)
                continue
            self.store.write_month(symbol, self.interval, month, df)
            for target in resample or []:
                self.store.write_month(symbol, target, month, resample_ohlcv(df, target))
            written.append(month)
            log.info("%s %s: %d velas", symbol, month, len(df))
        return written
