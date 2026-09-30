import math

import pandas as pd
import pytest

from bot_eve.backtest.metrics import max_drawdown, profit_factor, sharpe_ratio


def test_max_drawdown():
    eq = pd.Series([100, 120, 90, 110, 60, 130.0])
    assert max_drawdown(eq) == pytest.approx(60 / 120 - 1)
    assert max_drawdown(pd.Series([1, 2, 3.0])) == 0


def test_profit_factor():
    assert profit_factor(pd.Series([10, -5, 5, -5.0])) == pytest.approx(1.5)
    assert profit_factor(pd.Series([10.0, 5.0])) == float("inf")
    assert math.isnan(profit_factor(pd.Series([0.0])))


def test_sharpe_needs_variation_and_history():
    idx = pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC")
    assert math.isnan(sharpe_ratio(pd.Series(100.0, index=idx)))
    up = pd.Series([100 * 1.01**i for i in range(10)], index=idx)
    assert math.isnan(sharpe_ratio(up))  # sin variación en los retornos diarios
    noisy = pd.Series([100, 101, 100, 102, 101, 103, 102, 104, 103, 105.0], index=idx)
    assert sharpe_ratio(noisy) > 0
