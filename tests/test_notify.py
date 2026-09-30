import logging

import httpx

from bot_eve.common.config import Config, NotifyConfig, TelegramConfig
from bot_eve.notify import NullNotifier, TelegramNotifier, make_notifier
from bot_eve.notify.__main__ import main
from bot_eve.notify.telegram import discover_chat_id

TOKEN = "123456:SECRET-TOKEN-abc"


def notifier(handler, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TelegramNotifier(TOKEN, "42", label="Binance demo", client=client, **kw)


def test_sends_to_the_configured_chat_with_label():
    seen = []

    def handler(request):
        seen.append((str(request.url), request.read().decode()))
        return httpx.Response(200, json={"ok": True})

    assert notifier(handler).send("hola")
    url, body = seen[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert '"chat_id":"42"' in body.replace(" ", "") and "[Binance demo] hola" in body


def test_identical_messages_are_grouped_but_critical_ones_always_go_through():
    calls = []
    now = [0.0]
    n = notifier(lambda r: calls.append(1) or httpx.Response(200), clock=lambda: now[0])
    assert n.send("x") and not n.send("x")  # el segundo idéntico se agrupa
    assert n.send("x", critical=True)  # lo crítico nunca se omite
    now[0] = 120.0
    assert n.send("x")  # pasada la ventana vuelve a enviarse
    assert len(calls) == 3


def test_a_failing_telegram_never_raises_and_never_logs_the_token(caplog):
    def boom(request):
        raise httpx.ConnectError(f"no route to {request.url}")  # el texto del error incluye la URL

    # Peor caso: httpx con su nivel por defecto (sin el ajuste de setup_logging): registraría la URL.
    logging.getLogger("httpx").setLevel(logging.NOTSET)
    with caplog.at_level(logging.DEBUG):
        assert notifier(boom).send("hola") is False
        assert notifier(lambda r: httpx.Response(401)).send("otro") is False
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "ConnectError" in logs and "401" in logs
    assert TOKEN not in logs and "SECRET" not in logs  # el token jamás aparece en los logs


def test_make_notifier_respects_config_and_missing_credentials(monkeypatch, caplog):
    off = Config()
    assert isinstance(make_notifier(off, "x"), NullNotifier)
    on = Config(notify=NotifyConfig(telegram=TelegramConfig(enabled=True)))
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)
    with caplog.at_level(logging.WARNING):
        assert isinstance(make_notifier(on, "x"), NullNotifier)  # no rompe el bot
    assert "faltan" in caplog.text.lower()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    built = make_notifier(on, "MT5 demo")
    assert isinstance(built, TelegramNotifier) and built.label == "MT5 demo"
    labelled = Config(notify=NotifyConfig(label="Mi bot", telegram=TelegramConfig(enabled=True)))
    assert make_notifier(labelled, "x").label == "Mi bot"


def test_discover_chat_id_lists_people_who_wrote_to_the_bot():
    payload = {"result": [
        {"message": {"chat": {"id": 777, "first_name": "Leo"}}},
        {"message": {"chat": {"id": 777, "first_name": "Leo"}}},
        {"channel_post": {"chat": {"id": -100, "title": "Canal"}}},
    ]}  # fmt: skip
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    )
    assert discover_chat_id(TOKEN, client) == [("777", "Leo"), ("-100", "Canal")]


def test_cli_without_token_explains_what_is_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert main(["test"]) == 2
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().out


def test_token_is_redacted_from_httpx_request_logs_even_at_info_level(caplog):
    """httpx registra la URL de cada petición, que contiene el token."""
    logging.getLogger("httpx").setLevel(logging.NOTSET)
    with caplog.at_level(logging.INFO):
        assert notifier(lambda r: httpx.Response(200, json={"ok": True})).send("hola")
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "sendMessage" in logs and "/bot***" in logs  # se ve que hubo petición...
    assert TOKEN not in logs and "SECRET" not in logs  # ...pero sin el secreto
