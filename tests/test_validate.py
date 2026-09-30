from conftest import make_candles

from bot_eve.data.validate import validate_candles


def test_clean_data_is_ok(candles):
    report = validate_candles(candles, "TEST", "1m")
    assert report.ok
    assert report.gaps == []
    assert report.outliers == []
    assert report.rows == 600


def test_detects_gaps_with_exact_count(candles):
    df = candles.drop(candles.index[100:110])
    report = validate_candles(df, "TEST", "1m")
    assert len(report.gaps) == 1
    gap = report.gaps[0]
    assert gap.missing == 10
    assert gap.start == "2024-01-01T01:40:00Z"
    assert gap.end == "2024-01-01T01:49:00Z"
    assert report.ok  # los huecos son aviso, no error


def test_detects_duplicates_and_unordered(candles):
    import pandas as pd

    dup = pd.concat([candles, candles.iloc[[5]]])
    report = validate_candles(dup, "TEST", "1m")
    assert report.duplicates == 1
    assert report.unordered >= 1
    assert not report.ok


def test_detects_invalid_ohlc_and_prices(candles):
    df = candles.copy()
    df.iloc[3, df.columns.get_loc("high")] = df.iloc[3]["low"] - 1  # high < low
    df.iloc[7, df.columns.get_loc("close")] = -5.0
    df.iloc[9, df.columns.get_loc("volume")] = -1.0
    report = validate_candles(df, "TEST", "1m")
    assert report.invalid_ohlc >= 1
    assert report.non_positive_price >= 1
    assert report.negative_volume == 1
    assert not report.ok


def test_detects_price_jump_outlier(candles):
    df = candles.copy()
    df.iloc[200:, df.columns.get_loc("close")] *= 1.5
    report = validate_candles(df, "TEST", "1m")
    assert len(report.outliers) == 1
    assert report.outliers[0]["time"] == "2024-01-01T03:20:00Z"


def test_empty_frame_does_not_crash():
    report = validate_candles(make_candles("2024-01-01", 5).iloc[:0], "TEST", "1m")
    assert report.rows == 0 and report.ok
