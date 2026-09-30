import pandas as pd
import pytest
from conftest import make_candles

from bot_eve.data.intervals import parse_interval, to_timedelta
from bot_eve.data.resample import resample_ohlcv


def test_resample_5m_ohlcv_is_correct(candles):
    out = resample_ohlcv(candles, "5m")
    first = candles.iloc[:5]
    row = out.iloc[0]
    assert out.index[0] == candles.index[0]
    assert row["open"] == first["open"].iloc[0]
    assert row["high"] == first["high"].max()
    assert row["low"] == first["low"].min()
    assert row["close"] == first["close"].iloc[-1]
    assert row["volume"] == pytest.approx(first["volume"].sum())
    assert row["trades"] == first["trades"].sum()
    assert row["n_base"] == 5
    assert len(out) == len(candles) // 5


def test_resample_labels_by_open_time_and_aligns_bins():
    df = make_candles("2024-01-01 00:03", 30)  # empieza desalineado
    out = resample_ohlcv(df, "15m")
    assert out.index[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")
    assert out["n_base"].iloc[0] == 12  # solo 00:03-00:14


def test_resample_does_not_invent_candles_in_gaps():
    df = make_candles("2024-01-01", 120)
    df = df.drop(df.index[30:90])  # hueco de 60 minutos
    out = resample_ohlcv(df, "15m")
    starts = set(out.index)
    assert pd.Timestamp("2024-01-01 00:45", tz="UTC") not in starts
    assert pd.Timestamp("2024-01-01 01:00", tz="UTC") not in starts
    assert (out["n_base"] > 0).all()


def test_resample_flags_partial_candles():
    df = make_candles("2024-01-01", 10)
    df = df.drop(df.index[2])
    out = resample_ohlcv(df, "5m")
    assert out["n_base"].iloc[0] == 4


def test_resample_4h_and_1h_consistent(candles):
    hourly = resample_ohlcv(candles, "1h")
    assert len(hourly) == 10
    assert hourly["volume"].sum() == pytest.approx(candles["volume"].sum())


def test_interval_parsing():
    assert to_timedelta("5m") == pd.Timedelta(minutes=5)
    assert to_timedelta("4h") == pd.Timedelta(hours=4)
    assert parse_interval("1d") == (1, "d")
    for bad in ("", "m5", "0m", "5x", "5"):
        with pytest.raises(ValueError):
            parse_interval(bad)
