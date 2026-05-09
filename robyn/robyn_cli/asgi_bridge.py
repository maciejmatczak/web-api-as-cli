"""
Bridge Robyn's in-process :class:`robyn.testing.TestClient` to ASGI3.

``Robyn`` does not implement ``async (scope, receive, send)``; this wrapper
lets ``httpx.ASGITransport`` exercise the same route pipeline without a TCP
socket.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl

from robyn.testing import TestClient


def _asgi_header_pairs(headers_obj: Any) -> list[tuple[bytes, bytes]]:
    raw = headers_obj.get_headers()
    out: list[tuple[bytes, bytes]] = []
    for key, values in raw.items():
        k = key.lower().encode("ascii")
        for v in values:
            out.append((k, str(v).encode("latin-1", errors="replace")))
    return out


async def _read_body(receive: Any) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


class _RobynASGIApp:
    __slots__ = ("_client",)

    def __init__(self, robyn_app: Any) -> None:
        self._client = TestClient(robyn_app)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"Not Found"})
            return

        method = scope["method"]
        path = scope.get("path") or "/"
        query_string = scope.get("query_string", b"").decode("ascii", errors="replace")
        body = await _read_body(receive)

        if method in ("GET", "DELETE", "HEAD"):
            params = dict(parse_qsl(query_string, keep_blank_values=True))
            tr = self._client._execute(
                method,
                path,
                query_params=params or None,
            )
        elif method in ("POST", "PUT", "PATCH"):
            payload: dict[str, Any] | None
            if body:
                try:
                    parsed = json.loads(body.decode("utf-8"))
                    payload = parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    payload = None
            else:
                payload = None
            if method == "POST":
                tr = self._client.post(path, json_data=payload)
            elif method == "PUT":
                tr = self._client.put(path, json_data=payload)
            else:
                tr = self._client.patch(path, json_data=payload)
        elif method == "OPTIONS":
            tr = self._client.options(path)
        else:
            await send(
                {
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"Method Not Allowed"})
            return

        headers = _asgi_header_pairs(tr.headers)
        await send(
            {
                "type": "http.response.start",
                "status": tr.status_code,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": tr.content})


def robyn_to_asgi(robyn_app: Any) -> _RobynASGIApp:
    return _RobynASGIApp(robyn_app)
