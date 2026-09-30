"""Simulacro: reproduce velas históricas REALES a través del motor en vivo (broker en memoria).

Se omite si no hay datos descargados (`python -m bot_eve.data sync`).
"""

from pathlib import Path

import pandas as pd
import pytest

from bot_eve.backtest.costs import rules_for
from bot_eve.common.config import Config, ExecutionConfig, RiskConfig
from bot_eve.data.store import CandleStore
from bot_eve.engine.live import LiveEngine, SlotSpec
from bot_eve.engine.state import StateStore
from bot_eve.execution.memory import InMemoryBroker
from bot_eve.strategies.sma_cross import SmaCross

DATA = Path(__file__).resolve().parents[1] / "data_store"
pytestmark = pytest.mark.skipif(not (DATA / "BTCUSDT" / "1h").exists(), reason="sin datos locales")


def replay(tmp_path, strategy, candles: pd.DataFrame, interval="1h"):
    cfg = Config(
        execution=ExecutionConfig(state_dir=tmp_path, candle_delay_seconds=0),
        risk=RiskConfig(risk_per_trade=0.05, default_stop_pct=0.05),
    )
    broker = InMemoryBroker({"USDT": 1000.0}, rules={"BTCUSDT": rules_for("BTCUSDT")})
    broker.candles[("BTCUSDT", interval)] = candles
    store = StateStore(tmp_path)
    spec = SlotSpec("s|BTCUSDT|" + interval, "sma_cross", strategy, "BTCUSDT", interval, 1.0)
    engine = LiveEngine(cfg, broker, store, [spec])
    step = pd.Timedelta(hours=1)
    for ts, row in candles.iterrows():
        broker.set_price("BTCUSDT", float(row["close"]), low=float(row["low"]))  # dispara stops
        broker.set_time(ts + step)
        engine.step()
        pos = engine.state.slots[spec.key].position
        if pos:  # invariante: nunca hay posición abierta sin stop activo en el exchange
            assert pos.stop_order_id and broker.orders[pos.stop_order_id]["status"] == "open"
    return engine, broker, store


def test_replay_real_btc_hourly_data_keeps_all_invariants(tmp_path):
    df = CandleStore(DATA).read("BTCUSDT", "1h", start="2023-01-01", end="2023-06-30")
    engine, broker, store = replay(tmp_path, SmaCross(10, 30), df)
    lines = store.trades_path.read_text().strip().splitlines() if store.trades_path.exists() else []
    assert len(lines) >= 5, "la estrategia debería operar varias veces en 6 meses"
    # contabilidad: el capital final coincide con saldo + posición abierta a precio de mercado
    equity = engine.equity()
    assert equity == pytest.approx(
        broker.get_balance("USDT")
        + sum(
            s.position.qty * broker.prices["BTCUSDT"]
            for s in engine.state.slots.values()
            if s.position
        )
    )
    assert 300 < equity < 3000  # sin explosiones numéricas
