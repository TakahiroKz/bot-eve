"""Conector de Binance spot sobre ccxt (Testnet o real).

Las señales pueden calcularse con velas del mercado real (API pública) aunque las órdenes
vayan al Testnet: los precios del testnet no son fiables. Las órdenes de stop se colocan
**en el exchange** (STOP_LOSS_LIMIT), así que siguen activas si el bot o el PC se caen.
El objetivo (take profit) lo gestiona el bot: un OCO requeriría otro endpoint y dejaría
saldo bloqueado por dos órdenes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import ccxt
import pandas as pd

from bot_eve.backtest.costs import SymbolRules
from bot_eve.data.intervals import to_timedelta
from bot_eve.execution.base import Broker, BrokerError, Fill, OrderInfo, _quote_of

log = logging.getLogger(__name__)

_STATUS = {"open": "open", "closed": "filled", "canceled": "canceled",
           "expired": "canceled", "rejected": "canceled"}  # fmt: skip


def to_ccxt_symbol(symbol: str) -> str:
    quote = _quote_of(symbol)
    if not quote:
        raise BrokerError(f"No se reconoce el activo de cotización de {symbol}")
    return f"{symbol[: -len(quote)]}/{quote}"


class BinanceBroker(Broker):
    name = "binance"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        data_from_production: bool = True,
        exchange_factory: Callable[[dict], ccxt.Exchange] | None = None,
    ) -> None:
        factory = exchange_factory or (lambda opts: ccxt.binance(opts))
        base_opts = {"enableRateLimit": True, "timeout": 20000}
        self.testnet = testnet
        self.is_real_money = not testnet
        self.ex = factory(
            {
                **base_opts,
                "apiKey": api_key,
                "secret": api_secret,
                "options": {"defaultType": "spot", "adjustForTimeDifference": True},
            }
        )
        if testnet:
            self.ex.set_sandbox_mode(True)
        # Datos públicos: del mercado real si se pide, si no del mismo exchange.
        self.data_ex = factory(base_opts) if (testnet and data_from_production) else self.ex
        self._markets_loaded: set[int] = set()
        self._clock_offset = pd.Timedelta(0)
        self._offset_at = 0.0

    # --- utilidades -------------------------------------------------------------------
    def _market(self, ex: ccxt.Exchange, symbol: str) -> dict:
        if id(ex) not in self._markets_loaded:
            self._call(ex.load_markets)
            self._markets_loaded.add(id(ex))
        return ex.market(to_ccxt_symbol(symbol))

    @staticmethod
    def _call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ccxt.BaseError as exc:
            raise BrokerError(f"{type(exc).__name__}: {exc}") from exc

    # --- interfaz Broker -----------------------------------------------------------------
    def now(self) -> pd.Timestamp:
        """Hora del servidor (se corrige con la diferencia medida cada 10 minutos)."""
        if time.monotonic() - self._offset_at > 600:
            server = pd.Timestamp(self._call(self.ex.fetch_time), unit="ms", tz="UTC")
            self._clock_offset = server - pd.Timestamp.now(tz="UTC")
            self._offset_at = time.monotonic()
        return pd.Timestamp.now(tz="UTC") + self._clock_offset

    def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        raw = self._call(
            self.data_ex.fetch_ohlcv, to_ccxt_symbol(symbol), interval, limit=limit + 1
        )
        if not raw:
            raise BrokerError(f"Sin velas para {symbol} {interval}")
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        df.index = pd.DatetimeIndex(
            pd.to_datetime(df.pop("ts"), unit="ms", utc=True), name="open_time"
        )
        closed = df[df.index + to_timedelta(interval) <= self.now()]  # sin la vela en formación
        return closed.tail(limit).astype(float)

    def get_price(self, symbol: str) -> float:
        ticker = self._call(self.ex.fetch_ticker, to_ccxt_symbol(symbol))
        price = ticker.get("last")
        if not price:
            raise BrokerError(f"Precio no disponible para {symbol}")
        return float(price)

    def get_balance(self, asset: str) -> float:
        balance = self._call(self.ex.fetch_balance)
        return float(balance.get("free", {}).get(asset, 0.0) or 0.0)

    def get_symbol_rules(self, symbol: str) -> SymbolRules:
        market = self._market(self.ex, symbol)
        filters = {f["filterType"]: f for f in market["info"].get("filters", [])}
        lot = filters.get("LOT_SIZE")
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        if lot is None:
            raise BrokerError(f"{symbol}: el exchange no informa LOT_SIZE")
        return SymbolRules(
            step_size=float(lot["stepSize"]),
            min_qty=float(lot["minQty"]),
            min_notional=float(notional.get("minNotional", 0.0)),
        )

    def _to_fill(self, symbol: str, side: str, order: dict) -> Fill:
        if not order.get("filled") or not order.get("average"):
            order = self._call(self.ex.fetch_order, order["id"], to_ccxt_symbol(symbol))
        filled, avg = float(order.get("filled") or 0), float(order.get("average") or 0)
        if filled <= 0 or avg <= 0:
            raise BrokerError(
                f"La orden {order.get('id')} no quedó ejecutada: {order.get('status')}"
            )
        quote = _quote_of(symbol)
        base = symbol[: -len(quote)]
        fees: dict[str, float] = {}
        for fee in order.get("fees") or ([order["fee"]] if order.get("fee") else []):
            if fee and fee.get("cost"):
                fees[fee["currency"]] = fees.get(fee["currency"], 0.0) + float(fee["cost"])
        if len(fees) > 1:
            log.warning("%s: comisiones en varios activos %s", symbol, fees)
        asset = base if base in fees else (quote if quote in fees else next(iter(fees), quote))
        return Fill(
            symbol, side, filled, avg, fees.get(asset, 0.0), asset,
            str(order["id"]), pd.Timestamp(order.get("timestamp") or 0, unit="ms", tz="UTC"),
        )  # fmt: skip

    def market_buy(self, symbol: str, qty: float) -> Fill:
        order = self._call(self.ex.create_order, to_ccxt_symbol(symbol), "market", "buy", qty)
        return self._to_fill(symbol, "buy", order)

    def market_sell(self, symbol: str, qty: float) -> Fill:
        order = self._call(self.ex.create_order, to_ccxt_symbol(symbol), "market", "sell", qty)
        return self._to_fill(symbol, "sell", order)

    def place_stop_loss(
        self, symbol: str, qty: float, stop_price: float, limit_price: float
    ) -> str:
        order = self._call(
            self.ex.create_order,
            to_ccxt_symbol(symbol), "limit", "sell", qty, limit_price,
            {"stopLossPrice": stop_price, "timeInForce": "GTC"},
        )  # fmt: skip
        return str(order["id"])

    def get_order(self, symbol: str, order_id: str) -> OrderInfo:
        try:
            order = self.ex.fetch_order(order_id, to_ccxt_symbol(symbol))
        except ccxt.OrderNotFound:
            return OrderInfo(order_id, "unknown")
        except ccxt.BaseError as exc:
            raise BrokerError(f"{type(exc).__name__}: {exc}") from exc
        quote = _quote_of(symbol)
        fee = order.get("fee") or {}
        return OrderInfo(
            order_id,
            _STATUS.get(order.get("status"), "unknown"),
            float(order.get("filled") or 0),
            float(order.get("average") or 0),
            float(fee.get("cost") or 0),
            fee.get("currency") or quote,
        )

    def cancel_order(self, symbol: str, order_id: str) -> None:
        try:
            self.ex.cancel_order(order_id, to_ccxt_symbol(symbol))
        except ccxt.OrderNotFound:
            return  # ya ejecutada o cancelada
        except ccxt.BaseError as exc:
            raise BrokerError(f"{type(exc).__name__}: {exc}") from exc
