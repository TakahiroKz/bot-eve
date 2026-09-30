"""MetaTrader5 simulado con posiciones (hedging), SL en el servidor e historial de operaciones."""

import itertools
import time
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd

DTYPE = [("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"),
         ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")]  # fmt: skip


class FakeTradingMt5:
    TRADE_ACTION_DEAL, TRADE_ACTION_SLTP = 1, 6
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    DEAL_ENTRY_IN, DEAL_ENTRY_OUT = 0, 1
    DEAL_REASON_CLIENT, DEAL_REASON_SL = 0, 4
    ACCOUNT_TRADE_MODE_REAL, ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2, 2
    TIMEFRAME_M15, TIMEFRAME_H1, TIMEFRAME_H4 = 15, 16385, 16388

    def __init__(self, real=False, algo=True, session=True, balance=50000.0, server_offset_h=3):
        self.real, self.algo, self.session = real, algo, session
        self.balance, self.leverage = balance, 1000
        self.bid, self.ask = 84000.0, 84030.0
        self.offset = pd.Timedelta(hours=server_offset_h)
        self.positions, self.deals = {}, []
        self.fail_retcode = None  # código a devolver en la próxima orden
        self.sent = []
        self._ids = itertools.count(1000)
        self.rates = None
        self.symbols = {"BTCUSD": NS(name="BTCUSD", digits=3, point=0.001, trade_contract_size=1.0,
                                     volume_min=0.01, volume_step=0.01, volume_max=10.0,
                                     filling_mode=1, trade_stops_level=0)}  # fmt: skip

    # --- conexión -------------------------------------------------------------------------
    def initialize(self):
        return True

    def shutdown(self):
        pass

    def last_error(self):
        return (-1, "error simulado")

    def account_info(self):
        if not self.session:
            return None
        floating = sum((self.bid - p.price_open) * p.volume for p in self.positions.values())
        return NS(balance=self.balance, equity=self.balance + floating, margin_free=self.balance * 0.99,
                  leverage=self.leverage, currency="USD", trade_mode=2 if self.real else 0,
                  margin_mode=2, trade_allowed=True, trade_expert=True)  # fmt: skip

    def terminal_info(self):
        return NS(trade_allowed=self.algo)

    # --- mercado ----------------------------------------------------------------------------
    def symbol_select(self, symbol, enable):
        return symbol in self.symbols

    def symbol_info(self, symbol):
        return self.symbols.get(symbol)

    def symbol_info_tick(self, symbol):
        server_now = pd.Timestamp.now(tz="UTC") + self.offset
        return NS(bid=self.bid, ask=self.ask, time=int(server_now.timestamp()))

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self.rates[-count:] if self.rates is not None else None

    # --- operaciones ------------------------------------------------------------------------
    def positions_get(self, symbol=None, ticket=None):
        found = [p for p in self.positions.values()
                 if (symbol is None or p.symbol == symbol) and (ticket is None or p.ticket == ticket)]  # fmt: skip
        return tuple(found)

    def history_deals_get(self, ticket=None, position=None):
        return tuple(d for d in self.deals
                     if (ticket is None or d.ticket == ticket) and (position is None or d.position_id == position))  # fmt: skip

    def _done(self, **kw):
        return NS(retcode=10009, comment="Done", **kw)

    def _close(self, pos, price, reason):
        commission = -pos.volume * price * 0.001  # 0.1% solo en la salida
        deal = NS(ticket=next(self._ids), position_id=pos.ticket, entry=self.DEAL_ENTRY_OUT,
                  volume=pos.volume, price=price, commission=commission, swap=-3.0, fee=0.0,
                  reason=reason, symbol=pos.symbol)  # fmt: skip
        self.deals.append(deal)
        self.balance += (price - pos.price_open) * pos.volume + commission + deal.swap
        del self.positions[pos.ticket]
        return deal

    def order_send(self, req):
        self.sent.append(req)
        if self.fail_retcode is not None:
            code, self.fail_retcode = self.fail_retcode, None
            return NS(retcode=code, comment="rechazada (simulado)")
        if req["action"] == self.TRADE_ACTION_SLTP:
            pos = self.positions[req["position"]]
            min_dist = self.symbols[pos.symbol].trade_stops_level * 0.001
            if self.bid - req["sl"] < min_dist or req["sl"] >= self.bid:
                return NS(retcode=10016, comment="Invalid stops")
            pos.sl = req["sl"]
            return self._done(order=pos.ticket, deal=0, volume=pos.volume, price=0.0)
        if req["type"] == self.ORDER_TYPE_BUY:
            ticket = next(self._ids)
            self.positions[ticket] = NS(ticket=ticket, symbol=req["symbol"], volume=req["volume"],
                                        price_open=req["price"], sl=0.0, magic=req["magic"])  # fmt: skip
            self.deals.append(NS(ticket=next(self._ids), position_id=ticket, entry=self.DEAL_ENTRY_IN,
                                 volume=req["volume"], price=req["price"], commission=0.0, swap=0.0,
                                 fee=0.0, reason=self.DEAL_REASON_CLIENT, symbol=req["symbol"]))  # fmt: skip
            return self._done(
                order=ticket, deal=self.deals[-1].ticket, volume=req["volume"], price=req["price"]
            )
        pos = self.positions[req["position"]]
        deal = self._close(pos, req["price"], self.DEAL_REASON_CLIENT)
        return self._done(
            order=deal.ticket, deal=deal.ticket, volume=req["volume"], price=req["price"]
        )

    # --- utilidades de prueba -----------------------------------------------------------------
    def trigger_stops(self, low):
        """Si el mínimo toca el SL de una posición, se cierra en el servidor."""
        for pos in list(self.positions.values()):
            if pos.sl and low <= pos.sl:
                self._close(pos, pos.sl, self.DEAL_REASON_SL)


def make_rates(n: int, step_s: int, end: str = None, price: float = 84000.0):
    """n velas que terminan justo antes de `end` (hora del servidor), la última «en formación»."""
    end_ts = pd.Timestamp(end or pd.Timestamp.now(tz="UTC")).floor(f"{step_s}s")
    arr = np.zeros(n, dtype=DTYPE)
    arr["time"] = [
        int((end_ts - pd.Timedelta(seconds=step_s * (n - 1 - i))).timestamp()) for i in range(n)
    ]
    arr["open"], arr["close"] = price, price + 1
    arr["high"], arr["low"] = price + 5, price - 5
    arr["tick_volume"], arr["spread"] = 10, 30000
    return arr


__all__ = ["FakeTradingMt5", "make_rates", "time"]
