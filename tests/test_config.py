import pytest

from bot_eve.common.config import load_config


def test_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.data.symbols == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    assert cfg.data.base_interval == "1m"


def test_loads_yaml_and_validates(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("data:\n  symbols: [ETHUSDT]\n  start: '2022-05'\n")
    cfg = load_config(f)
    assert cfg.data.symbols == ["ETHUSDT"]
    assert cfg.data.start == "2022-05"


def test_rejects_bad_start(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("data:\n  start: '2022-13'\n")
    with pytest.raises(ValueError):
        load_config(f)


def test_explicit_missing_config_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_repo_default_config_is_valid(monkeypatch):
    monkeypatch.chdir(__file__.rsplit("/tests", 1)[0])
    assert load_config().data.start == "2020-01"
