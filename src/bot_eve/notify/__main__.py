"""Utilidades de Telegram.

python -m bot_eve.notify chat-id   # tras escribirle cualquier mensaje a tu bot: muestra tu chat_id
python -m bot_eve.notify test      # envía un mensaje de prueba con la configuración de .env
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from bot_eve.notify.telegram import TelegramNotifier, discover_chat_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bot_eve.notify")
    parser.add_argument("command", choices=["chat-id", "test"])
    args = parser.parse_args(argv)
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Falta TELEGRAM_BOT_TOKEN en el archivo .env")
        return 2
    try:
        if args.command == "chat-id":
            chats = discover_chat_id(token)
            if not chats:
                print(
                    "Sin mensajes. Abre tu bot en Telegram, escríbele «hola» y repite este comando."
                )
                return 1
            for chat_id, name in chats:
                print(f"chat_id: {chat_id}  ({name})   ->  TELEGRAM_CHAT_ID={chat_id}")
            return 0
    except Exception as exc:  # noqa: BLE001 - nunca mostrar la URL (contiene el token)
        print(f"No se pudo consultar Telegram ({type(exc).__name__}). Revisa el token.")
        return 2
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not chat:
        print("Falta TELEGRAM_CHAT_ID en .env (usa: python -m bot_eve.notify chat-id)")
        return 2
    ok = TelegramNotifier(token, chat, label="prueba").send(
        "✅ Las alertas de bot-eve funcionan.", critical=True
    )
    print("Mensaje enviado." if ok else "No se pudo enviar el mensaje. Revisa token y chat_id.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
