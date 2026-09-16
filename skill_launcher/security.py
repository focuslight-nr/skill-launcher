"""Request guards for a localhost-only web app.

Binding to 127.0.0.1 keeps other machines out, but it does not protect
against a page the user visits in their browser: any site can issue
requests to http://127.0.0.1:<port>/ from the user's own machine, and a
DNS-rebinding attack can make such a request carry an attacker-controlled
Host header. Since this app reads and writes local files, we add two cheap
checks on top of the bind:

1. Host header allow-list  - blocks DNS rebinding (the attacker's hostname
   never matches 127.0.0.1/localhost).
2. Origin check on state-changing methods - blocks cross-site POST/PUT/DELETE
   from another page. Requests with no Origin at all (curl, scripts) are
   allowed: browsers always send Origin on these methods, so the absence of
   the header means the request did not come from a web page.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from aiohttp import web

LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1", "[::1]"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def hostname_of(host_header: str) -> str:
    """Strip the port from a Host header value ('127.0.0.1:8877' -> '127.0.0.1')."""
    host = host_header.strip()
    if host.startswith("["):  # IPv6 literal: [::1]:8877
        end = host.find("]")
        return host[: end + 1] if end != -1 else host
    return host.rsplit(":", 1)[0] if ":" in host else host


def make_local_only_middleware(extra_hostnames: set[str] | None = None):
    allowed = LOCAL_HOSTNAMES | {h.lower() for h in (extra_hostnames or set())}

    @web.middleware
    async def local_only(request: web.Request, handler):
        host = hostname_of(request.headers.get("Host", "")).lower()
        if host not in allowed:
            raise web.HTTPForbidden(text=f"unexpected Host header: {host!r}")

        if request.method not in SAFE_METHODS:
            origin = request.headers.get("Origin")
            if origin is not None:
                origin_host = (urlsplit(origin).hostname or "").lower()
                if origin_host not in allowed:
                    raise web.HTTPForbidden(text=f"cross-origin request refused: {origin!r}")

        return await handler(request)

    return local_only
