"""Dashboard local de solo lectura + parada de emergencia.

Seguridad:
- No tiene claves del exchange: solo lee `status.json` y `trades.jsonl` de cada bot.
- Escucha solo en localhost y rechaza cabeceras Host ajenas (DNS rebinding).
- La única acción (kill / unkill) exige la cabecera `X-Dashboard-Token` igual a `DASHBOARD_TOKEN`;
  sin ese token configurado, las acciones quedan desactivadas.
- CSP estricta con nonce, sin recursos externos.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from bot_eve.common.config import Config, DashboardBot
from bot_eve.dashboard.data import age_seconds, pnl_curve, read_status, read_trades, trade_stats
from bot_eve.dashboard.page import PAGE

LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
DEFAULT_BOTS = [
    DashboardBot(name="Binance demo", state_dir=Path("state")),
    DashboardBot(name="MT5 demo", state_dir=Path("state/mt5")),
]


def create_app(
    cfg: Config, token: str | None = None, allowed_hosts: list[str] | None = None
) -> FastAPI:
    bots = cfg.dashboard.bots or DEFAULT_BOTS
    app = FastAPI(title="bot-eve", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or LOCAL_HOSTS)

    def bot_or_404(index: int) -> DashboardBot:
        if not 0 <= index < len(bots):
            raise HTTPException(404, "bot desconocido")
        return bots[index]

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        nonce = secrets.token_urlsafe(16)
        csp = (
            f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'"
        )
        return HTMLResponse(
            PAGE.replace("__NONCE__", nonce), headers={"Content-Security-Policy": csp}
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/overview")
    def overview() -> JSONResponse:
        now = datetime.now(UTC)
        out = []
        for i, bot in enumerate(bots):
            status = read_status(bot.state_dir)
            age = age_seconds(status, now)
            poll = (status or {}).get("poll_seconds", 20)
            out.append(
                {
                    "index": i,
                    "name": bot.name,
                    "status": status,
                    "age_seconds": age,
                    "online": age is not None and age <= max(3 * poll, 120),
                    "stats": trade_stats(read_trades(bot.state_dir)),
                    "kill_file": (Path(bot.state_dir) / "KILL").exists(),
                }
            )
        return JSONResponse(
            {"server_time": now.isoformat(), "actions_enabled": bool(token), "bots": out}
        )

    @app.get("/api/bots/{index}/trades")
    def trades(index: int, limit: int = 40) -> JSONResponse:
        bot = bot_or_404(index)
        items = read_trades(bot.state_dir)
        limit = max(1, min(limit, 500))
        recent = sorted(items, key=lambda t: t.get("exit_time", ""), reverse=True)[:limit]
        return JSONResponse(
            {"trades": recent, "curve": pnl_curve(items), "stats": trade_stats(items)}
        )

    def check_token(supplied: str | None) -> None:
        if not token:
            raise HTTPException(
                403, "Acciones desactivadas: define DASHBOARD_TOKEN en .env y reinicia"
            )
        if not supplied or not hmac.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(403, "Token incorrecto")

    @app.post("/api/bots/{index}/kill")
    def kill(index: int, x_dashboard_token: str | None = Header(default=None)) -> JSONResponse:
        check_token(x_dashboard_token)
        bot = bot_or_404(index)
        Path(bot.state_dir).mkdir(parents=True, exist_ok=True)
        (Path(bot.state_dir) / "KILL").write_text("kill from dashboard", encoding="utf-8")
        return JSONResponse(
            {
                "ok": True,
                "message": f"KILL creado para {bot.name}: cerrará posiciones y se detendrá",
            }
        )

    @app.post("/api/bots/{index}/unkill")
    def unkill(index: int, x_dashboard_token: str | None = Header(default=None)) -> JSONResponse:
        check_token(x_dashboard_token)
        bot = bot_or_404(index)
        (Path(bot.state_dir) / "KILL").unlink(missing_ok=True)
        return JSONResponse({"ok": True, "message": f"KILL retirado para {bot.name}"})

    return app
