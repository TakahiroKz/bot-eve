import numpy as np
import pandas as pd
import pytest

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import run_backtest
from bot_eve.strategies.base import BUY, HOLD, SELL, Strategy, empty_signals

ZERO = Costs(fee_rate=0.0, slippage=0.0)
LOOSE = SymbolRules(step_size=1e-6, min_qty=1e-6, min_notional=0.0)


class Scripted(Strategy):
    """Emite señales fijas por posición de vela: {i: (signal, stop_pct, target_pct)}."""

    name = "scripted"

    def __init__(self, script):
        self.script = script

    def generate(self, df):
        out = empty_signals(df.index)
        for i, (sig, stop, target) in self.script.items():
            if i < len(df):
                out.iloc[i, 0] = sig
                out.iloc[i, 1] = np.nan if stop is None else stop
                out.iloc[i, 2] = np.nan if target is None else target
        return out


def candles(rows, freq="15min"):
    """rows: lista de (open, high, low, close)."""
    idx = pd.date_range("2024-01-01", periods=len(rows), freq=freq, tz="UTC", name="open_time")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1.0
    return df


def flat(price, n):
    return [(price, price, price, price)] * n


def run(df, script, costs=ZERO, rules=LOOSE, cash=1000.0, **kw):
    return run_backtest(df, Scripted(script), costs, rules, cash, **kw)


def test_signal_executes_at_next_open_not_at_signal_close():
    # cierre de la vela 1 = 100; la apertura de la vela 2 = 105 -> se compra a 105
    rows = [(100, 100, 100, 100), (100, 100, 100, 100), (105, 105, 105, 105)] + flat(120, 3)
    res = run(candles(rows), {1: (BUY, None, None), 4: (SELL, None, None)})
    t = res.trades.iloc[0]
    assert t["entry_price"] == 105
    assert t["exit_price"] == 120  # SELL en vela 4 -> apertura de vela 5
    assert t["exit_reason"] == "signal"


def test_zero_cost_pnl_and_equity_identity():
    rows = flat(100, 3) + flat(110, 3)
    res = run(candles(rows), {0: (BUY, None, None), 3: (SELL, None, None)})
    t = res.trades.iloc[0]
    assert t["qty"] == pytest.approx(10.0)
    assert t["pnl"] == pytest.approx(100.0)
    assert res.equity.iloc[-1] == pytest.approx(1100.0)
    assert res.equity.iloc[-1] == pytest.approx(1000.0 + res.trades["pnl"].sum())


def test_fees_and_slippage_are_charged_on_both_sides():
    costs = Costs(fee_rate=0.001, slippage=0.001)
    rows = flat(100, 4)
    res = run(candles(rows), {0: (BUY, None, None), 2: (SELL, None, None)}, costs=costs)
    t = res.trades.iloc[0]
    assert t["entry_price"] == pytest.approx(100.1)
    assert t["exit_price"] == pytest.approx(99.9)
    assert t["pnl"] < 0  # precio plano: solo se pierde en costos
    assert t["fees"] == pytest.approx(t["qty"] * (100.1 + 99.9) * 0.001, rel=1e-6)
    assert res.equity.iloc[-1] == pytest.approx(1000.0 + t["pnl"])
    # ida y vuelta cuesta ~ 2*(0.1% + 0.1%) = 0.4% del capital
    assert res.metrics["total_return"] == pytest.approx(-0.004, abs=2e-4)


def test_stop_loss_fills_at_stop_price():
    rows = flat(100, 2) + [(99, 100, 94, 96)] + flat(96, 2)
    res = run(candles(rows), {0: (BUY, 0.05, None)})
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop" and t["exit_price"] == pytest.approx(95.0)


def test_stop_gap_fills_at_worse_open():
    rows = flat(100, 2) + [(90, 92, 88, 91)] + flat(91, 2)
    res = run(candles(rows), {0: (BUY, 0.05, None)})
    assert res.trades.iloc[0]["exit_price"] == pytest.approx(90.0)


def test_target_fills_at_target_price():
    rows = flat(100, 2) + [(101, 112, 100, 111)] + flat(111, 2)
    res = run(candles(rows), {0: (BUY, 0.05, 0.10)})
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "target" and t["exit_price"] == pytest.approx(110.0)


def test_stop_wins_when_stop_and_target_hit_same_candle():
    rows = flat(100, 2) + [(100, 115, 90, 100)] + flat(100, 2)
    res = run(candles(rows), {0: (BUY, 0.05, 0.10)})
    assert res.trades.iloc[0]["exit_reason"] == "stop"


def test_stop_can_trigger_on_entry_candle():
    rows = flat(100, 1) + [(100, 101, 90, 95)] + flat(95, 2)
    res = run(candles(rows), {0: (BUY, 0.05, None)})
    t = res.trades.iloc[0]
    assert t["entry_time"] == t["exit_time"] and t["exit_reason"] == "stop"


def test_open_position_is_closed_at_last_close():
    rows = flat(100, 3) + flat(120, 2)
    res = run(candles(rows), {0: (BUY, None, None)})
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "end" and t["exit_price"] == 120
    assert res.equity.iloc[-1] == pytest.approx(1200.0)


def test_signal_on_last_candle_is_ignored():
    res = run(candles(flat(100, 5)), {4: (BUY, None, None)})
    assert res.trades.empty


def test_redundant_signals_are_ignored():
    rows = flat(100, 8)
    script = {0: (SELL, None, None), 1: (BUY, None, None), 2: (BUY, None, None),
              4: (SELL, None, None), 5: (SELL, None, None)}  # fmt: skip
    res = run(candles(rows), script)
    assert len(res.trades) == 1


def test_min_notional_rejects_entry_with_tiny_capital():
    """Con 3.54 USDT no se puede cumplir el mínimo de 5 USDT por orden."""
    rules = SymbolRules(step_size=1e-5, min_qty=1e-5, min_notional=5.0)
    res = run(candles(flat(100, 6)), {0: (BUY, None, None), 3: (SELL, None, None)},
              rules=rules, cash=3.54)  # fmt: skip
    assert res.trades.empty
    assert res.rejected_entries == 1
    assert res.equity.iloc[-1] == pytest.approx(3.54)


def test_quantity_is_floored_to_step_size():
    rules = SymbolRules(step_size=0.01, min_qty=0.01, min_notional=0.0)
    res = run(candles(flat(300, 4)), {0: (BUY, None, None)}, rules=rules, cash=1000.0)
    assert res.trades.iloc[0]["qty"] == pytest.approx(3.33)


def test_size_fraction_limits_capital_used():
    res = run(candles(flat(100, 4)), {0: (BUY, None, None)}, size_fraction=0.5)
    assert res.trades.iloc[0]["qty"] == pytest.approx(5.0)


def test_only_trades_inside_start_end_but_uses_warmup():
    rows = flat(100, 10)
    df = candles(rows)
    script = {
        1: (BUY, None, None),
        2: (SELL, None, None),
        6: (BUY, None, None),
        8: (SELL, None, None),
    }
    res = run(df, script, start=df.index[5], end=df.index[9])
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["entry_time"] >= df.index[5]
    assert res.equity.index[0] == df.index[5]


def test_no_overlapping_positions_and_deterministic():
    rng = np.random.default_rng(1)
    close = 100 + rng.normal(0, 1, 500).cumsum()
    df = candles([(c, c + 1, c - 1, c) for c in close])
    script = {i: (BUY if (i // 5) % 2 == 0 else SELL, None, None) for i in range(0, 500, 5)}
    a = run(df, script, costs=Costs())
    b = run(df, script, costs=Costs())
    pd.testing.assert_frame_equal(a.trades, b.trades)
    pd.testing.assert_series_equal(a.equity, b.equity)
    t = a.trades
    assert (t["entry_time"].iloc[1:].to_numpy() >= t["exit_time"].iloc[:-1].to_numpy()).all()
    assert a.equity.iloc[-1] == pytest.approx(1000.0 + t["pnl"].sum())


def test_hold_signals_do_nothing():
    res = run(candles(flat(100, 5)), {2: (HOLD, None, None)})
    assert res.trades.empty and res.equity.iloc[-1] == 1000.0


def test_invalid_size_fraction_rejected():
    with pytest.raises(ValueError):
        run(candles(flat(100, 5)), {}, size_fraction=0)


def test_engine_matches_independent_vectorized_calculation():
    """Sin costos ni stops, el capital final debe ser el producto de cada operación."""
    from bot_eve.strategies.sma_cross import SmaCross

    rng = np.random.default_rng(42)
    close = 100 * np.exp(rng.normal(0, 0.004, 4000).cumsum())
    open_ = np.concatenate([[100.0], close[:-1]])
    df = candles(
        [(o, max(o, c) * 1.001, min(o, c) * 0.999, c) for o, c in zip(open_, close, strict=True)]
    )
    strat = SmaCross(8, 25)
    res = run_backtest(df, strat, ZERO, LOOSE, 1000.0)

    sig = strat.generate(df)["signal"].to_numpy()
    equity, holding, entry = 1000.0, False, 0.0
    for i in range(len(df) - 1):
        nxt_open = df["open"].iloc[i + 1]
        if sig[i] == BUY and not holding:
            holding, entry = True, nxt_open
        elif sig[i] == SELL and holding:
            holding, equity = False, equity * nxt_open / entry
    if holding:
        equity *= df["close"].iloc[-1] / entry
    assert len(res.trades) > 10
    assert res.equity.iloc[-1] == pytest.approx(equity, rel=1e-4)
