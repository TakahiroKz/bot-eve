import pytest
from conftest import make_candles

from bot_eve.data.store import CandleStore


def test_roundtrip_and_months(tmp_path, candles):
    store = CandleStore(tmp_path)
    store.write_month("BTCUSDT", "1m", "2024-01", candles)
    store.write_month("BTCUSDT", "1m", "2024-02", make_candles("2024-02-01", 50))
    assert store.months("BTCUSDT", "1m") == ["2024-01", "2024-02"]
    back = store.read_month("BTCUSDT", "1m", "2024-01")
    assert back.equals(candles) or (back.index.equals(candles.index) and len(back) == 600)
    assert len(store.read("BTCUSDT", "1m")) == 650


def test_read_range_filter(tmp_path, candles):
    store = CandleStore(tmp_path)
    store.write_month("BTCUSDT", "1m", "2024-01", candles)
    out = store.read("BTCUSDT", "1m", start="2024-01-01 01:00", end="2024-01-01 01:59")
    assert len(out) == 60


def test_read_missing_returns_empty(tmp_path):
    assert store_read_empty(tmp_path)


def store_read_empty(tmp_path):
    return CandleStore(tmp_path).read("NOPE", "1m").empty


def test_refuses_empty_partition(tmp_path, candles):
    with pytest.raises(ValueError):
        CandleStore(tmp_path).write_month("BTCUSDT", "1m", "2024-01", candles.iloc[:0])
