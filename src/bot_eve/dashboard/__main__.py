"""Dashboard local.

python -m bot_eve.dashboard            # http://127.0.0.1:8765
python -m bot_eve.dashboard --port 9000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from bot_eve.common.config import load_config
from bot_eve.dashboard.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bot_eve.dashboard")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="permite escuchar fuera de localhost (no recomendado)",
    )
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    host, port = args.host or cfg.dashboard.host, args.port or cfg.dashboard.port
    if host not in ("127.0.0.1", "localhost", "::1") and not args.allow_remote:
        print(
            f"Rechazado: {host} expone el dashboard a la red. Usa 127.0.0.1 o --allow-remote bajo tu responsabilidad."
        )
        return 2
    token = os.getenv("DASHBOARD_TOKEN") or None
    if token is None:
        print(
            "Aviso: sin DASHBOARD_TOKEN el botón de parada de emergencia queda desactivado (solo lectura)."
        )
    elif len(token) < 12:
        print("Aviso: DASHBOARD_TOKEN es corto; usa al menos 12 caracteres.")
    allowed = ["localhost", "127.0.0.1", "[::1]"] if not args.allow_remote else ["*"]
    import uvicorn

    print(f"Dashboard en http://{host}:{port}  (Ctrl+C para cerrar)")
    uvicorn.run(create_app(cfg, token, allowed), host=host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
