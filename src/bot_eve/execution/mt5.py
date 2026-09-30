"""Conector de órdenes de MetaTrader 5 (solo Windows; CFD).

Diferencias con el spot de Binance que se resuelven aquí:
- Un CFD no gasta efectivo al comprar: `equity()` es el capital de la cuenta y el poder de
  compra se limita a 1x el capital (aunque el apalancamiento sea 1:1000).
- El stop es el **SL de la posición** en el servidor (sigue activo aunque el bot o el PC se
  caigan). `place_stop_loss` lo fija y devuelve el ticket de la posición; el «limit» se ignora.
- Cerrar la posición elimina su SL, por eso `cancel_order` no hace nada.
- La cantidad del motor está en unidades del activo; los lotes son cantidad / tamaño de contrato.
- Las velas y la hora son las del **servidor del broker** (no UTC), igual que en la investigación.
- Se detecta si la cuenta es real o demo desde el propio MT5: no se confía en la configuración.
"""

from __future__ import annotations

import logging
import time

import pandas as pd

from bot_eve.backtest.costs import SymbolRules
from bot_eve.data.intervals import to_timedelta
from bot_eve.data.mt5 import TIMEFRAMES, load_mt5, rates_to_frame
from bot_eve.execution.base import Broker, BrokerError, Fill, OrderInfo

log = logging.getLogger(__name__)

MAGIC = 20260930  # identifica las órdenes del bot
COMMENT = "bot-eve"
RETCODE_DONE = 10009
FILL_FOK, FILL_IOC = 1, 2  # bits de symbol_info.filling_mode


class Mt5Broker(Broker):
    name = "mt5"

    def __init__(self, reference_symbol: str = "BTCUSD", mt5=None) -> None:
        self.mt5 = mt5 or load_mt5()
        self.reference_symbol = reference_symbol
        self._clock_offset = pd.Timedelta(0)
        self._offset_at: float | None = None
        self._connect()

    # --- conexión y comprobaciones de seguridad --------------------------------------------
    def _connect(self) -> None:
        if not self.mt5.initialize():
            raise BrokerError(
                f"No se pudo conectar con la terminal MT5: {self.mt5.last_error()}. "
                "Abre MetaTrader 5 e inicia sesión en la cuenta."
            )
        acc, term = self.mt5.account_info(), self.mt5.terminal_info()
        if acc is None:
            raise BrokerError("No hay una cuenta con sesión iniciada en MT5.")
        if not (term and term.trade_allowed):
            raise BrokerError(
                "El trading algorítmico está desactivado en la terminal. Pulsa el botón "
                "«Algo Trading» de la barra de herramientas (debe quedar en verde). Se apaga "
                "al cambiar de cuenta."
            )
        if not (acc.trade_allowed and acc.trade_expert):
            raise BrokerError(
                "La cuenta no permite operar con robots (trade_expert/trade_allowed)."
            )
        self.is_real_money = acc.trade_mode == getattr(self.mt5, "ACCOUNT_TRADE_MODE_REAL", 2)
        self.currency, self.leverage = acc.currency, acc.leverage
        self.hedging = acc.margin_mode == getattr(self.mt5, "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", 2)
        log.info("MT5: cuenta %s, %s, apalancamiento %s", "REAL" if self.is_real_money else "demo",
                 "hedging" if self.hedging else "netting", self.leverage)  # fmt: skip

    def close(self) -> None:
        self.mt5.shutdown()

    def _info(self, symbol: str):
        if not self.mt5.symbol_select(symbol, True):
            raise BrokerError(f"El símbolo {symbol} no existe o no se pudo activar en MT5.")
        info = self.mt5.symbol_info(symbol)
        if info is None:
            raise BrokerError(f"Sin información del símbolo {symbol}.")
        return info

    def _tick(self, symbol: str):
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None or tick.bid <= 0:
            raise BrokerError(f"Sin cotización de {symbol}.")
        return tick

    # --- interfaz Broker -------------------------------------------------------------------
    def now(self) -> pd.Timestamp:
        """Hora del servidor del broker (corregida cada 10 minutos con la última cotización)."""
        if self._offset_at is None or time.monotonic() - self._offset_at > 600:
            tick = self._tick(self.reference_symbol)
            server = pd.Timestamp(tick.time, unit="s", tz="UTC")
            self._clock_offset = server - pd.Timestamp.now(tz="UTC")
            self._offset_at = time.monotonic()
        return pd.Timestamp.now(tz="UTC") + self._clock_offset

    def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        if interval not in TIMEFRAMES:
            raise BrokerError(f"Intervalo no soportado en MT5: {interval}")
        self._info(symbol)
        rates = self.mt5.copy_rates_from_pos(
            symbol, getattr(self.mt5, TIMEFRAMES[interval]), 0, limit + 1
        )
        if rates is None or len(rates) == 0:
            raise BrokerError(
                f"MT5 no devolvió velas de {symbol} {interval}: {self.mt5.last_error()}"
            )
        df = rates_to_frame(rates)
        closed = df[df.index + to_timedelta(interval) <= self.now()]  # sin la vela en formación
        return closed.tail(limit)[["open", "high", "low", "close", "volume"]]

    def get_price(self, symbol: str) -> float:
        return float(
            self._tick(symbol).bid
        )  # el gráfico va a precio bid; conservador para el valor

    def get_balance(self, asset: str) -> float:
        """Moneda de la cuenta: saldo. Activo base de un símbolo: unidades en posiciones abiertas."""
        if asset == self.currency:
            return float(self.mt5.account_info().balance)
        total = 0.0
        for pos in self.mt5.positions_get() or []:
            if pos.magic == MAGIC and pos.symbol.startswith(asset):
                total += pos.volume * self._info(pos.symbol).trade_contract_size
        return total

    def equity(self, quote: str, positions: list[tuple[str, float]]) -> float:
        return float(self.mt5.account_info().equity)  # incluye la ganancia/pérdida flotante

    def buying_power(self, quote: str) -> float:
        """Como máximo 1x el capital, aunque el apalancamiento de la cuenta sea mayor."""
        acc = self.mt5.account_info()
        return float(min(acc.margin_free * acc.leverage, acc.equity))

    def get_symbol_rules(self, symbol: str) -> SymbolRules:
        info = self._info(symbol)
        size = info.trade_contract_size
        return SymbolRules(
            step_size=info.volume_step * size, min_qty=info.volume_min * size, min_notional=0.0
        )

    # --- órdenes ------------------------------------------------------------------------------
    def _lots(self, info, qty: float) -> float:
        lots = round(qty / info.trade_contract_size, 8)
        step = info.volume_step
        lots = round(int(lots / step + 1e-9) * step, 8)
        if lots < info.volume_min - 1e-12:
            raise BrokerError(f"{info.name}: {lots} lotes < mínimo {info.volume_min}")
        return min(lots, info.volume_max)

    def _send(self, request: dict):
        result = self.mt5.order_send(request)
        if result is None:
            raise BrokerError(f"order_send falló: {self.mt5.last_error()}")
        if result.retcode != RETCODE_DONE:
            raise BrokerError(f"MT5 rechazó la orden (retcode {result.retcode}): {result.comment}")
        return result

    def _filling(self, info) -> int:
        mode = info.filling_mode
        if mode & FILL_FOK:
            return self.mt5.ORDER_FILLING_FOK
        if mode & FILL_IOC:
            return self.mt5.ORDER_FILLING_IOC
        return self.mt5.ORDER_FILLING_RETURN

    def _position(self, symbol: str):
        found = [p for p in (self.mt5.positions_get(symbol=symbol) or []) if p.magic == MAGIC]
        return found[0] if found else None

    def market_buy(self, symbol: str, qty: float) -> Fill:
        info = self._info(symbol)
        lots = self._lots(info, qty)
        tick = self._tick(symbol)
        result = self._send(
            {
                "action": self.mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lots,
                "type": self.mt5.ORDER_TYPE_BUY, "price": tick.ask, "deviation": 20,
                "magic": MAGIC, "comment": COMMENT, "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self._filling(info),
            }
        )  # fmt: skip
        price = result.price or tick.ask
        return Fill(symbol, "buy", result.volume * info.trade_contract_size, price, 0.0,
                    self.currency, str(result.order), self.now())  # fmt: skip

    def market_sell(self, symbol: str, qty: float) -> Fill:
        info = self._info(symbol)
        pos = self._position(symbol)
        if pos is None:
            raise BrokerError(f"No hay posición abierta del bot en {symbol}")
        lots = min(self._lots(info, qty), pos.volume)
        tick = self._tick(symbol)
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lots,
            "type": self.mt5.ORDER_TYPE_SELL, "price": tick.bid, "deviation": 20,
            "magic": MAGIC, "comment": COMMENT, "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self._filling(info),
        }  # fmt: skip
        if self.hedging:
            request["position"] = pos.ticket  # en hedging hay que indicar qué posición cerrar
        result = self._send(request)
        fee = self._deal_cost(result.deal)
        return Fill(symbol, "sell", result.volume * info.trade_contract_size, result.price or tick.bid,
                    fee, self.currency, str(result.order), self.now())  # fmt: skip

    def _deal_cost(self, deal_ticket: int) -> float:
        """Comisión + swap + cargos de una operación de cierre (positivo = costo)."""
        deals = self.mt5.history_deals_get(ticket=deal_ticket)
        if not deals:
            log.warning(
                "Sin historial para la operación %s: costo de cierre estimado en 0", deal_ticket
            )
            return 0.0
        d = deals[0]
        return float(-(d.commission + d.swap + getattr(d, "fee", 0.0)))

    def place_stop_loss(
        self, symbol: str, qty: float, stop_price: float, limit_price: float
    ) -> str:
        """Fija el SL de la posición en el servidor. Devuelve el ticket de la posición."""
        pos = self._position(symbol)
        if pos is None:
            raise BrokerError(f"No hay posición abierta del bot en {symbol} para protegerla")
        info = self._info(symbol)
        self._send(
            {
                "action": self.mt5.TRADE_ACTION_SLTP, "symbol": symbol, "position": pos.ticket,
                "sl": round(stop_price, info.digits), "tp": 0.0, "magic": MAGIC,
            }
        )  # fmt: skip
        return str(pos.ticket)

    def get_order(self, symbol: str, order_id: str) -> OrderInfo:
        """Estado del stop = estado de la posición: abierta (stop activo) o cerrada."""
        ticket = int(order_id)
        if self.mt5.positions_get(ticket=ticket):
            return OrderInfo(order_id, "open")
        deals = [
            d for d in (self.mt5.history_deals_get(position=ticket) or [])
            if d.entry == self.mt5.DEAL_ENTRY_OUT
        ]  # fmt: skip
        if not deals:
            return OrderInfo(order_id, "unknown")
        d = deals[-1]
        size = self._info(symbol).trade_contract_size
        if d.reason != getattr(self.mt5, "DEAL_REASON_SL", 4):
            log.warning("La posición %s se cerró por otro motivo (reason=%s)", ticket, d.reason)
        return OrderInfo(order_id, "filled", d.volume * size, d.price,
                         float(-(d.commission + d.swap + getattr(d, "fee", 0.0))), self.currency)  # fmt: skip

    def cancel_order(self, symbol: str, order_id: str) -> None:
        """No hace nada: el SL desaparece al cerrar la posición y así, si la venta falla,
        la posición sigue protegida."""
