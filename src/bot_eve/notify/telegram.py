"""Alertas por Telegram.

Reglas de diseño:
- **Una alerta nunca rompe el bot**: todo error se captura y se registra.
- **El token nunca se escribe en logs**: la URL de la API lo contiene, así que al fallar solo se
  registra el tipo de error, nunca su texto ni la URL.
- Solo se escribe al chat configurado. Los mensajes idénticos repetidos en una ventana corta se
  agrupan para no inundar el chat.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Protocol

import httpx

log = logging.getLogger(__name__)
API = "https://api.telegram.org"


_TOKEN_IN_URL = re.compile(r"/bot\d+:[\w-]+")


class RedactTokenFilter(logging.Filter):
    """Tapa el token de Telegram en cualquier mensaje de log.

    `httpx` registra la URL de cada petición (INFO), y la de Telegram contiene el token; sin este
    filtro el secreto acabaría en los archivos de log según el nivel configurado.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _TOKEN_IN_URL.search(message):
            record.msg, record.args = _TOKEN_IN_URL.sub("/bot***", message), ()
        return True


def _protect_logs() -> None:
    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTokenFilter) for f in logger.filters):
            logger.addFilter(RedactTokenFilter())


class Notifier(Protocol):
    def send(self, text: str, critical: bool = False) -> bool: ...


class NullNotifier:
    """No hace nada (alertas desactivadas o sin credenciales)."""

    def send(self, text: str, critical: bool = False) -> bool:
        return False


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        label: str = "",
        client: httpx.Client | None = None,
        dedupe_seconds: float = 60.0,
        clock=time.monotonic,
    ) -> None:
        _protect_logs()  # antes de cualquier petición
        self._url = f"{API}/bot{token}/sendMessage"
        self.chat_id = str(chat_id)
        self.label = label
        self.client = client or httpx.Client(timeout=10)
        self._dedupe_seconds = dedupe_seconds
        self._clock = clock
        self._recent: dict[str, float] = {}

    def send(self, text: str, critical: bool = False) -> bool:
        """Envía un mensaje. Devuelve True si Telegram lo aceptó. Nunca lanza excepciones."""
        body = f"[{self.label}] {text}" if self.label else text
        now = self._clock()
        if not critical and now - self._recent.get(body, -1e9) < self._dedupe_seconds:
            return False  # idéntico y reciente
        self._recent[body] = now
        if len(self._recent) > 200:  # no crecer sin límite
            self._recent = {k: v for k, v in self._recent.items() if now - v < self._dedupe_seconds}
        try:
            resp = self.client.post(self._url, json={"chat_id": self.chat_id, "text": body})
            if resp.status_code != 200:
                log.warning("Telegram rechazó el mensaje (HTTP %s)", resp.status_code)
                return False
            return True
        except Exception as exc:  # noqa: BLE001 - una alerta jamás debe romper el bot
            log.warning("No se pudo enviar la alerta de Telegram (%s)", type(exc).__name__)
            return False


def make_notifier(cfg, label: str) -> Notifier:
    """Crea el notificador según la configuración; sin credenciales devuelve uno nulo."""
    tg = cfg.notify.telegram
    if not tg.enabled:
        return NullNotifier()
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        log.warning("Telegram activado pero faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en .env")
        return NullNotifier()
    return TelegramNotifier(token, chat, label=cfg.notify.label or label)


def discover_chat_id(token: str, client: httpx.Client | None = None) -> list[tuple[str, str]]:
    """Lista (chat_id, nombre) de quienes escribieron al bot (para configurar TELEGRAM_CHAT_ID)."""
    _protect_logs()
    client = client or httpx.Client(timeout=10)
    resp = client.get(f"{API}/bot{token}/getUpdates")
    resp.raise_for_status()
    found: dict[str, str] = {}
    for update in resp.json().get("result", []):
        chat = (update.get("message") or update.get("channel_post") or {}).get("chat")
        if chat:
            name = chat.get("title") or chat.get("first_name") or chat.get("username") or "?"
            found[str(chat["id"])] = name
    return list(found.items())
