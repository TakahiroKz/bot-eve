"""El motor en vivo operando a través del conector de MT5 (CFD, SL en el servidor)."""

import json

import pandas as pd
import pytest
from fake_mt5 import FakeTradingMt5, make_rates

from bot_eve.common.config import Config, ExecutionConfig, RiskConfig
from bot_eve.engine.live import LiveEngine, SlotSpec
from bot_eve.engine.state import StateStore
from bot_eve.execution.mt5 import Mt5Broker
from bot_eve.strategies.base import BUY, SELL, Strategy, empty_signals

T0 = pd.Timestamp("2024-01-01 00:00", tz="UTC")
STEP = pd.Timedelta(hours=4)


class Scripted(Strategy):
    name, warmup = "scripted", 1

    def __init__(self):
        self.plan = {}

    def generate(self, df):
        out = empty_signals(df.index)
        for ts, (sig, stop) in self.plan.items():
            if ts in out.index:
                out.loc[ts, ["signal", "stop_pct"]] = [sig, stop]
        return out


class Env:
    def __init__(self, tmp_path):
        self.fake = FakeTradingMt5()
        self.broker = Mt5Broker("BTCUSD", mt5=self.fake)
        self.cfg = Config(
            execution=ExecutionConfig(broker="mt5", quote_asset="USD", state_dir=tmp_path / "s",
                                      candle_delay_seconds=0),
            risk=RiskConfig(),
        )  # fmt: skip
        self.strategy, self.store = Scripted(), StateStore(tmp_path / "s")
        spec = SlotSpec("s|BTCUSD|4h", "scripted", self.strategy, "BTCUSD", "4h", 1.0)
        self.engine = LiveEngine(self.cfg, self.broker, self.store, [spec])
        self.all_rates = make_rates(60, 4 * 3600, end=(T0 + 59 * STEP).isoformat())
        self.all_rates["time"] = [int((T0 + i * STEP).timestamp()) for i in range(60)]

    def step(self, n_closed):
        """Quedan cerradas las velas 0..n_closed-1 (la hora del broker es controlada)."""
        self.fake.rates = self.all_rates[:n_closed]
        self.broker.now = lambda: T0 + n_closed * STEP
        self.engine.step()

    @property
    def position(self):
        return self.engine.state.slots["s|BTCUSD|4h"].position

    def trades(self):
        p = self.store.trades_path
        return [json.loads(x) for x in p.open()] if p.exists() else []


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def test_buy_signal_opens_cfd_position_sized_by_risk_with_server_side_stop(env):
    env.step(10)
    env.strategy.plan[T0 + 10 * STEP] = (BUY, 0.04)
    env.step(11)
    pos = env.position
    # riesgo 1% de 50.000 = 500; stop 4% sobre 84.030 -> 0.148 BTC -> 0.14 lotes
    assert pos.qty == pytest.approx(0.14)
    (mt5_pos,) = env.fake.positions.values()
    assert mt5_pos.sl == pytest.approx(84030.0 * 0.96, abs=0.01) and pos.stop_order_id == str(
        mt5_pos.ticket
    )
    assert env.engine.equity() == pytest.approx(50000.0 + (env.fake.bid - 84030.0) * 0.14)


def test_stop_hit_on_the_server_is_booked_as_a_loss(env):
    env.step(10)
    env.strategy.plan[T0 + 10 * STEP] = (BUY, 0.04)
    env.step(11)
    env.fake.trigger_stops(low=80000.0)
    env.step(11)
    assert env.position is None and not env.fake.positions
    (trade,) = env.trades()
    assert trade["reason"] == "stop" and trade["pnl"] < 0
    assert trade["exit_price"] == pytest.approx(84030.0 * 0.96, abs=0.01)


def test_sell_signal_closes_position_and_books_costs(env):
    env.step(10)
    env.strategy.plan[T0 + 10 * STEP] = (BUY, 0.04)
    env.step(11)
    env.fake.bid, env.fake.ask = 88000.0, 88030.0
    env.strategy.plan[T0 + 11 * STEP] = (SELL, None)
    env.step(12)
    assert env.position is None and not env.fake.positions
    (trade,) = env.trades()
    assert trade["reason"] == "signal" and trade["pnl"] > 400  # ~ (88000-84030)*0.14 - costos


def test_if_the_server_rejects_the_stop_the_position_is_closed_immediately(env):
    env.step(10)
    env.fake.symbols["BTCUSD"].trade_stops_level = 10**9  # distancia mínima imposible
    env.strategy.plan[T0 + 10 * STEP] = (BUY, 0.04)
    env.step(11)
    assert env.position is None and not env.fake.positions  # nunca queda sin protección
    assert env.trades()[0]["reason"] == "sin_stop"


def test_minimum_lot_blocks_entries_when_capital_is_too_small(tmp_path):
    e = Env(tmp_path)
    e.fake.balance = 1000.0  # 0.01 BTC ≈ 840 USD supera el riesgo permitido
    e.step(10)
    e.strategy.plan[T0 + 10 * STEP] = (BUY, 0.04)
    e.step(11)
    assert e.position is None and not e.fake.positions
