"""Entry point: binds to 127.0.0.1 and serves the UI.

If the preferred port is busy, the next ports in sequence are tried so a
second instance (or a leftover process) never blocks startup.
"""
from __future__ import annotations

import argparse
import contextlib
import socket
from pathlib import Path

from aiohttp import web

from . import config
from .api import routes
from .security import make_local_only_middleware

HOST = "127.0.0.1"
DEFAULT_PORT = 8877
PORT_SCAN_RANGE = 20
STATIC_DIR = Path(__file__).resolve().parent / "static"


def port_is_free(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def find_free_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + PORT_SCAN_RANGE):
        if port_is_free(host, port):
            return port
    raise RuntimeError(f"No free port found in range {preferred}-{preferred + PORT_SCAN_RANGE - 1}")


def build_app(extra_hostnames: set[str] | None = None) -> web.Application:
    app = web.Application(middlewares=[make_local_only_middleware(extra_hostnames)])
    app.add_routes(routes)

    async def index(request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    # Register the exact "/" route BEFORE add_static: aiohttp resolves resources
    # in registration order, and add_static's catch-all resource matches "/"
    # too (filename="" -> the static dir itself), which with show_index=False
    # makes aiohttp raise 403 Forbidden on the directory. Registering our
    # explicit index route first ensures it wins the match for "/".
    app.router.add_get("/", index)
    app.router.add_static("/", STATIC_DIR, show_index=False, name="static")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="skill-launcher local web app")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default=HOST)
    args = parser.parse_args()

    config.ensure_dirs()
    port = find_free_port(args.host, args.port)
    if port != args.port:
        print(f"[skill-launcher] port {args.port} busy, using {port} instead")

    app = build_app(extra_hostnames={args.host})
    print(f"[skill-launcher] serving on http://{args.host}:{port}")
    print(f"[skill-launcher] config dir: {config.CONFIG_DIR}")
    print(f"[skill-launcher] target dir: {config.CLAUDE_SKILLS_DIR}")
    web.run_app(app, host=args.host, port=port, print=None)
