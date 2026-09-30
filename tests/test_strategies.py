import pytest
from conftest import make_candles

from bot_eve.strategies import build_strategy
from bot_eve.strategies.base import BUY, SELL, Strategy, check_no_lookahead, empty_signals
from bot_eve.strategies.sma_cross import SmaCross


def test_sma_cross_has_no_lookahead():
    df = make_candles("2024-01-01", 800, freq="15min", seed=3)
    check_no_lookahead(SmaCross(fast=5, slow=20, stop_pct=0.01, target_pct=0.02), df, cuts=15)


def test_lookahead_detector_catches_a_cheating_strategy():
    class Cheater(Strategy):
        name = "cheater"

        def generate(self, df):
            out = empty_signals(df.index)
            out["signal"] = (df["close"].shift(-1) > df["close"]).astype("int8")  # mira el futuro
            return out

    df = make_candles("2024-01-01", 200, freq="15min")
    with pytest.raises(AssertionError, match="look-ahead"):
        check_no_lookahead(Cheater(), df)


def test_sma_cross_emits_both_signals_and_attaches_stops_only_to_buys():
    df = make_candles("2024-01-01", 2000, freq="15min", seed=5)
    sig = SmaCross(fast=5, slow=20, stop_pct=0.01, target_pct=0.02).generate(df)
    assert (sig["signal"] == BUY).any() and (sig["signal"] == SELL).any()
    buys = sig[sig["signal"] == BUY]
    assert buys["stop_pct"].eq(0.01).all() and buys["target_pct"].eq(0.02).all()
    assert sig[sig["signal"] != BUY]["stop_pct"].isna().all()


def test_sma_cross_validation_and_registry():
    with pytest.raises(ValueError):
        SmaCross(fast=30, slow=10)
    assert isinstance(build_strategy("sma_cross", fast=3, slow=9), SmaCross)
    with pytest.raises(ValueError):
        build_strategy("nope")
