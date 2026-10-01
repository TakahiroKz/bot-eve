import numpy as np
import pandas as pd
import pytest

from bot_eve.backtest.pairs import simulate_pairs, spread_z
from bot_eve.backtest.scalp import ScalpCosts

ZERO = ScalpCosts(0.0, 0.0)


def idx(n):
    return pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")


def test_enters_next_open_exits_on_reversion_with_costs():
    n = 10
    z = np.array([0, 0, -3.0, -3.0, 0.5, 0, 0, 0, 0, 0])
    beta = np.ones(n)
    o1 = np.array([100, 100, 100, 100, 110, 110, 110, 110, 110, 110.0])
    o2 = np.full(n, 100.0)
    t = simulate_pairs(o1, o2, z, beta, idx(n), costs=ZERO)
    # señal en barra 2 -> entra en la apertura de la 3 (100); z cruza 0 en la barra 4 -> sale en la apertura de la 5 (110)
    assert len(t) == 1 and t.iloc[0].side == 1 and t.iloc[0].reason == "revert"
    assert t.iloc[0].ret == pytest.approx(0.5 * np.log(1.1))  # patas de peso 0.5
    t2 = simulate_pairs(o1, o2, z, beta, idx(n), costs=ScalpCosts(0.001, 0.0005))
    assert t2.iloc[0].ret == pytest.approx(0.5 * np.log(1.1) - 2 * 0.0015)


def test_stop_and_time_exits_and_short_side():
    n = 12
    z = np.array([0, 3.0, 5.0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    t = simulate_pairs(np.full(n, 100.0), np.full(n, 100.0), z, np.ones(n), idx(n), costs=ZERO)
    assert t.iloc[0].side == -1 and t.iloc[0].reason == "stop"
    z2 = np.array([0, -3.0] + [-3.0] * 10)
    t2 = simulate_pairs(
        np.full(n, 100.0), np.full(n, 100.0), z2, np.ones(n), idx(n), max_hold=3, costs=ZERO
    )
    assert t2.iloc[0].reason == "time"


def test_spread_z_is_causal():
    rng = np.random.default_rng(0)
    a = pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1500))),
        index=pd.date_range("2024", periods=1500, freq="1h", tz="UTC"),
    )
    b = pd.Series(50 * np.exp(np.cumsum(rng.normal(0, 0.01, 1500))), index=a.index)
    z_full, _ = spread_z(a, b)
    z_cut, _ = spread_z(a.iloc[:1000], b.iloc[:1000])
    np.testing.assert_allclose(z_full.iloc[:1000].dropna(), z_cut.dropna())
