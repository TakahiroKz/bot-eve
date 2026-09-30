from datetime import date

import httpx
import pandas as pd
from conftest import klines_zip, make_candles

from bot_eve.data.downloader import KlineDownloader, iter_months, parse_klines_zip
from bot_eve.data.store import CandleStore


def make_client(files: dict[str, bytes], calls: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        body = files.get(request.url.path)
        return httpx.Response(200, content=body) if body else httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_milliseconds_and_microseconds_give_same_result(candles):
    ms = parse_klines_zip(klines_zip(candles, "ms"))
    us = parse_klines_zip(klines_zip(candles, "us"))
    assert ms.index.equals(us.index)
    assert ms.index[0] == pd.Timestamp("2024-01-01", tz="UTC")
    assert len(ms) == 600


def test_parse_handles_header_row(candles):
    df = parse_klines_zip(klines_zip(candles, "ms", header=True))
    assert len(df) == 600
    assert df["close"].dtype == "float64"


def test_iter_months():
    assert list(iter_months("2023-11", "2024-02")) == ["2023-11", "2023-12", "2024-01", "2024-02"]


def test_sync_monthly_then_skips_complete_months(tmp_path):
    jan = make_candles("2024-01-01", 31 * 1440)
    files = {"/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip": klines_zip(jan)}
    calls: list[str] = []
    store = CandleStore(tmp_path)
    dl = KlineDownloader(store, interval="1m", client=make_client(files, calls))

    written = dl.sync("BTCUSDT", "2024-01", ["5m", "1h"], today=date(2024, 3, 15))
    assert "2024-01" in written
    assert len(store.read("BTCUSDT", "1m", end="2024-01-31 23:59")) == 31 * 1440
    assert len(store.read_month("BTCUSDT", "5m", "2024-01")) == 31 * 288
    assert len(store.read_month("BTCUSDT", "1h", "2024-01")) == 31 * 24

    calls.clear()
    written = dl.sync("BTCUSDT", "2024-01", ["5m", "1h"], today=date(2024, 3, 15))
    assert "2024-01" not in written
    assert not any("2024-01.zip" in c for c in calls)  # reanudable: no repite descargas


def test_sync_falls_back_to_daily_files(tmp_path):
    files = {}
    for day in (1, 2, 3):
        d = make_candles(f"2024-03-{day:02d}", 1440, seed=day)
        files[f"/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-03-{day:02d}.zip"] = klines_zip(
            d, "us"
        )
    store = CandleStore(tmp_path)
    dl = KlineDownloader(store, interval="1m", client=make_client(files, []))

    written = dl.sync("BTCUSDT", "2024-03", today=date(2024, 3, 3))
    assert written == ["2024-03"]
    df = store.read_month("BTCUSDT", "1m", "2024-03")
    assert len(df) == 3 * 1440
    assert df.index.is_monotonic_increasing and not df.index.has_duplicates


def test_current_month_is_always_refreshed(tmp_path):
    files = {}
    for day in (1, 2):
        d = make_candles(f"2024-03-{day:02d}", 1440, seed=day)
        files[f"/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-03-{day:02d}.zip"] = klines_zip(
            d
        )
    store = CandleStore(tmp_path)
    dl = KlineDownloader(store, interval="1m", client=make_client(files, []))
    dl.sync("BTCUSDT", "2024-03", today=date(2024, 3, 1))
    assert len(store.read_month("BTCUSDT", "1m", "2024-03")) == 1440
    dl.sync("BTCUSDT", "2024-03", today=date(2024, 3, 2))
    assert len(store.read_month("BTCUSDT", "1m", "2024-03")) == 2880
