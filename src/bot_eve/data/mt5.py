"""Historial y especificaciones de símbolos desde MetaTrader 5 (solo Windows).

Usa la terminal MT5 ya abierta y con sesión iniciada: no se piden ni guardan credenciales.
Los tiempos de las velas están en **hora del servidor del broker** (no UTC). Se guardan tal
cual, etiquetados como UTC, y el bot trabajará con esa misma hora para ser consistente.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from bot_eve.data.store import CandleStore

log = logging.getLogger(__name__)

TIMEFRAMES = {
    "1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15",
    "1h": "TIMEFRAME_H1", "4h": "TIMEFRAME_H4",
}  # fmt: skip
MT5_COLUMNS = ["open", "high", "low", "close", "volume", "spread"]


class Mt5Error(Exception):
    pass


def load_mt5():
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise Mt5Error(
            "No se pudo importar MetaTrader5. Solo existe para Windows: pip install MetaTrader5"
        ) from exc
    return mt5


def rates_to_frame(rates) -> pd.DataFrame:
    """Convierte el array estructurado de `copy_rates_*` al formato de velas del proyecto."""
    if rates is None or len(rates) == 0:
        return pd.DataFrame(
            columns=MT5_COLUMNS, index=pd.DatetimeIndex([], tz="UTC", name="open_time")
        )
    df = pd.DataFrame(rates)
    df.index = pd.DatetimeIndex(
        pd.to_datetime(df.pop("time"), unit="s", utc=True), name="open_time"
    )
    df = df.rename(columns={"tick_volume": "volume"})[MT5_COLUMNS].astype(float)
    return df[~df.index.duplicated(keep="last")].sort_index()


@dataclass
class SymbolSpec:
    symbol: str
    digits: int
    point: float
    contract_size: float
    volume_min: float
    volume_step: float
    volume_max: float
    spread_points: float
    swap_long: float
    swap_short: float
    swap_mode: int
    stops_level: int
    price: float

    @property
    def swap_long_pct_per_day(self) -> float | None:
        """Swap largo diario como % del valor, solo si el swap está en puntos (modo 1)."""
        if self.swap_mode != 1 or self.price <= 0:
            return None
        return self.swap_long * self.point / self.price

    @property
    def spread_pct(self) -> float:
        return self.spread_points * self.point / self.price if self.price > 0 else float("nan")


class Mt5Client:
    def __init__(self, mt5=None) -> None:
        self.mt5 = mt5 or load_mt5()

    def connect(self) -> None:
        if not self.mt5.initialize():
            raise Mt5Error(
                f"No se pudo conectar con la terminal MT5: {self.mt5.last_error()}. "
                "Abre MetaTrader 5, inicia sesión en la cuenta y vuelve a intentar."
            )

    def shutdown(self) -> None:
        self.mt5.shutdown()

    def account_summary(self) -> dict:
        """Datos de la cuenta SIN login, nombre ni empresa."""
        acc, term = self.mt5.account_info(), self.mt5.terminal_info()
        if acc is None:
            raise Mt5Error("No hay una cuenta con sesión iniciada en la terminal.")
        modes = {0: "netting", 1: "exchange", 2: "hedging"}
        return {
            "servidor": acc.server,
            "apalancamiento": acc.leverage,
            "moneda": acc.currency,
            "saldo": acc.balance,
            "modo_de_margen": modes.get(acc.margin_mode, acc.margin_mode),
            "cuenta_permite_trading": bool(acc.trade_allowed),
            "permite_robots_en_la_cuenta": bool(acc.trade_expert),
            "terminal_permite_trading_algoritmico": bool(term.trade_allowed) if term else None,
        }

    def symbol_spec(self, symbol: str) -> SymbolSpec:
        if not self.mt5.symbol_select(symbol, True):
            raise Mt5Error(f"El símbolo {symbol} no existe o no se pudo activar en Market Watch.")
        info, tick = self.mt5.symbol_info(symbol), self.mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise Mt5Error(f"Sin datos del símbolo {symbol}.")
        return SymbolSpec(
            symbol, info.digits, info.point, info.trade_contract_size, info.volume_min,
            info.volume_step, info.volume_max, info.spread, info.swap_long, info.swap_short,
            info.swap_mode, info.trade_stops_level, (tick.bid + tick.ask) / 2,
        )  # fmt: skip

    def download(self, symbol: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Descarga [start, end] por meses (evita el límite de barras de la terminal)."""
        if interval not in TIMEFRAMES:
            raise Mt5Error(f"Intervalo no soportado: {interval}. Usa {sorted(TIMEFRAMES)}")
        timeframe = getattr(self.mt5, TIMEFRAMES[interval])
        if not self.mt5.symbol_select(symbol, True):
            raise Mt5Error(f"El símbolo {symbol} no existe o no se pudo activar.")
        frames, cursor = [], start
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=31), end)
            rates = self.mt5.copy_rates_range(symbol, timeframe, cursor, chunk_end)
            if rates is None:
                raise Mt5Error(f"copy_rates_range falló para {symbol}: {self.mt5.last_error()}")
            frames.append(rates_to_frame(rates))
            cursor = chunk_end
        frames = [f for f in frames if not f.empty]
        if not frames:
            return rates_to_frame(None)
        df = pd.concat(frames)
        return df[~df.index.duplicated(keep="last")].sort_index()


def sync_symbol(
    client: Mt5Client, store: CandleStore, symbol: str, interval: str, start: str,
    now: datetime | None = None,
) -> int:  # fmt: skip
    """Descarga y guarda por meses; devuelve cuántas velas se escribieron."""
    now = now or datetime.now(UTC)
    first = datetime.strptime(start, "%Y-%m").replace(tzinfo=UTC)
    df = client.download(symbol, interval, first, now + timedelta(days=1))
    written = 0
    for month, part in df.groupby(df.index.strftime("%Y-%m")):
        store.write_month(symbol, interval, month, part)
        written += len(part)
    if df.empty:
        log.warning("%s %s: el broker no devolvió velas desde %s", symbol, interval, start)
    else:
        log.info("%s %s: %d velas (%s -> %s)", symbol, interval, len(df), df.index[0], df.index[-1])
    return written


def median_spread_pct(store: CandleStore, symbol: str, interval: str, point: float) -> float:
    """Spread mediano histórico como % del precio (usa la columna `spread` en puntos)."""
    df = store.read(symbol, interval)
    if df.empty or "spread" not in df:
        return float("nan")
    return float((df["spread"] * point / df["close"]).median())


DEFAULT_STORE = Path("data_store") / "mt5"
