from functools import partial

import pandas as pd
import pytest
from conftest import make_candles

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.walkforward import param_combinations, split_holdout, walk_forward
from bot_eve.strategies import build_strategy

RULES = SymbolRules(step_size=1e-6, min_qty=1e-6, min_notional=0.0)
GRID = {"fast": [3, 5], "slow": [12, 20]}


def data(n=1500, seed=11):
    return make_candles("2024-01-01", n, freq="15min", seed=seed)


def wf(df, **kw):
    make = partial(build_strategy, "sma_cross")
    return walk_forward(df, make, GRID, 400, 200, min_trades=1, costs=Costs(), rules=RULES, **kw)


def test_param_combinations():
    combos = param_combinations({"a": [1, 2], "b": [3]})
    assert combos == [{"a": 1, "b": 3}, {"a": 2, "b": 3}]


def test_split_holdout_is_disjoint_and_complete():
    df = data()
    dev, hold = split_holdout(df, "2024-01-10")
    assert len(dev) + len(hold) == len(df)
    assert dev.index.max() < pd.Timestamp("2024-01-10", tz="UTC") <= hold.index.min()


def test_windows_are_contiguous_and_test_follows_train():
    res = wf(data())
    assert len(res.windows) == (1500 - 400) // 200
    step = pd.Timedelta(minutes=15)
    for w in res.windows:
        assert w.test_start == w.train_end + step
        assert w.best_params in param_combinations(GRID)
    for a, b in zip(res.windows, res.windows[1:], strict=False):
        assert b.test_start == a.test_end + step  # sin solaparse ni dejar huecos
    assert res.equity.index.is_unique and res.equity.index.is_monotonic_increasing


def test_capital_compounds_across_windows():
    res = wf(data())
    ends = [w.test_metrics["final_equity"] for w in res.windows]
    starts = [w.test_metrics["initial_cash"] for w in res.windows]
    assert starts[0] == 1000.0
    for prev_end, nxt_start in zip(ends[:-1], starts[1:], strict=True):
        assert nxt_start == pytest.approx(prev_end)
    assert res.metrics["final_equity"] == pytest.approx(ends[-1])


def test_results_do_not_depend_on_the_future():
    """Alterar datos posteriores a una ventana no debe cambiar sus resultados."""
    df = data()
    base = wf(df)
    altered = df.copy()
    cut = base.windows[2].test_end  # a partir de aquí se corrompe el futuro
    altered.loc[altered.index > cut, ["open", "high", "low", "close"]] *= 3.7
    other = wf(altered)
    for a, b in zip(base.windows[:3], other.windows[:3], strict=True):
        assert a.best_params == b.best_params
        assert a.test_metrics["final_equity"] == pytest.approx(b.test_metrics["final_equity"])


def test_rejects_bad_inputs():
    make = partial(build_strategy, "sma_cross")
    with pytest.raises(ValueError):
        walk_forward(data(100), make, GRID, 400, 200)
    with pytest.raises(ValueError):
        walk_forward(data(), make, GRID, 400, 200, objective="magic")


def test_benchmark_is_a_single_buy_and_hold_over_the_oos_period():
    df = data()
    res = wf(df)
    oos = df.loc[res.equity.index[0] : res.equity.index[-1]]
    costs = Costs()
    units = 1000.0 / (oos["open"].iloc[0] * (1 + costs.slippage) * (1 + costs.fee_rate))
    expected = units * oos["close"].iloc[-1] * (1 - costs.slippage - costs.fee_rate)
    assert res.benchmark.iloc[-1] == pytest.approx(expected)
    assert res.metrics["buy_and_hold_return"] == pytest.approx(expected / 1000.0 - 1)
