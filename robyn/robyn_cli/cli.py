#!/usr/bin/env python3
"""
CLI shim that routes argv into Robyn via httpx.ASGITransport (no TCP socket).

Usage
-----
  python -m robyn_cli.cli /ping
  python -m robyn_cli.cli GET /ping
  python -m robyn_cli.cli GET /calculate x=10 y=3
  python -m robyn_cli.cli GET /calculate x=10 y=3 op=div
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

import httpx

logging.getLogger("httpx").setLevel(logging.WARNING)

from robyn_cli.app import asgi_app

_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)


def _parse_argv(argv: list[str]) -> tuple[str, str, dict[str, str]]:
    method = "GET"
    if argv and argv[0].upper() in _METHODS:
        method, argv = argv[0].upper(), argv[1:]
    if not argv:
        print("Usage: cli.py [METHOD] <path> [key=value ...]", file=sys.stderr)
        sys.exit(1)
    path, *tokens = argv
    params: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            print(f"Invalid param '{token}' – expected key=value", file=sys.stderr)
            sys.exit(1)
        k, _, v = token.partition("=")
        params[k] = v
    return method, path, params


async def _request(
    method: str, path: str, params: dict[str, str]
) -> httpx.Response:
    query = params if method in ("GET", "DELETE", "HEAD") else None
    body = params if method not in ("GET", "DELETE", "HEAD") else None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, params=query, json=body)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    method, path, params = _parse_argv(argv)
    response = asyncio.run(_request(method, path, params))
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
    sys.exit(0 if response.is_success else 1)


if __name__ == "__main__":
    main()
