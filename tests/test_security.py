"""The local-only request guards, exercised through a real aiohttp app."""
from __future__ import annotations

import asyncio

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from skill_launcher.security import make_local_only_middleware


def build_app() -> web.Application:
    app = web.Application(middlewares=[make_local_only_middleware()])

    async def ok(request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app.router.add_get("/probe", ok)
    app.router.add_post("/probe", ok)
    return app


def request(method: str, headers: dict) -> int:
    async def run() -> int:
        async with TestClient(TestServer(build_app())) as client:
            resp = await client.request(method, "/probe", headers=headers)
            return resp.status

    return asyncio.run(run())


def test_localhost_requests_pass():
    assert request("GET", {"Host": "127.0.0.1:8877"}) == 200
    assert request("GET", {"Host": "localhost:8877"}) == 200


def test_foreign_host_header_is_refused():
    # What a DNS-rebinding attack looks like from the server's side.
    assert request("GET", {"Host": "attacker.example.com"}) == 403


def test_cross_origin_post_is_refused():
    assert request("POST", {"Host": "127.0.0.1:8877", "Origin": "https://evil.example"}) == 403


def test_same_origin_post_passes():
    assert request("POST", {"Host": "127.0.0.1:8877", "Origin": "http://127.0.0.1:8877"}) == 200


def test_post_without_an_origin_passes():
    # curl and scripts send no Origin; browsers always do on POST.
    assert request("POST", {"Host": "127.0.0.1:8877"}) == 200
