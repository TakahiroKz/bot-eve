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
from bot_eve.execution.base import Broker, BrokerConnectionError, BrokerError, fee_in_quote
from bot_eve.notify import Notifier, NullNotifier
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
    max_positions: int | None = None  # tope de posiciones simultáneas de la estrategia


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
    if sc.position_cap is not None:  # tope por posición validado; el máximo lo aplica el motor
        share = sc.position_cap
    else:
        share = sc.capital_fraction / (len(symbols) * len(sc.intervals))  # sin sobreasignar
    return [
        SlotSpec(slot_key(name, sym, itv), name, strategy, sym, itv, share, sc.max_positions)
        for sym in symbols
        for itv in sc.intervals
    ]


class LiveEngine:
    def __init__(
        self,
        cfg: Config,
        broker: Broker,
        store: StateStore,
        slots: list[SlotSpec],
        notifier: Notifier | None = None,
        label: str = "",
    ):
        self.cfg, self.broker, self.store, self.slots = cfg, broker, store, slots
        self.notifier = notifier or NullNotifier()
        self.label = label or f"{broker.name} {cfg.execution.mode}"
        self._limit_alert_day = ""
        self._outage_since: pd.Timestamp | None = None  # inicio de la caída de conexión en curso
        self._outage_alerted = False
        self._last_equity: float | None = None
        self.risk = RiskManager(cfg.risk, store.kill_path)
        self.quote = cfg.execution.quote_asset
        self.state: State = store.load()
        for spec in slots:
            self.state.slots.setdefault(spec.key, Slot())

    # --- alertas y estado (nunca deben romper el trading) ----------------------------------------
    def _say(self, text: str, critical: bool = False) -> None:
        try:
            self.notifier.send(text, critical=critical)
        except Exception as exc:  # noqa: BLE001
            log.warning("Fallo al enviar una alerta (%s)", type(exc).__name__)

    def _after_step(self, equity: float, now: pd.Timestamp) -> None:
        for action in (
            lambda: self._daily_summary(equity, now),
            lambda: self._write_status(equity, now),
        ):
            try:
                action()
            except Exception as exc:  # noqa: BLE001 - el estado/resumen no deben detener el bot
                log.warning(
                    "Fallo al actualizar el estado/resumen (%s: %s)", type(exc).__name__, exc
                )

    def _write_status(self, equity: float, now: pd.Timestamp) -> None:
        positions = []
        for spec in self.slots:
            pos = self.state.slots[spec.key].position
            if not pos:
                continue
            try:
                price = self.broker.get_price(spec.symbol)
            except BrokerError:
                price = pos.entry_price
            pnl = (price - pos.entry_price) * pos.qty
            positions.append(
                {
                    "key": spec.key, "strategy": spec.strategy_name, "symbol": spec.symbol,
                    "qty": pos.qty, "entry_price": pos.entry_price, "entry_time": pos.entry_time,
                    "price": price, "unrealized_pnl": pnl,
                    "unrealized_pct": price / pos.entry_price - 1,
                    "stop_price": pos.stop_price, "target_price": pos.target_price,
                    "protected": pos.stop_order_id is not None,
                }
            )  # fmt: skip
        start = self.state.day_start_equity
        self.store.save_status(
            {
                "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                "broker_time": now.isoformat(),
                "label": self.label,
                "broker": self.broker.name,
                "mode": self.cfg.execution.mode,
                "real_money": bool(self.broker.is_real_money),
                "equity": equity,
                "day_start_equity": start,
                "day_pnl_pct": (equity / start - 1) if start > 0 else 0.0,
                "consecutive_errors": self.state.consecutive_errors,
                "kill_active": self.risk.kill_requested(),
                "poll_seconds": self.cfg.execution.poll_seconds,
                "positions": positions,
                "slots": [
                    {"key": k, "last_candle": sl.last_candle} for k, sl in self.state.slots.items()
                ],
            }
        )  # fmt: skip

    def _daily_summary(self, equity: float, now: pd.Timestamp) -> None:
        hour = self.cfg.notify.telegram.daily_summary_hour
        day = now.strftime("%Y-%m-%d")
        if now.hour < hour or self.state.last_summary_day == day:
            return
        self.state.last_summary_day = day
        start = self.state.day_start_equity
        opened = sum(1 for sl in self.state.slots.values() if sl.position)
        change = (equity / start - 1) if start > 0 else 0.0
        self._say(
            f"📊 Resumen diario\nCapital: {equity:,.2f} ({change:+.2%} hoy)\n"
            f"Posiciones abiertas: {opened} · errores seguidos: {self.state.consecutive_errors}"
        )

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
            self._say(
                "🚨 KILL SWITCH: archivo KILL detectado; posiciones cerradas y bot detenido", True
            )
            raise KillSwitch("archivo KILL detectado")
        now = self.broker.now()
        try:
            equity = self.equity()
            self._last_equity = equity
            self._roll_day(equity, now)
            for spec in self.slots:
                self._process(spec, equity, now)
            self.state.consecutive_errors = 0
            if self._outage_since is not None:
                self._say("✅ Conexión con el broker restablecida.")
                self._outage_since, self._outage_alerted = None, False
            self._after_step(equity, now)
        except BrokerConnectionError as exc:
            self._on_outage(exc, now)
        except BrokerError as exc:
            self.state.consecutive_errors += 1
            log.error("Error de broker (%d seguidos): %s", self.state.consecutive_errors, exc)
            if self._last_equity is not None:  # que el dashboard vea el contador de errores
                try:
                    self._write_status(self._last_equity, now)
                except Exception:  # noqa: BLE001
                    pass
            if self.state.consecutive_errors == 1:
                self._say(
                    f"⚠️ Error de conexión con el broker: {type(exc).__name__}. Se reintentará."
                )
            if self.state.consecutive_errors >= self.cfg.risk.max_consecutive_errors:
                self.store.save(self.state)
                self.flatten_all("errores")
                self._say("🚨 KILL SWITCH: demasiados errores seguidos; bot detenido", True)
                raise KillSwitch("demasiados errores seguidos") from exc
        finally:
            self.store.save(self.state)

    def _on_outage(self, exc: Exception, now: pd.Timestamp) -> None:
        """Caída de conexión: se reintenta sin cerrar nada (los stops viven en el exchange).
        No cuenta para el kill switch; se avisa al inicio y de nuevo si dura más de 30 minutos."""
        if self._outage_since is None:
            self._outage_since = now
            log.warning("Sin conexión con el broker (se reintenta): %s", exc)
            self._say(
                f"⚠️ Sin conexión con el broker: {type(exc).__name__}. Los stops siguen en el exchange; se reintenta."
            )
        elif not self._outage_alerted and now - self._outage_since > pd.Timedelta(minutes=30):
            self._outage_alerted = True
            log.error("Sin conexión con el broker desde hace más de 30 minutos")
            self._say(
                "🔴 Más de 30 min sin conexión con el broker. Revisa internet/PC; los stops siguen en el exchange.",
                True,
            )

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
        if spec.max_positions is not None:
            open_n = sum(
                1
                for other in self.slots
                if other.strategy_name == spec.strategy_name
                and self.state.slots[other.key].position
            )
            if open_n >= spec.max_positions:
                log.info("%s: máximo de %d posiciones, se omite", spec.key, spec.max_positions)
                return
        decision = self.risk.can_open(equity, self.state.day_start_equity)
        if not decision.ok:
            log.warning("%s: no se abre posición: %s", spec.key, decision.reason)
            if self._limit_alert_day != self.state.day:  # una alerta por día
                self._limit_alert_day = self.state.day
                self._say(f"⛔ No se abren posiciones: {decision.reason}")
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
        self._say(
            f"🟢 COMPRA {spec.symbol} {net:g} @ {fill.price:,.2f}\n"
            f"Stop {stop:,.2f} (−{stop_pct:.1%}) · {spec.strategy_name} {spec.interval}"
        )
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
        icon = "🛑" if reason == "stop" else ("✅" if pnl >= 0 else "🔴")
        self._say(
            f"{icon} CIERRE {spec.symbol} ({reason}) @ {price:,.2f}\n"
            f"P&L {pnl:+,.2f} ({pnl / cost:+.2%}) · {spec.strategy_name}"
        )
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
            self._say("⏹ Bot detenido por el usuario. Los stops del exchange siguen activos.")
        except KillSwitch as exc:
            log.error("KILL SWITCH: %s", exc)
