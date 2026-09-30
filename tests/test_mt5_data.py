from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bot_eve.common.config import load_config
from bot_eve.data.__main__ import main
from bot_eve.data.mt5 import (
    Mt5Client,
    Mt5Error,
    median_spread_pct,
    rates_to_frame,
    sync_symbol,
)
from bot_eve.data.store import CandleStore

DTYPE = [("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"),
         ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")]  # fmt: skip


def make_rates(start: str, n: int, step_s: int = 3600, price: float = 80000.0):
    t0 = int(pd.Timestamp(start, tz="UTC").timestamp())
    arr = np.zeros(n, dtype=DTYPE)
    arr["time"] = t0 + np.arange(n) * step_s
    arr["open"] = price + np.arange(n)
    arr["close"] = price + np.arange(n) + 1
    arr["high"] = arr["close"] + 5
    arr["low"] = arr["open"] - 5
    arr["tick_volume"] = 10
    arr["spread"] = 4000  # puntos
    return arr


class FakeMt5:
    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15 = 1, 5, 15
    TIMEFRAME_H1, TIMEFRAME_H4 = 16385, 16388

    def __init__(
        self, symbols=("BTCUSD",), ok=True, history_start="2024-01-01 00:00", bars=24 * 70
    ):
        self.symbols, self.ok = set(symbols), ok
        self.history_start, self.bars = history_start, bars
        self.calls = []

    def initialize(self):
        return self.ok

    def last_error(self):
        return (-10005, "IPC timeout")

    def shutdown(self):
        pass

    def symbol_select(self, symbol, enable):
        return symbol in self.symbols

    def symbol_info(self, symbol):
        return SimpleNamespace(digits=3, point=0.001, trade_contract_size=1.0, volume_min=0.01,
                               volume_step=0.01, volume_max=10.0, spread=4000, swap_long=-37079.08,
                               swap_short=-9269.87, swap_mode=1, trade_stops_level=0)  # fmt: skip

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=83790.0, ask=83790.0)

    def account_info(self):
        return SimpleNamespace(server="Libertex-Demo", leverage=1000, currency="USD", balance=10000.0,
                               margin_mode=2, trade_allowed=True, trade_expert=True,
                               login=123456, name="Secreto", company="Libertex")  # fmt: skip

    def terminal_info(self):
        return SimpleNamespace(trade_allowed=True)

    def copy_rates_range(self, symbol, timeframe, date_from, date_to):
        self.calls.append((symbol, timeframe, date_from, date_to))
        arr = make_rates(self.history_start, self.bars)
        lo, hi = date_from.timestamp(), date_to.timestamp()
        return arr[(arr["time"] >= lo) & (arr["time"] < hi)]


def test_rates_to_frame_formats_columns_and_time():
    df = rates_to_frame(make_rates("2024-03-01", 5))
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "spread"]
    assert df.index[0] == pd.Timestamp("2024-03-01", tz="UTC") and df.index.name == "open_time"
    assert df["volume"].iloc[0] == 10 and df["spread"].iloc[0] == 4000
    assert rates_to_frame(None).empty and rates_to_frame([]).empty


def test_account_summary_hides_personal_data():
    summary = Mt5Client(FakeMt5()).account_summary()
    assert summary["modo_de_margen"] == "hedging" and summary["apalancamiento"] == 1000
    assert summary["terminal_permite_trading_algoritmico"] is True
    text = str(summary)
    assert "123456" not in text and "Secreto" not in text and "Libertex" in text  # sin login/nombre


def test_symbol_spec_and_cost_estimates_match_the_libertex_specification():
    spec = Mt5Client(FakeMt5()).symbol_spec("BTCUSD")
    assert spec.volume_min == 0.01 and spec.contract_size == 1.0
    # -37079.08 puntos * 0.001 = -37.08 USD por lote y día, sobre 83.790 USD
    assert spec.swap_long_pct_per_day == pytest.approx(-37.07908 / 83790.0)
    assert spec.spread_pct == pytest.approx(4.0 / 83790.0)
    with pytest.raises(Mt5Error, match="no existe"):
        Mt5Client(FakeMt5()).symbol_spec("XYZUSD")


def test_connect_failure_gives_actionable_error():
    with pytest.raises(Mt5Error, match="Abre MetaTrader 5"):
        Mt5Client(FakeMt5(ok=False)).connect()


def test_download_chunks_the_range_and_returns_sorted_unique_bars():
    fake = FakeMt5()
    df = Mt5Client(fake).download(
        "BTCUSD", "1h", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC)
    )
    assert len(fake.calls) >= 2  # varios tramos de ~31 días
    assert df.index.is_monotonic_increasing and df.index.is_unique
    assert len(df) == 24 * 60  # 60 días de barras horarias (ene 31 + feb 29 en 2024)
    with pytest.raises(Mt5Error, match="Intervalo"):
        Mt5Client(fake).download(
            "BTCUSD", "2h", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC)
        )


def test_sync_writes_monthly_partitions_and_spread_is_measured(tmp_path):
    store, client = CandleStore(tmp_path), Mt5Client(FakeMt5())
    n = sync_symbol(client, store, "BTCUSD", "1h", "2024-01", now=datetime(2024, 3, 15, tzinfo=UTC))
    assert n > 0 and store.months("BTCUSD", "1h") == ["2024-01", "2024-02", "2024-03"]
    assert "spread" in store.read_month("BTCUSD", "1h", "2024-01").columns
    # spread 4000 puntos * 0.001 sobre ~80.000 = 0.005%
    assert median_spread_pct(store, "BTCUSD", "1h", 0.001) == pytest.approx(4.0 / 80000, rel=0.05)


def test_sync_with_no_history_returns_zero(tmp_path):
    fake = FakeMt5(history_start="2030-01-01 00:00")
    n = sync_symbol(Mt5Client(fake), CandleStore(tmp_path), "BTCUSD", "1h", "2024-01",
                    now=datetime(2024, 2, 1, tzinfo=UTC))  # fmt: skip
    assert n == 0


def test_cli_reports_clear_error_when_metatrader_is_missing(monkeypatch, capsys, tmp_path):
    def boom(*a, **k):
        raise Mt5Error("No se pudo importar MetaTrader5. Solo existe para Windows")

    monkeypatch.setattr("bot_eve.data.__main__.Mt5Client", boom)
    assert main(["mt5-info"]) == 2
    assert "Windows" in capsys.readouterr().out


def test_cli_mt5_info_prints_costs_without_personal_data(monkeypatch, capsys):
    monkeypatch.setattr("bot_eve.data.__main__.Mt5Client", lambda: Mt5Client(FakeMt5()))
    assert main(["mt5-info", "--symbols", "BTCUSD"]) == 0
    out = capsys.readouterr().out
    assert "hedging" in out and "por día" in out and "al año" in out
    assert "123456" not in out and "Secreto" not in out


def test_mt5_config_file_is_valid_and_models_libertex_costs():
    cfg = load_config(Path(__file__).resolve().parents[1] / "config" / "mt5.yaml")
    btc, eth = cfg.backtest.costs("BTCUSD"), cfg.backtest.costs("ETHUSD")
    assert btc.entry_fee == 0.0 and btc.exit_fee == 0.001  # comisión solo en la salida
    assert btc.spread_pct == pytest.approx(0.000354) and eth.spread_pct == pytest.approx(0.002275)
    assert btc.swap_pct_per_day > 0 and eth.swap_pct_per_day > 0
    assert eth.spread_pct > 5 * btc.spread_pct  # ETH cuesta mucho más de entrar que BTC
    assert cfg.data.symbols == ["BTCUSD", "ETHUSD"]
    assert (
        list(cfg.active_strategies("demo")) == ["atr_breakout"]
        and cfg.active_strategies("live") == {}
    )
    assert cfg.execution.broker == "mt5" and cfg.execution.mode == "demo"
    assert (
        cfg.execution.state_dir.as_posix() == "state/mt5"
        and cfg.execution.i_understand_real_money is False
    )
    assert cfg.backtest.costs("OTRO").spread_pct == 0.0  # símbolos sin override usan lo general


def test_mt5_info_warns_when_there_is_no_quote_and_about_missing_commission(monkeypatch, capsys):
    fake = FakeMt5()
    fake.symbol_info_tick = lambda symbol: SimpleNamespace(
        bid=0.0, ask=0.0
    )  # pausa diaria: sin cotización
    monkeypatch.setattr("bot_eve.data.__main__.Mt5Client", lambda: Mt5Client(fake))
    assert main(["mt5-info", "--symbols", "BTCUSD"]) == 0
    out = capsys.readouterr().out
    assert "SIN COTIZACIÓN" in out and "NO expone la comisión" in out


def test_mt5_sync_flags_a_zero_historical_spread_as_unusable(monkeypatch, capsys, tmp_path):
    class ZeroSpread(FakeMt5):
        def copy_rates_range(self, symbol, timeframe, date_from, date_to):
            arr = super().copy_rates_range(symbol, timeframe, date_from, date_to)
            arr["spread"] = 0
            return arr

    monkeypatch.setattr("bot_eve.data.__main__.Mt5Client", lambda: Mt5Client(ZeroSpread()))
    assert (
        main(
            [
                "mt5-sync",
                "--symbols",
                "BTCUSD",
                "--intervals",
                "1h",
                "--from",
                "2024-01",
                "--dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert "spread histórico = 0" in capsys.readouterr().out
