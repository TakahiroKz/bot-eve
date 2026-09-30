"""Motor en vivo: convierte señales de velas cerradas en órdenes, con protección en el exchange.

Semántica idéntica al backtest: la señal sale de la vela **cerrada** y se ejecuta de
inmediato (≈ apertura de la siguiente). Reglas de seguridad:

- Toda posición se abre con un stop en el exchange; si no se puede colocar, se cierra al instante.
- Al arrancar por primera vez una combinación, NO se opera con la vela ya cerrada: se espera a
  la siguiente (evita entrar con señales viejas tras un reinicio sin estado).
- Datos obsoletos -> no se abren posiciones nuevas (los stops existentes siguen protegiendo).
- Errores seguidos por encima del límite, o el archivo KILL, cierran todo y detienen el bot.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pandas as pd

from bot_eve.common.config import Config, StrategyConfig
from bot_eve.data.intervals import to_timedelta
from bot_eve.engine.state import Position, Slot, State, StateStore, slot_key
from bot_eve.execution.base import Broker, BrokerError, fee_in_quote
from bot_eve.risk.manager import RiskManager
from bot_eve.strategies import build_strategy
from bot_eve.strategies.base import BUY, SELL, Strategy

log = logging.getLogger(__name__)


class KillSwitch(Exception):
    """Se cerraron las posiciones y el bot debe detenerse."""


@dataclass
class SlotSpec:
    key: str
    strategy_name: str
    strategy: Strategy
    symbol: str
    interval: str
    capital_fraction: float


def build_slots(cfg: Config) -> list[SlotSpec]:
    slots = []
    for name, sc in cfg.active_strategies(cfg.execution.mode).items():
        if sc.capital_fraction <= 0:
            raise ValueError(
                f"{name}: asigna capital_fraction > 0 para operar en {cfg.execution.mode}"
            )
        slots += _slots_for(cfg, name, sc)
    return slots


def _slots_for(cfg: Config, name: str, sc: StrategyConfig) -> list[SlotSpec]:
    strategy = build_strategy(name, **sc.params)
    symbols = sc.symbols or cfg.data.symbols
    share = sc.capital_fraction / (len(symbols) * len(sc.intervals))  # sin sobreasignar
    return [
        SlotSpec(slot_key(name, sym, itv), name, strategy, sym, itv, share)
        for sym in symbols
        for itv in sc.intervals
    ]


class LiveEngine:
    def __init__(self, cfg: Config, broker: Broker, store: StateStore, slots: list[SlotSpec]):
        self.cfg, self.broker, self.store, self.slots = cfg, broker, store, slots
        self.risk = RiskManager(cfg.risk, store.kill_path)
        self.quote = cfg.execution.quote_asset
        self.state: State = store.load()
        for spec in slots:
            self.state.slots.setdefault(spec.key, Slot())

    # --- equity y día ---------------------------------------------------------------------
    def equity(self) -> float:
        held = [
            (spec.symbol, self.state.slots[spec.key].position.qty)
            for spec in self.slots
            if self.state.slots[spec.key].position
        ]
        return self.broker.equity(self.quote, held)

    def _roll_day(self, equity: float, now: pd.Timestamp) -> None:
        day = now.strftime("%Y-%m-%d")
        if self.state.day != day:
            self.state.day, self.state.day_start_equity = day, equity

    # --- paso principal ------------------------------------------------------------------
    def step(self) -> None:
        """Una pasada por todas las combinaciones. Lanza KillSwitch si hay que detenerse."""
        if self.risk.kill_requested():
            self.flatten_all("kill")
            raise KillSwitch("archivo KILL detectado")
        now = self.broker.now()
        try:
            equity = self.equity()
            self._roll_day(equity, now)
            for spec in self.slots:
                self._process(spec, equity, now)
            self.state.consecutive_errors = 0
        except BrokerError as exc:
            self.state.consecutive_errors += 1
            log.error("Error de broker (%d seguidos): %s", self.state.consecutive_errors, exc)
            if self.state.consecutive_errors >= self.cfg.risk.max_consecutive_errors:
                self.store.save(self.state)
                self.flatten_all("errores")
                raise KillSwitch("demasiados errores seguidos") from exc
        finally:
            self.store.save(self.state)

    def _process(self, spec: SlotSpec, equity: float, now: pd.Timestamp) -> None:
        slot = self.state.slots[spec.key]
        step = to_timedelta(spec.interval)
        if slot.position:
            self._manage_position(spec, slot)
        delay = pd.Timedelta(seconds=self.cfg.execution.candle_delay_seconds)
        if slot.last_candle and now < pd.Timestamp(slot.last_candle) + 2 * step + delay:
            return  # todavía no puede haber cerrado una vela nueva
        candles = self.broker.get_candles(
            spec.symbol, spec.interval, self.cfg.execution.candles_lookback
        )
        if candles.empty:
            return
        last = candles.index[-1]
        if slot.last_candle and last <= pd.Timestamp(slot.last_candle):
            return
        first_time = slot.last_candle is None
        slot.last_candle = last.isoformat()
        if first_time:
            log.info("%s: primera ejecución, se espera a la siguiente vela", spec.key)
            return
        if self.risk.is_stale(last, spec.interval, now):
            log.warning("%s: datos obsoletos (última vela %s), sin operar", spec.key, last)
            return
        if len(candles) < spec.strategy.warmup:
            log.warning("%s: pocas velas (%d < %d)", spec.key, len(candles), spec.strategy.warmup)
            return
        row = spec.strategy.generate(candles).iloc[-1]
        if slot.position and row["signal"] == SELL:
            self._exit(spec, slot, "signal")
        elif not slot.position and row["signal"] == BUY:
            self._enter(spec, slot, equity, row)

    # --- entradas y salidas ------------------------------------------------------------------
    def _enter(self, spec: SlotSpec, slot: Slot, equity: float, row: pd.Series) -> None:
        for other in self.slots:
            if other.symbol == spec.symbol and self.state.slots[other.key].position:
                log.info(
                    "%s: %s ya tiene posición en %s, se omite", spec.key, other.key, spec.symbol
                )
                return
        decision = self.risk.can_open(equity, self.state.day_start_equity)
        if not decision.ok:
            log.warning("%s: no se abre posición: %s", spec.key, decision.reason)
            return
        rules = self.broker.get_symbol_rules(spec.symbol)
        price = self.broker.get_price(spec.symbol)
        stop_pct = self.risk.stop_pct_for(row["stop_pct"])
        qty = self.risk.position_size(
            equity, price, stop_pct, spec.capital_fraction, rules,
            self.broker.buying_power(self.quote),
        )  # fmt: skip
        if qty <= 0:
            log.warning("%s: tamaño 0 (mínimos del par o saldo), no se opera", spec.key)
            return
        fill = self.broker.market_buy(spec.symbol, qty)
        # Se protege lo que REALMENTE hay disponible: si la comisión no viene informada en la
        # respuesta de la orden, `fill.net_qty` sería mayor que lo recibido y el stop se rechazaría.
        held = self.broker.get_balance(spec.symbol[: -len(self.quote)])
        net = rules.round_qty(min(fill.net_qty, held) if held > 0 else fill.net_qty)
        stop, limit = self.risk.stop_prices(fill.price, stop_pct)
        target_pct = row["target_pct"]
        target = fill.price * (1 + target_pct) if target_pct == target_pct else None
        # La posición se registra ANTES de colocar el stop: si algo falla, queda constancia.
        slot.position = Position(
            net, fill.price, fill.time.isoformat(), fee_in_quote(fill), None, stop, target
        )
        log.info("%s: COMPRA %.8f @ %.2f, stop %.2f", spec.key, net, fill.price, stop)
        self.store.save(self.state)
        self._ensure_stop(spec, slot, limit)

    def _ensure_stop(self, spec: SlotSpec, slot: Slot, limit: float | None = None) -> None:
        """Coloca el stop en el exchange. Si no se puede, cierra la posición; y si tampoco
        se puede cerrar, la deja registrada sin stop y se reintenta en cada paso."""
        pos = slot.position
        limit = limit or pos.stop_price * (1 - self.cfg.risk.stop_limit_buffer)
        try:
            pos.stop_order_id = self.broker.place_stop_loss(
                spec.symbol, pos.qty, pos.stop_price, limit
            )
            return
        except BrokerError as exc:
            log.error("%s: no se pudo colocar el stop (%s); se cierra la posición", spec.key, exc)
        try:
            self._exit(spec, slot, "sin_stop")
        except BrokerError as exc:
            log.critical(
                "%s: POSICIÓN SIN STOP y no se pudo cerrar (%s). Se reintentará.", spec.key, exc
            )

    def _exit(self, spec: SlotSpec, slot: Slot, reason: str) -> None:
        pos = slot.position
        if pos.stop_order_id:
            self.broker.cancel_order(spec.symbol, pos.stop_order_id)
            pos.stop_order_id = None  # si la venta falla, el siguiente paso repone el stop
        rules = self.broker.get_symbol_rules(spec.symbol)
        base = spec.symbol[: -len(self.quote)]
        qty = rules.round_qty(min(pos.qty, self.broker.get_balance(base)))
        fill = self.broker.market_sell(spec.symbol, qty)
        self._close(spec, slot, fill.price, fill.qty, fee_in_quote(fill), reason)

    def _close(
        self, spec: SlotSpec, slot: Slot, price: float, qty: float, fee_q: float, reason: str
    ) -> None:
        pos = slot.position
        cost = pos.entry_price * pos.qty + pos.entry_fee_quote
        pnl = price * qty - fee_q - cost
        self.store.log_trade(
            {
                "strategy": spec.strategy_name, "symbol": spec.symbol, "interval": spec.interval,
                "entry_time": pos.entry_time, "exit_time": self.broker.now().isoformat(),
                "entry_price": pos.entry_price, "exit_price": price, "qty": qty,
                "pnl": round(pnl, 8), "return_pct": pnl / cost, "reason": reason,
            }
        )  # fmt: skip
        log.info("%s: CIERRE (%s) @ %.2f pnl %.4f", spec.key, reason, price, pnl)
        slot.position = None

    def _manage_position(self, spec: SlotSpec, slot: Slot) -> None:
        """Reconcilia con el exchange: ¿saltó el stop? ¿se alcanzó el objetivo?"""
        pos = slot.position
        if pos.stop_order_id is None:  # quedó sin stop (fallo anterior): reintentar
            self._ensure_stop(spec, slot)
            if slot.position is None or pos.stop_order_id is None:
                return
        if pos.stop_order_id:
            info = self.broker.get_order(spec.symbol, pos.stop_order_id)
            if info.status == "filled":
                fee_q = info.fee if info.fee_asset == self.quote else 0.0
                self._close(spec, slot, info.avg_price, info.filled_qty, fee_q, "stop")
                return
            if info.status in ("canceled", "unknown"):
                log.error(
                    "%s: el stop %s ya no existe; se vuelve a colocar",
                    spec.key,
                    pos.stop_order_id,
                )
                pos.stop_order_id = None
                self._ensure_stop(spec, slot)
                return
        if pos.target_price and self.broker.get_price(spec.symbol) >= pos.target_price:
            self._exit(spec, slot, "target")

    def flatten_all(self, reason: str) -> None:
        for spec in self.slots:
            slot = self.state.slots[spec.key]
            if slot.position:
                try:
                    self._exit(spec, slot, reason)
                except BrokerError as exc:
                    log.error(
                        "%s: no se pudo cerrar (%s). El stop en el exchange sigue activo.",
                        spec.key,
                        exc,
                    )
        self.store.save(self.state)

    # --- bucle ------------------------------------------------------------------------------
    def run_forever(self) -> None:
        log.info(
            "Motor iniciado: modo %s, %d combinaciones", self.cfg.execution.mode, len(self.slots)
        )
        try:
            while True:
                self.step()
                time.sleep(self.cfg.execution.poll_seconds)
        except KeyboardInterrupt:
            log.info("Detenido por el usuario. Los stops del exchange siguen activos.")
        except KillSwitch as exc:
            log.error("KILL SWITCH: %s", exc)
