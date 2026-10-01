"""Interfaz común de brokers. El motor en vivo solo conoce esta interfaz."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from bot_eve.backtest.costs import SymbolRules


class BrokerError(Exception):
    """Fallo al hablar con el broker (red, rechazo de orden, datos inválidos)."""


class BrokerConnectionError(BrokerError):
    """Pérdida transitoria de conexión (timeout, red caída, servicio no disponible, límite de peticiones).

    No indica que algo esté mal con la cuenta ni con las órdenes: los stops siguen en el exchange. El motor
    reintenta sin cerrar posiciones por esta causa.
    """


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: str  # "buy" | "sell"
    qty: float  # cantidad ejecutada (activo base)
    price: float  # precio medio de ejecución
    fee: float  # comisión en `fee_asset`
    fee_asset: str
    order_id: str
    time: pd.Timestamp

    @property
    def base_asset(self) -> str:
        return self.symbol[: -len(_quote_of(self.symbol))] if _quote_of(self.symbol) else ""

    @property
    def net_qty(self) -> float:
        """Cantidad realmente recibida: Binance cobra la comisión de una compra en el activo base."""
        paid_in_base = self.side == "buy" and self.fee_asset == self.base_asset
        return self.qty - self.fee if paid_in_base else self.qty


@dataclass(frozen=True)
class OrderInfo:
    order_id: str
    status: str  # "open" | "filled" | "canceled" | "unknown"
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    fee_asset: str = ""


def fee_in_quote(fill: Fill) -> float:
    """Comisión expresada en el activo de cotización (0 si está en otro activo, p. ej. BNB)."""
    quote = _quote_of(fill.symbol)
    if fill.fee_asset == quote:
        return fill.fee
    if fill.fee_asset == fill.base_asset:
        return fill.fee * fill.price
    return 0.0


def _quote_of(symbol: str) -> str:
    for quote in ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return quote
    return ""


class Broker(ABC):
    name: str = "broker"
    #: True si opera con dinero real
    is_real_money: bool = False

    @abstractmethod
    def now(self) -> pd.Timestamp:
        """Hora actual (UTC) según el broker."""

    @abstractmethod
    def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        """Últimas velas **cerradas** (la vela en formación se excluye), índice `open_time` UTC."""

    @abstractmethod
    def get_price(self, symbol: str) -> float: ...

    @abstractmethod
    def get_balance(self, asset: str) -> float:
        """Saldo libre (disponible) del activo."""

    def equity(self, quote: str, positions: list[tuple[str, float]]) -> float:
        """Capital total. En spot: saldo libre + valor de lo que se tiene (activo - no CFD).
        Un CFD no gasta efectivo al comprar, así que su broker lo sobrescribe."""
        return self.get_balance(quote) + sum(q * self.get_price(sym) for sym, q in positions)

    def buying_power(self, quote: str) -> float:
        """Importe máximo de valor que se puede comprar ahora (spot: el saldo libre)."""
        return self.get_balance(quote)

    @abstractmethod
    def get_symbol_rules(self, symbol: str) -> SymbolRules: ...

    @abstractmethod
    def market_buy(self, symbol: str, qty: float) -> Fill: ...

    @abstractmethod
    def market_sell(self, symbol: str, qty: float) -> Fill: ...

    @abstractmethod
    def place_stop_loss(
        self, symbol: str, qty: float, stop_price: float, limit_price: float
    ) -> str:
        """Orden de venta con stop en el exchange (sigue activa aunque el bot se caiga)."""

    @abstractmethod
    def get_order(self, symbol: str, order_id: str) -> OrderInfo: ...

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> None: ...
