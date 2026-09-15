#!/usr/bin/env python3
"""skill-launcher server entrypoint.

Binds to 127.0.0.1 only. If the preferred port is busy, tries the next
ports in sequence until one is free (same fallback idea as the earlier
gui.py tools in this environment).
"""
from __future__ import annotations

import argparse
import contextlib
import socket
import sys
from pathlib import Path

from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_launcher import config  # noqa: E402
from skill_launcher.api import routes  # noqa: E402

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


def build_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    app.router.add_static("/", STATIC_DIR, show_index=False, name="static")

    async def index(request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    app.router.add_get("/", index)
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

    app = build_app()
    print(f"[skill-launcher] serving on http://{args.host}:{port}")
    print(f"[skill-launcher] config dir: {config.CONFIG_DIR}")
    print(f"[skill-launcher] target dir: {config.CLAUDE_SKILLS_DIR}")
    web.run_app(app, host=args.host, port=port, print=None)


if __name__ == "__main__":
    main()
