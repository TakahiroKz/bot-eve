import numpy as np
import pandas as pd
import pytest

from bot_eve.backtest.scalp import ScalpCosts, simulate, summarize
from bot_eve.strategies.scalp_signals import align_htf, pullback_momentum

ZERO = ScalpCosts(0.0, 0.0)


def bars(rows, freq="5min"):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(
        volume=1.0
    )


def run(rows, side_at, side=1, sl=1.0, tp=2.0, hold=10, costs=ZERO):
    df = bars(rows)
    s = np.zeros(len(df), dtype=np.int8)
    s[side_at] = side
    return simulate(df, s, np.full(len(df), 2.0), sl, tp, hold, costs)


FLAT = (100, 100, 100, 100)


def test_long_hits_target_in_r_multiples():
    # señal en 0 -> entra en la apertura de la vela 1 a 100; stop 98, objetivo 104
    t = run([FLAT, FLAT, (100, 105, 100, 104), FLAT], 0)
    assert t.iloc[0].reason == "target" and t.iloc[0].r_net == pytest.approx(2.0)


def test_stop_wins_when_candle_touches_both():
    t = run([FLAT, FLAT, (100, 110, 95, 100), FLAT], 0)
    assert t.iloc[0].reason == "stop" and t.iloc[0].r_net == pytest.approx(-1.0)


def test_gap_through_stop_fills_at_open():
    t = run([FLAT, FLAT, (90, 91, 89, 90), FLAT], 0)
    assert t.iloc[0].r_net == pytest.approx(-5.0)  # (90-100)/2


def test_short_mirror_and_time_exit():
    t = run([FLAT, FLAT, (100, 100, 95, 96), FLAT], 0, side=-1)
    assert t.iloc[0].reason == "target" and t.iloc[0].r_net == pytest.approx(2.0)  # objetivo 96
    t2 = run([FLAT] * 6 + [(101, 101, 101, 101)] * 3, 0, hold=4)
    assert t2.iloc[0].reason == "time" and t2.iloc[0].r_net == pytest.approx(0.0)


def test_costs_reduce_r_and_one_position_at_a_time():
    c = ScalpCosts(fee=0.001, slip=0.0)
    t = run([FLAT, FLAT, (100, 105, 100, 104), FLAT], 0, costs=c)
    assert t.iloc[0].r_gross - t.iloc[0].r_net == pytest.approx(
        0.002 / 0.02
    )  # 2 comisiones / (d/px)
    df = bars([FLAT] * 12)
    s = np.ones(len(df), dtype=np.int8)
    tr = simulate(df, s, np.full(len(df), 2.0), 1.0, 2.0, 3, ZERO)
    assert (tr.entry_time.iloc[1:].to_numpy() > tr.exit_time.iloc[:-1].to_numpy()).all()


def test_summarize_basic():
    tr = pd.DataFrame({"r_net": [2.0, -1.0, -1.0, 2.0], "r_gross": [2.1, -0.9, -0.9, 2.1]})
    m = summarize(tr)
    assert m["trades"] == 4 and m["exp_r"] == pytest.approx(0.5) and m["pf"] == pytest.approx(2.0)
    assert m["cost_r"] == pytest.approx(0.1)


def test_htf_alignment_uses_only_closed_bars():
    h = pd.Series(
        [1.0, 2.0, 3.0], index=pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    )
    ltf = pd.date_range("2024-01-01", periods=36, freq="5min", tz="UTC")
    a = align_htf(h, ltf, "5m")
    # la vela 1h de las 00:00 se conoce al cierre de la vela 5m de las 00:55 (cierre 01:00), no antes
    assert np.isnan(a.loc["2024-01-01 00:50"]) and a.loc["2024-01-01 00:55"] == 1.0
    assert a.loc["2024-01-01 01:50"] == 1.0 and a.loc["2024-01-01 01:55"] == 2.0


def test_pullback_signals_have_no_lookahead():
    rng = np.random.default_rng(1)
    n = 3000
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.003, n)))
    df = bars(
        [
            (a, a * 1.002, a * 0.998, b)
            for a, b in zip(np.r_[close[0], close[:-1]], close, strict=True)
        ]
    )
    htf = df.resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    full, _ = pullback_momentum(df, htf, "5m")
    k = 2000
    cut = df.iloc[: k + 1]
    part, _ = pullback_momentum(
        cut, htf[htf.index + pd.Timedelta(hours=1) <= cut.index[-1] + pd.Timedelta(minutes=5)], "5m"
    )
    assert (full[:k] == part[:k]).all() and (full != 0).sum() > 10
