import numpy as np
import pandas as pd
import pytest
from conftest import volatile_candles

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import run_backtest
from bot_eve.strategies import REGISTRY, build_strategy
from bot_eve.strategies import indicators as ind
from bot_eve.strategies.atr_breakout import AtrBreakout
from bot_eve.strategies.base import BUY, SELL, Strategy, build_signals, check_no_lookahead
from bot_eve.strategies.bollinger_reversion import BollingerReversion
from bot_eve.strategies.ema_adx import EmaAdx
from bot_eve.strategies.registry import register
from bot_eve.strategies.rsi_trend import RsiTrend

EXPECTED = {"sma_cross", "rsi_trend", "atr_breakout", "bollinger_reversion", "ema_adx"}


def ohlc(closes):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="15min", tz="UTC")
    return pd.DataFrame(
        {"open": closes, "high": closes * 1.001, "low": closes * 0.999, "close": closes},
        index=idx,
    )


def test_all_strategies_are_discovered():
    assert EXPECTED <= set(REGISTRY)
    for cls in REGISTRY.values():
        assert cls.description and cls.default_grid, cls.name


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_strategy_is_free_of_lookahead(name):
    df = volatile_candles(1800)
    check_no_lookahead(build_strategy(name), df, cuts=6)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_strategy_produces_trades_and_valid_signals(name):
    df = volatile_candles(6000, seed=3)
    strat = build_strategy(name)
    sig = strat.generate(df)
    assert set(sig["signal"].unique()) <= {-1, 0, 1}
    assert (sig["signal"] == BUY).sum() > 3, f"{name} casi no genera compras"
    for col in ("stop_pct", "target_pct"):
        valid = sig[col].dropna()
        assert (valid > 0).all() and np.isfinite(valid).all()
        assert (sig.loc[sig[col].notna(), "signal"] == BUY).all()  # solo en filas de compra
    res = run_backtest(df, strat, Costs(), SymbolRules(1e-6, 1e-6, 0.0))
    assert res.metrics["trades"] > 0


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_default_grid_params_are_accepted(name):
    cls = REGISTRY[name]
    from bot_eve.backtest.walkforward import param_combinations

    for params in param_combinations(cls.default_grid):
        strat = cls(**params)
        for key, value in params.items():
            assert strat.params[key] == value


def test_build_signals_rules():
    idx = pd.RangeIndex(4)
    buy = pd.Series([True, True, False, False])
    sell = pd.Series([False, True, True, False])
    stop = pd.Series([0.01, 0.02, np.nan, np.inf])
    out = build_signals(idx, buy, sell, stop_pct=stop, target_pct=-1.0)
    assert out["signal"].tolist() == [BUY, SELL, SELL, 0]  # compra y venta juntas -> venta
    assert out["stop_pct"].iloc[0] == 0.01 and out["stop_pct"].iloc[1:].isna().all()
    assert out["target_pct"].isna().all()  # valores no positivos se ignoran


def test_rsi_trend_buys_only_bounces_in_uptrend():
    df = volatile_candles(6000, seed=11)
    strat = RsiTrend(buy_level=30, exit_level=60, trend_len=100)
    sig = strat.generate(df)
    rsi = ind.rsi(df["close"], 14)
    buys = sig.index[sig["signal"] == BUY]
    assert len(buys) > 0
    for t in buys:
        i = df.index.get_loc(t)
        assert rsi.iloc[i] > 30 >= rsi.iloc[i - 1]  # cruce al alza del nivel de compra
        assert df["close"].iloc[i] > ind.ema(df["close"], 100).iloc[i]
    assert sig["stop_pct"].dropna().gt(0).all()


def test_rsi_trend_validation():
    with pytest.raises(ValueError):
        RsiTrend(buy_level=60, exit_level=40)


def test_atr_breakout_buys_the_breakout_bar_and_sells_the_breakdown():
    closes = [100.0] * 40 + [110.0] * 10 + [95.0] * 10
    df = ohlc(closes)
    sig = AtrBreakout(entry_len=20, exit_len=10, atr_len=5).generate(df)
    assert sig["signal"].iloc[40] == BUY  # primera vela sobre el máximo previo
    assert sig["signal"].iloc[:40].eq(0).all()
    sells = sig.index[sig["signal"] == SELL]
    assert sells[0] == df.index[50]  # primera vela bajo el mínimo previo de 10 velas
    assert sig["stop_pct"].iloc[40] > 0


def test_atr_breakout_volatility_filter_blocks_quiet_breakouts():
    df = ohlc([100.0] * 40 + [100.5] * 10)
    assert (AtrBreakout(20, 10, 5).generate(df)["signal"] == BUY).any()
    assert not (AtrBreakout(20, 10, 5, min_atr_pct=0.5).generate(df)["signal"] == BUY).any()


def test_atr_breakout_validation():
    with pytest.raises(ValueError):
        AtrBreakout(entry_len=10, exit_len=20)


def test_bollinger_buys_when_price_reenters_lower_band():
    rng = np.random.default_rng(0)
    base = 100 + rng.normal(0, 0.2, 60)
    closes = np.concatenate([base, [95.0, 99.8], 100 + rng.normal(0, 0.2, 10)])
    df = ohlc(closes)
    strat = BollingerReversion(length=20, num_std=2.0, stop_width_frac=0.5, target_width_frac=0.5)
    sig = strat.generate(df)
    assert sig["signal"].iloc[61] == BUY  # vuelve a entrar tras cerrar bajo la banda
    _, up, low = ind.bollinger(df["close"], 20, 2.0)
    width_pct = (up.iloc[61] - low.iloc[61]) / df["close"].iloc[61]
    assert sig["stop_pct"].iloc[61] == pytest.approx(0.5 * width_pct)
    assert sig["target_pct"].iloc[61] == pytest.approx(0.5 * width_pct)


def test_ema_adx_requires_strong_trend():
    df = volatile_candles(6000, seed=5)
    strat = EmaAdx(adx_min=25)
    sig = strat.generate(df)
    adx = ind.adx(df, 14)
    buys = sig.index[sig["signal"] == BUY]
    assert len(buys) > 0
    assert all(adx.loc[t] > 25 for t in buys)
    more_buys = (EmaAdx(adx_min=0).generate(df)["signal"] == BUY).sum()
    assert more_buys > len(buys)
    filtered = (EmaAdx(adx_min=0, trend_filter=True).generate(df)["signal"] == BUY).sum()
    assert filtered < more_buys


def test_registry_add_remove_and_duplicates():
    class Dummy(Strategy):
        name = "dummy_test"

        def generate(self, df):
            return build_signals(
                df.index, pd.Series(False, index=df.index), pd.Series(False, index=df.index)
            )

    register(Dummy)
    try:
        assert build_strategy("dummy_test").name == "dummy_test"
        register(Dummy)  # registrar la misma clase otra vez es idempotente

        class Other(Dummy):
            name = "dummy_test"

        with pytest.raises(ValueError, match="Ya existe"):
            register(Other)
    finally:
        REGISTRY.pop("dummy_test")
    with pytest.raises(ValueError, match="desconocida"):
        build_strategy("dummy_test")
