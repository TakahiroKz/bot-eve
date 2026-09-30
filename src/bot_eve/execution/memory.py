"""Broker en memoria: simula un exchange spot sin red. Para pruebas y simulacros."""

from __future__ import annotations

import itertools

import pandas as pd

from bot_eve.backtest.costs import SymbolRules
from bot_eve.data.intervals import to_timedelta
from bot_eve.execution.base import Broker, BrokerError, Fill, OrderInfo, _quote_of


class InMemoryBroker(Broker):
    name = "memory"

    def __init__(
        self,
        balances: dict[str, float],
        fee_rate: float = 0.001,
        rules: dict[str, SymbolRules] | None = None,
    ) -> None:
        self.free = dict(balances)
        self.fee_rate = fee_rate
        self.rules = rules or {}
        self.candles: dict[tuple[str, str], pd.DataFrame] = {}
        self.prices: dict[str, float] = {}
        self.orders: dict[str, dict] = {}
        self.fills: list[Fill] = []
        self.fail_with: Exception | None = None  # se lanza en la próxima operación
        self._now = pd.Timestamp("2024-01-01", tz="UTC")
        self._ids = itertools.count(1)

    # --- control del simulador -------------------------------------------------------
    def set_time(self, ts: str | pd.Timestamp) -> None:
        ts = pd.Timestamp(ts)
        self._now = ts.tz_localize("UTC") if ts.tzinfo is None else ts

    def set_price(self, symbol: str, price: float, low: float | None = None) -> None:
        """Fija el precio y dispara los stops tocados (por `low` si se da)."""
        self.prices[symbol] = price
        trigger = price if low is None else min(low, price)
        for oid, order in self.orders.items():
            if order["status"] == "open" and order["symbol"] == symbol:
                if trigger <= order["stop_price"]:
                    self._fill_stop(oid, order)

    def _fill_stop(self, oid: str, order: dict) -> None:
        price = order["limit_price"]
        proceeds = order["qty"] * price
        fee = proceeds * self.fee_rate
        quote = _quote_of(order["symbol"])
        self.free[quote] = self.free.get(quote, 0.0) + proceeds - fee
        order.update(status="filled", avg_price=price, fee=fee, fee_asset=quote)

    def _check(self) -> None:
        if self.fail_with is not None:
            err, self.fail_with = self.fail_with, None
            raise err

    # --- interfaz Broker ---------------------------------------------------------------
    def now(self) -> pd.Timestamp:
        return self._now

    def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        self._check()
        df = self.candles.get((symbol, interval))
        if df is None:
            raise BrokerError(f"Sin velas para {symbol} {interval}")
        closed = df[df.index + to_timedelta(interval) <= self._now]
        return closed.tail(limit)

    def get_price(self, symbol: str) -> float:
        self._check()
        if symbol not in self.prices:
            raise BrokerError(f"Sin precio para {symbol}")
        return self.prices[symbol]

    def get_balance(self, asset: str) -> float:
        self._check()
        return self.free.get(asset, 0.0)

    def get_symbol_rules(self, symbol: str) -> SymbolRules:
        return self.rules.get(symbol, SymbolRules(1e-5, 1e-5, 5.0))

    def _fill(self, symbol: str, side: str, qty: float, price: float, fee: float, asset: str):
        fill = Fill(symbol, side, qty, price, fee, asset, f"m{next(self._ids)}", self._now)
        self.fills.append(fill)
        return fill

    def market_buy(self, symbol: str, qty: float) -> Fill:
        self._check()
        quote, price = _quote_of(symbol), self.get_price(symbol)
        base = symbol[: -len(quote)]
        if qty * price > self.free.get(quote, 0.0) + 1e-9:
            raise BrokerError("Saldo insuficiente")
        fee = qty * self.fee_rate  # Binance cobra la compra en el activo base
        self.free[quote] -= qty * price
        self.free[base] = self.free.get(base, 0.0) + qty - fee
        return self._fill(symbol, "buy", qty, price, fee, base)

    def market_sell(self, symbol: str, qty: float) -> Fill:
        self._check()
        quote, price = _quote_of(symbol), self.get_price(symbol)
        base = symbol[: -len(quote)]
        if qty > self.free.get(base, 0.0) + 1e-12:
            raise BrokerError("Saldo libre insuficiente (¿bloqueado por un stop?)")
        proceeds = qty * price
        fee = proceeds * self.fee_rate
        self.free[base] -= qty
        self.free[quote] = self.free.get(quote, 0.0) + proceeds - fee
        return self._fill(symbol, "sell", qty, price, fee, quote)

    def place_stop_loss(
        self, symbol: str, qty: float, stop_price: float, limit_price: float
    ) -> str:
        self._check()
        base = symbol[: -len(_quote_of(symbol))]
        if qty > self.free.get(base, 0.0) + 1e-12:
            raise BrokerError("Saldo libre insuficiente para el stop")
        self.free[base] -= qty  # el stop bloquea el activo
        oid = f"s{next(self._ids)}"
        self.orders[oid] = {
            "symbol": symbol, "qty": qty, "stop_price": stop_price,
            "limit_price": limit_price, "status": "open",
        }  # fmt: skip
        return oid

    def get_order(self, symbol: str, order_id: str) -> OrderInfo:
        self._check()
        order = self.orders.get(order_id)
        if order is None:
            return OrderInfo(order_id, "unknown")
        return OrderInfo(
            order_id,
            order["status"],
            order["qty"] if order["status"] == "filled" else 0.0,
            order.get("avg_price", 0.0),
            order.get("fee", 0.0),
            order.get("fee_asset", ""),
        )

    def cancel_order(self, symbol: str, order_id: str) -> None:
        self._check()
        order = self.orders.get(order_id)
        if order and order["status"] == "open":
            order["status"] = "canceled"
            base = symbol[: -len(_quote_of(symbol))]
            self.free[base] = self.free.get(base, 0.0) + order["qty"]
