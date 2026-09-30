import json

import pandas as pd
import pytest
from conftest import make_candles

from bot_eve.backtest.costs import SymbolRules
from bot_eve.common.config import Config, ExecutionConfig, RiskConfig, StrategyConfig
from bot_eve.engine.live import KillSwitch, LiveEngine, SlotSpec, build_slots
from bot_eve.engine.state import StateStore
from bot_eve.execution.base import BrokerError
from bot_eve.execution.memory import InMemoryBroker
from bot_eve.strategies.base import BUY, SELL, Strategy, empty_signals

RULES = SymbolRules(step_size=1e-4, min_qty=1e-4, min_notional=5.0)
T0 = pd.Timestamp("2024-01-01 00:00", tz="UTC")
STEP = pd.Timedelta(minutes=15)


class Scripted(Strategy):
    """Emite la señal indicada para una vela concreta (por su hora de apertura)."""

    name = "scripted"
    warmup = 1

    def __init__(self):
        self.plan: dict[pd.Timestamp, tuple[int, float | None, float | None]] = {}

    def generate(self, df):
        out = empty_signals(df.index)
        for ts, (sig, stop, target) in self.plan.items():
            if ts in out.index:
                out.loc[ts, "signal"] = sig
                out.loc[ts, "stop_pct"] = float("nan") if stop is None else stop
                out.loc[ts, "target_pct"] = float("nan") if target is None else target
        return out


class Env:
    """Motor + broker en memoria con el reloj bajo control."""

    def __init__(self, tmp_path, cash=1000.0, slots=1, **risk):
        self.cfg = Config(
            execution=ExecutionConfig(state_dir=tmp_path / "state", candle_delay_seconds=0),
            risk=RiskConfig(**risk),
        )
        self.broker = InMemoryBroker({"USDT": cash}, rules={"BTCUSDT": RULES, "ETHUSDT": RULES})
        for sym in ("BTCUSDT", "ETHUSDT"):
            self.broker.candles[(sym, "15m")] = make_candles("2024-01-01", 200, "15min")
            self.broker.prices[sym] = 100.0
        self.strategy = Scripted()
        self.store = StateStore(tmp_path / "state")
        specs = [SlotSpec("s|BTCUSDT|15m", "scripted", self.strategy, "BTCUSDT", "15m", 1.0)]
        if slots == 2:
            specs.append(
                SlotSpec("t|BTCUSDT|15m", "scripted2", self.strategy, "BTCUSDT", "15m", 1.0)
            )
        self.specs = specs
        self.engine = LiveEngine(self.cfg, self.broker, self.store, specs)

    def at(self, n_closed: int) -> None:
        """El reloj queda justo tras cerrar `n_closed` velas (la última tiene índice n-1)."""
        self.broker.set_time(T0 + STEP * n_closed)

    def candle(self, i: int) -> pd.Timestamp:
        return T0 + STEP * i

    def step(self, n_closed: int) -> None:
        self.at(n_closed)
        self.engine.step()

    @property
    def position(self):
        return self.engine.state.slots["s|BTCUSDT|15m"].position

    def trades(self):
        path = self.store.trades_path
        return [json.loads(line) for line in path.open()] if path.exists() else []


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def test_first_run_waits_for_the_next_candle(env):
    env.strategy.plan[env.candle(9)] = (BUY, 0.02, None)  # señal ya cerrada al arrancar
    env.step(10)
    assert env.position is None and env.broker.fills == []
    assert env.engine.state.slots["s|BTCUSDT|15m"].last_candle == env.candle(9).isoformat()


def test_buy_signal_opens_position_with_exchange_stop_and_risk_sizing(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, 0.05)
    env.step(11)
    pos = env.position
    # riesgo 1% de 1000 = 10 USDT; stop 2% a 100 -> 5 unidades; comisión 0.1% en BTC
    assert pos.qty == pytest.approx(5 * 0.999, abs=1e-4)
    assert pos.entry_price == 100.0 and pos.stop_price == pytest.approx(98.0)
    assert pos.target_price == pytest.approx(105.0)
    stop = env.broker.orders[pos.stop_order_id]
    assert stop["status"] == "open" and stop["qty"] == pos.qty
    assert env.broker.get_balance("BTC") == pytest.approx(0.0, abs=1e-4)  # bloqueado por el stop
    saved = json.loads(env.store.path.read_text())
    assert saved["slots"]["s|BTCUSDT|15m"]["position"]["stop_order_id"] == pos.stop_order_id


def test_position_without_strategy_stop_uses_emergency_stop(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, None, None)
    env.step(11)
    assert env.position.stop_price == pytest.approx(97.0)  # default_stop_pct 3%


def test_sell_signal_cancels_stop_and_closes_with_logged_pnl(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    stop_id = env.position.stop_order_id
    env.broker.prices["BTCUSDT"] = 110.0
    env.strategy.plan[env.candle(11)] = (SELL, None, None)
    env.step(12)
    assert env.position is None
    assert env.broker.orders[stop_id]["status"] == "canceled"
    (trade,) = env.trades()
    assert trade["reason"] == "signal" and trade["pnl"] > 40  # ~ +5 unidades * 10, menos costos
    assert env.broker.get_balance("BTC") == pytest.approx(0.0, abs=1e-4)
    assert env.broker.get_balance("USDT") > 1040


def test_stop_hit_on_exchange_is_detected_and_booked(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    env.broker.set_price("BTCUSDT", 97.0, low=96.0)  # el mercado cae y salta el stop
    env.step(11)  # mismo reloj: solo reconcilia
    assert env.position is None
    (trade,) = env.trades()
    assert trade["reason"] == "stop" and trade["pnl"] < 0
    assert trade["exit_price"] == pytest.approx(98.0 * 0.997)


def test_target_is_managed_by_the_bot(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, 0.05)
    env.step(11)
    stop_id = env.position.stop_order_id
    env.broker.set_price("BTCUSDT", 106.0)
    env.step(11)
    assert env.position is None and env.trades()[0]["reason"] == "target"
    assert env.broker.orders[stop_id]["status"] == "canceled"


def test_same_candle_is_not_processed_twice(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    n = len(env.broker.fills)
    env.step(11)
    env.engine.step()
    assert len(env.broker.fills) == n


def test_restart_keeps_position_and_does_not_buy_again(env, tmp_path):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    before = env.position
    engine2 = LiveEngine(env.cfg, env.broker, env.store, env.specs)  # "reinicio"
    assert engine2.state.slots["s|BTCUSDT|15m"].position == before
    env.at(11)
    engine2.step()
    assert len(env.broker.fills) == 1


def test_failed_stop_placement_closes_the_position_immediately(env, monkeypatch):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    monkeypatch.setattr(
        env.broker, "place_stop_loss", lambda *a, **k: (_ for _ in ()).throw(BrokerError("x"))
    )
    env.step(11)
    assert env.position is None  # nunca queda una posición sin protección
    assert [f.side for f in env.broker.fills] == ["buy", "sell"]
    assert env.trades()[0]["reason"] == "sin_stop"


def test_unprotected_position_is_recorded_and_stop_retried(env, monkeypatch):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    real_stop, real_sell = env.broker.place_stop_loss, env.broker.market_sell
    monkeypatch.setattr(
        env.broker, "place_stop_loss", lambda *a, **k: (_ for _ in ()).throw(BrokerError("x"))
    )
    monkeypatch.setattr(
        env.broker, "market_sell", lambda *a, **k: (_ for _ in ()).throw(BrokerError("y"))
    )
    env.step(11)
    assert env.position is not None and env.position.stop_order_id is None  # registrada, sin stop
    monkeypatch.setattr(env.broker, "place_stop_loss", real_stop)
    monkeypatch.setattr(env.broker, "market_sell", real_sell)
    env.step(11)  # el siguiente paso repone el stop
    assert env.position.stop_order_id is not None
    assert env.broker.orders[env.position.stop_order_id]["status"] == "open"


def test_lost_stop_order_is_replaced(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    old = env.position.stop_order_id
    env.broker.cancel_order("BTCUSDT", old)  # alguien lo canceló a mano
    env.step(11)
    assert env.position.stop_order_id not in (None, old)
    assert env.broker.orders[env.position.stop_order_id]["status"] == "open"


def test_daily_loss_limit_blocks_new_entries(env):
    env.step(10)
    env.engine.state.day_start_equity = 2000.0  # hoy ya se perdió la mitad
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    assert env.position is None and env.broker.fills == []


def test_stale_data_blocks_new_entries(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.broker.candles[("BTCUSDT", "15m")] = env.broker.candles[("BTCUSDT", "15m")].iloc[:11]
    env.step(150)  # el reloj avanzó muchísimo y las velas no
    assert env.position is None and env.broker.fills == []


def test_one_position_per_symbol_first_strategy_wins(tmp_path):
    e = Env(tmp_path, slots=2)
    e.step(10)
    e.strategy.plan[e.candle(10)] = (BUY, 0.02, None)
    e.step(11)
    opened = [k for k, s in e.engine.state.slots.items() if s.position]
    assert opened == ["s|BTCUSDT|15m"] and len(e.broker.fills) == 1


def test_tiny_capital_below_min_notional_does_not_trade(tmp_path):
    e = Env(tmp_path, cash=3.54)
    e.step(10)
    e.strategy.plan[e.candle(10)] = (BUY, 0.02, None)
    e.step(11)
    assert e.position is None and e.broker.fills == []


def test_kill_file_flattens_everything_and_stops(env):
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    stop_id = env.position.stop_order_id
    env.store.dir.mkdir(exist_ok=True)
    env.store.kill_path.write_text("kill")
    with pytest.raises(KillSwitch):
        env.step(12)
    assert env.position is None and env.broker.orders[stop_id]["status"] == "canceled"
    assert env.trades()[-1]["reason"] == "kill"


def test_consecutive_errors_trigger_kill_switch_and_reset_on_success(tmp_path):
    e = Env(tmp_path, max_consecutive_errors=3)
    e.step(10)
    for _ in range(2):
        e.broker.fail_with = BrokerError("red caída")
        e.step(11)
    assert e.engine.state.consecutive_errors == 2
    e.step(11)  # una pasada correcta reinicia el contador
    assert e.engine.state.consecutive_errors == 0
    with pytest.raises(KillSwitch):
        for _ in range(3):
            e.broker.fail_with = BrokerError("red caída")
            e.step(11)


def test_kill_switch_on_errors_attempts_to_close_open_positions(tmp_path):
    e = Env(tmp_path, max_consecutive_errors=2)
    e.step(10)
    e.strategy.plan[e.candle(10)] = (BUY, 0.02, None)
    e.step(11)
    with pytest.raises(KillSwitch):
        for _ in range(2):
            e.broker.fail_with = BrokerError("caída")
            e.step(11)
    assert e.position is None  # tras recuperar la conexión, se cerró


def test_build_slots_splits_capital_and_requires_allocation():
    cfg = Config(
        strategies={
            "sma_cross": StrategyConfig(enabled=True, stage="demo", capital_fraction=0.6,
                                        intervals=["15m", "1h"], symbols=["BTCUSDT", "ETHUSDT"]),
            "rsi_trend": StrategyConfig(enabled=False, stage="demo", capital_fraction=0.3),
        }
    )  # fmt: skip
    slots = build_slots(cfg)
    assert len(slots) == 4 and all(s.capital_fraction == pytest.approx(0.15) for s in slots)
    assert {s.strategy_name for s in slots} == {"sma_cross"}
    bad = Config(strategies={"sma_cross": StrategyConfig(enabled=True, stage="demo")})
    with pytest.raises(ValueError, match="capital_fraction"):
        build_slots(bad)


def test_backtest_stage_strategies_never_become_slots():
    cfg = Config(
        strategies={
            "sma_cross": StrategyConfig(enabled=True, stage="backtest", capital_fraction=1.0)
        }
    )
    assert build_slots(cfg) == []


def test_stop_covers_what_was_really_received_even_if_the_fee_is_not_reported(env):
    """Si la respuesta de la compra no informa la comisión (cobrada en el activo base), el stop
    debe colocarse por el saldo real; con la cantidad pedida el exchange lo rechazaría."""
    from dataclasses import replace

    real_buy = env.broker.market_buy
    env.broker.market_buy = lambda symbol, qty: replace(
        real_buy(symbol, qty), fee=0.0
    )  # sin comisión
    env.step(10)
    env.strategy.plan[env.candle(10)] = (BUY, 0.02, None)
    env.step(11)
    assert env.position is not None, "la posición no debe cerrarse por un stop rechazado"
    stop = env.broker.orders[env.position.stop_order_id]
    assert (
        stop["status"] == "open" and stop["qty"] <= 5.0 * 0.999 + 1e-9
    )  # lo recibido, no lo pedido
    assert env.position.qty == stop["qty"]
