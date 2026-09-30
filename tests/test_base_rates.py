import numpy as np
import pandas as pd
import pytest

from bot_eve.backtest import base_rates as br
from bot_eve.backtest.__main__ import main
from bot_eve.backtest.costs import Costs
from bot_eve.data.store import CandleStore


def random_walk(n=60_000, seed=1, freq="5min", vol=0.0005, start="2024-01-01"):
    rng = np.random.default_rng(seed)
    close = 1.10 * np.exp(rng.normal(0, vol, n).cumsum())
    open_ = np.concatenate([[1.10], close[:-1]])
    wick = np.abs(rng.normal(0, vol / 2, n)) * close
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC", name="open_time")
    return pd.DataFrame(
        {"open": open_, "high": np.maximum(open_, close) + wick, "low": np.minimum(open_, close) - wick,
         "close": close, "volume": 1.0}, index=idx)  # fmt: skip


def test_random_entries_hit_the_target_about_sl_over_tp_plus_sl():
    b = br.Barriers(1.8, 1.2)
    out = br.outcomes(random_walk(), "5m", b)
    p = (out["outcome"] == "tp").mean()
    assert p == pytest.approx(0.40, abs=0.03)  # sin deriva: 1.2 / (1.2 + 1.8)
    assert abs(out["r_gross"].mean()) < 0.06  # esperanza bruta ~ 0 en un paseo aleatorio
    assert b.random_win == pytest.approx(0.4) and b.rr == pytest.approx(1.5)


def test_cost_in_R_lowers_expectancy_exactly_and_sets_the_breakeven():
    b = br.Barriers(1.8, 1.2)
    out = br.outcomes(random_walk(), "5m", b)
    free = br.summarize(out, 0.0, b)
    paid = br.summarize(out, 0.0002, b)
    assert paid["net_R"] == pytest.approx(free["net_R"] - paid["cost_R"], abs=1e-9)
    assert paid["win_needed"] == pytest.approx((1 + paid["cost_R"]) / 2.5)
    assert paid["lift_pts"] == pytest.approx((paid["win_needed"] - paid["p_tp"]) * 100)
    assert free["win_needed"] == pytest.approx(0.4)  # sin costo solo hace falta el 40%


def test_entry_uses_next_open_and_ignores_the_future_beyond_the_window():
    df = random_walk(8_000, seed=3)
    base = br.outcomes(df, "5m", horizon=12)
    altered = df.copy()
    altered.iloc[5_000:, altered.columns.get_indexer(["open", "high", "low", "close"])] *= 3.0
    after = br.outcomes(altered, "5m", horizon=12)
    early = base.index[
        base.index < df.index[5_000 - 14]
    ]  # ventanas que terminan antes de la alteración
    pd.testing.assert_frame_equal(base.loc[early], after.loc[early])


def test_same_candle_touching_both_barriers_counts_as_a_loss():
    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC", name="open_time")
    df = pd.DataFrame(
        {"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=idx
    )
    # ATR ≈ 1.0: objetivo ≈ +1.8, stop ≈ -1.2; la vela 20 lo toca todo
    df.iloc[20, df.columns.get_loc("high")] = 110.0
    df.iloc[20, df.columns.get_loc("low")] = 90.0
    out = br.outcomes(df, "5m", br.Barriers(1.8, 1.2), horizon=6)
    hit = out.loc[idx[16:20]]  # entradas cuya ventana incluye la vela 20
    assert set(hit["outcome"]) == {"sl"}


def test_windows_crossing_a_data_gap_are_discarded():
    df = random_walk(400, seed=5)
    gap = df.index[200:] + pd.Timedelta(days=2)  # fin de semana simulado
    df = df.set_axis(df.index[:200].append(gap))
    out = br.outcomes(df, "5m", horizon=12)
    crossing = [
        t for t in out.index if df.index[199] - pd.Timedelta(minutes=5 * 12) < t <= df.index[199]
    ]
    assert not crossing


def test_hour_blocks_and_pip_helpers():
    out = br.outcomes(random_walk(30_000), "5m")
    table = br.by_hour_block(out, 0.0002)
    assert table.index[0] == "00-04h" and len(table) == 6 and table["n"].sum() == len(out)
    assert (table["costo_R_mediano"] > 0).all()
    assert br.pip_size("USDJPY") == 0.01 and br.pip_size("EURUSD") == 0.0001
    costs = Costs(fee_rate=0.0, slippage=0.0, spread_pct=0.0)
    # 1 pip en EURUSD a 1.10 = 0.0001/1.10
    assert br.cost_fraction(costs, 1.0, "EURUSD", 1.10) == pytest.approx(0.0001 / 1.10)
    assert br.cost_fraction(Costs(0.0, 0.0, None, 0.001, 0.0002, 0.0)) == pytest.approx(0.0012)


def test_cli_base_rates_prints_cost_in_R_hour_table_and_spread_sensitivity(tmp_path, capsys):
    store = CandleStore(tmp_path / "s")
    df = random_walk(30_000)
    for month, part in df.groupby(df.index.strftime("%Y-%m")):
        store.write_month("EURUSD", "5m", month, part)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"data:\n  dir: {tmp_path / 's'}\n  symbols: [EURUSD]\nlogging:\n  file: null\n")
    assert main(["--config", str(cfg), "base-rates", "--interval", "5m", "--by-hour"]) == 0
    out = capsys.readouterr().out
    assert "costo_R" in out and "acierto necesario" in out and "Por hora del día" in out
    assert "Sensibilidad al spread" in out and "provisionales" in out
