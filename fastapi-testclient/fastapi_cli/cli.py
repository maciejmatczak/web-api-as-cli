#!/usr/bin/env python3
"""
CLI shim that routes argv into FastAPI via TestClient (no network socket).

Usage
-----
  python -m fastapi_cli.cli /ping
  python -m fastapi_cli.cli /calculate x=10 y=3
  python -m fastapi_cli.cli /calculate x=10 y=3 op=div
"""

import json
import sys

from fastapi.testclient import TestClient

from fastapi_cli.app import app

_client = TestClient(app, raise_server_exceptions=True)


def _parse_argv(argv: list[str]) -> tuple[str, dict[str, str]]:
    if not argv:
        print("Usage: cli.py <path> [key=value ...]", file=sys.stderr)
        sys.exit(1)
    path = argv[0]
    params: dict[str, str] = {}
    for token in argv[1:]:
        if "=" not in token:
            print(f"Invalid param '{token}' – expected key=value", file=sys.stderr)
            sys.exit(1)
        k, v = token.split("=", 1)
        params[k] = v
    return path, params


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    path, params = _parse_argv(argv)

    response = _client.get(path, params=params)

    # Pretty-print JSON when possible, fall back to raw text.
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
    except Exception:
        print(response.text)

    sys.exit(0 if response.is_success else 1)


if __name__ == "__main__":
    main()
