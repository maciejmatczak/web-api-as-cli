#!/usr/bin/env python3
"""
CLI shim that routes argv into Starlette via httpx ASGITransport (no network socket).

Usage
-----
  python -m starlette_cli.cli GET /ping
  python -m starlette_cli.cli GET /calculate x=10 y=3
  python -m starlette_cli.cli GET /calculate x=10 y=3 op=div
  python -m starlette_cli.cli POST /calculate x=10 y=3 op=add
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from starlette_cli.app import app

_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"},
)


def _parse_argv(argv: list[str]) -> tuple[str, str, dict[str, str]]:
    if not argv:
        print(
            "Usage: cli.py [METHOD] <path> [key=value ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    method = "GET"
    if argv[0].upper() in _METHODS:
        method = argv[0].upper()
        argv = argv[1:]

    if not argv:
        print("Usage: cli.py [METHOD] <path> [key=value ...]", file=sys.stderr)
        sys.exit(1)

    path = argv[0]
    params: dict[str, str] = {}
    for token in argv[1:]:
        if "=" not in token:
            print(
                f"Invalid param '{token}' – expected key=value",
                file=sys.stderr,
            )
            sys.exit(1)
        k, v = token.split("=", 1)
        params[k] = v

    return method, path, params


async def _request(
    method: str,
    path: str,
    params: dict[str, str],
) -> httpx.Response:
    query = params if method in ("GET", "DELETE", "HEAD") else None
    body = params if method not in ("GET", "DELETE", "HEAD") else None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.request(
            method,
            path,
            params=query,
            json=body if body else None,
        )


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    method, path, params = _parse_argv(argv)

    response = asyncio.run(_request(method, path, params))

    try:
        data = response.json()
        print(json.dumps(data, indent=2))
    except Exception:
        print(response.text)

    sys.exit(0 if response.is_success else 1)


if __name__ == "__main__":
    main()
