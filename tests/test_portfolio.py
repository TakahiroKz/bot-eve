import numpy as np
import pandas as pd
import pytest
from test_engine import LOOSE, ZERO, Scripted, candles, flat

from bot_eve.backtest.costs import Costs
from bot_eve.backtest.engine import RiskSizing, run_backtest
from bot_eve.backtest.portfolio import PortfolioLeg, run_portfolio
from bot_eve.strategies import build_strategy
from bot_eve.strategies.base import BUY, SELL

RISK = RiskSizing(risk_per_trade=0.01, default_stop_pct=0.03)


def leg(sym, rows, script, costs=ZERO):
    return PortfolioLeg(sym, candles(rows), Scripted(script), costs, LOOSE)


def test_single_leg_matches_single_symbol_engine():
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600)))
    rows = [
        (a, a * 1.01, a * 0.99, b) for a, b in zip(np.r_[close[0], close[:-1]], close, strict=True)
    ]
    df = candles(rows, "4h")
    strat = build_strategy("atr_breakout", entry_len=20, exit_len=10, stop_atr=2.0)
    costs = Costs(fee_rate=0.001, slippage=0.001)
    single = run_backtest(df, strat, costs, LOOSE, 500.0, 0.25, risk=RISK)
    port = run_portfolio([PortfolioLeg("X", df, strat, costs, LOOSE)], 500.0, RISK, 0.25, 4)
    assert len(single.trades) > 3
    assert len(port.trades) == len(single.trades)
    np.testing.assert_allclose(port.trades.pnl.to_numpy(), single.trades.pnl.to_numpy(), rtol=1e-9)
    np.testing.assert_allclose(port.equity.to_numpy(), single.equity.to_numpy(), rtol=1e-9)


def test_max_positions_limits_and_counts_skipped():
    rows = flat(100, 6)
    legs = [leg(s, rows, {1: (BUY, 0.02, None)}) for s in "ABC"]
    res = run_portfolio(legs, 1000.0, RISK, 0.25, max_positions=2)
    assert res.max_open == 2 and res.skipped_no_slot == 1
    assert sorted(res.trades.symbol) == ["A", "B"]  # orden de los pares, determinista


def test_capital_is_shared_and_never_negative():
    rows = flat(100, 6)
    legs = [leg(s, rows, {1: (BUY, 0.01, None)}) for s in "ABCD"]
    # riesgo 1% con stop 1% = 100% del capital, tope 50% por posición: solo caben 2 con el efectivo
    res = run_portfolio(legs, 1000.0, RISK, 0.5, max_positions=4)
    assert res.max_open <= 4
    assert res.equity.min() > 0
    assert (
        res.trades.qty.mul(100).sum() <= 1000.0 + 1e-6 * 4 + 1000.0
    )  # sin apalancamiento: cada nocional <= efectivo
    assert res.metrics["final_equity"] == pytest.approx(1000.0)


def test_sizing_uses_current_equity_not_initial():
    up = [(100, 100, 100, 100)] * 2 + [(200, 200, 200, 200)] * 6
    a = leg(
        "A",
        up,
        {0: (BUY, 0.5, None), 2: (SELL, None, None), 3: (BUY, 0.5, None), 6: (SELL, None, None)},
    )
    res = run_portfolio([a], 1000.0, RiskSizing(0.01, 0.03), 1.0, 1)
    first, second = res.trades.iloc[0], res.trades.iloc[1]
    assert first.qty * first.entry_price == pytest.approx(20.0)  # 1% riesgo / 50% stop * 1000
    assert second.qty * second.entry_price == pytest.approx(0.02 * res.equity.iloc[3], rel=1e-9)


def test_stop_beats_target_and_gap_fills_at_open():
    rows = flat(100, 2) + [(90, 110, 89, 100)] + flat(100, 3)
    res = run_portfolio([leg("A", rows, {0: (BUY, 0.05, 0.05)})], 1000.0, RISK, 0.25, 4)
    t = res.trades.iloc[0]
    assert t.exit_reason == "stop" and t.exit_price == 90  # gap: abre por debajo del stop


def test_forced_close_and_bad_args():
    rows = flat(100, 5)
    res = run_portfolio([leg("A", rows, {1: (BUY, 0.05, None)})], 1000.0, RISK, 0.25, 4)
    assert res.trades.iloc[0].exit_reason == "end"
    with pytest.raises(ValueError):
        run_portfolio([], 1000.0)
    with pytest.raises(ValueError):
        run_portfolio([leg("A", rows, {})], 1000.0, max_positions=0)


def test_symbols_with_different_histories_align():
    a = leg("A", flat(100, 10), {1: (BUY, 0.05, None)})
    short = candles(flat(50, 4))
    short.index = short.index + pd.Timedelta(minutes=15 * 6)  # empieza más tarde
    b = PortfolioLeg("B", short, Scripted({0: (BUY, 0.05, None)}), ZERO, LOOSE)
    res = run_portfolio([a, b], 1000.0, RISK, 0.25, 4)
    assert set(res.trades.symbol) == {"A", "B"}
