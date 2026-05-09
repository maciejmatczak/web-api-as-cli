---
name: Falcon Solution
overview: Create the `falcon/` solution directory with a framework-agnostic CLI shim (httpx.ASGITransport) that supports any HTTP method, and generalize `benchmark/bench.py` so `--solution-dir falcon` works end-to-end.
todos:
  - id: pyproject
    content: Create falcon/pyproject.toml with falcon>=4.0 and httpx dependencies
    status: completed
  - id: init
    content: Create falcon/falcon_cli/__init__.py (empty)
    status: completed
  - id: app
    content: "Create falcon/falcon_cli/app.py: inline PingResponse + CalculateResponse dataclasses, PingResource + CalculateResource (ASGI, manual param casting, dataclasses.asdict() for resp.media, error handling)"
    status: completed
  - id: cli
    content: "Create falcon/falcon_cli/cli.py: generic shim using httpx.AsyncClient + httpx.ASGITransport, [METHOD] argv, GET→query params, POST/PUT/PATCH→JSON body"
    status: completed
isProject: false
---

# Falcon Solution Plan

## Why not framework-specific TestClients

The existing `fastapi-testclient/` shim uses `fastapi.testclient.TestClient` which only calls `.get()`. Two problems:

1. Any POST/PUT/PATCH/DELETE route is unreachable from the CLI.
2. Every new framework needs its own test-client variant (`falcon.testing.TestClient.simulate_get()`, etc.).

**Better approach:** `httpx.AsyncClient` with `httpx.ASGITransport` works against any ASGI app (Falcon, FastAPI, Starlette, Litestar…) and supports all HTTP methods. The CLI shim becomes framework-agnostic.

## Files to create

### `falcon/pyproject.toml`

Two dependencies: `falcon` (the framework) and `httpx` (ASGI transport for the shim). Falcon has no httpx as a transitive dep, unlike FastAPI.

```toml
[project]
name = "falcon-testclient"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "falcon>=4.0",
    "httpx>=0.28",
]
```

### `falcon/falcon_cli/__init__.py`

Empty (mirrors `fastapi_cli/__init__.py`).

### `falcon/falcon_cli/app.py`

Falcon ASGI app with inline dataclass response models. Key points:

- Response shapes are defined as `@dataclass` at the top of the file — single source of truth for all routes
- Falcon's `resp.media` serializer only understands plain dicts/lists, so each handler converts with `dataclasses.asdict()`
- No automatic type coercion — `req.get_param('x')` returns a string, cast manually with `float()`
- Errors raised via `falcon.HTTPBadRequest` (400) / `falcon.HTTPUnprocessableEntity` (422)

```python
from __future__ import annotations
import dataclasses
import falcon.asgi


@dataclasses.dataclass
class PingResponse:
    status: str


@dataclasses.dataclass
class CalculateResponse:
    op: str
    x: float
    y: float
    result: float


class PingResource:
    async def on_get(self, req, resp):
        resp.media = dataclasses.asdict(PingResponse(status="ok"))


class CalculateResource:
    async def on_get(self, req, resp):
        try:
            x = float(req.get_param("x", required=True))
            y = float(req.get_param("y", required=True))
        except (TypeError, ValueError) as e:
            raise falcon.HTTPBadRequest(description=str(e))
        op = req.get_param("op") or "add"
        if op == "div" and y == 0:
            raise falcon.HTTPUnprocessableEntity(description="Division by zero")
        ops = {"add": x + y, "sub": x - y, "mul": x * y, "div": x / y}
        if op not in ops:
            raise falcon.HTTPBadRequest(description=f"Unknown op '{op}'")
        resp.media = dataclasses.asdict(
            CalculateResponse(op=op, x=x, y=y, result=ops[op])
        )


def create_app() -> falcon.asgi.App:
    app = falcon.asgi.App()
    app.add_route("/ping", PingResource())
    app.add_route("/calculate", CalculateResource())
    return app


app = create_app()
```

### `falcon/falcon_cli/cli.py`

Generic shim using `httpx.AsyncClient` + `httpx.ASGITransport`. No Falcon-specific test utilities needed.

**Argv contract:**

```
[METHOD] <path> [key=value ...]
```

- `METHOD` is optional and defaults to `GET` (detected as all-uppercase word before the path)
- `GET` / `DELETE`: `key=value` tokens → query params
- `POST` / `PUT` / `PATCH`: `key=value` tokens → JSON body fields

```python
import asyncio, json, sys
import httpx
from falcon_cli.app import app

_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

def _parse_argv(argv):
    method = "GET"
    if argv and argv[0].upper() in _METHODS:
        method, argv = argv[0].upper(), argv[1:]
    if not argv:
        print("Usage: cli.py [METHOD] <path> [key=value ...]", file=sys.stderr)
        sys.exit(1)
    path, *tokens = argv
    params = {}
    for token in tokens:
        k, _, v = token.partition("=")
        params[k] = v
    return method, path, params

async def _request(method, path, params):
    query = params if method in ("GET", "DELETE", "HEAD") else None
    body  = params if method not in ("GET", "DELETE", "HEAD") else None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, params=query, json=body)

def main(argv=None):
    method, path, params = _parse_argv(argv if argv is not None else sys.argv[1:])
    response = asyncio.run(_request(method, path, params))
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
    sys.exit(0 if response.is_success else 1)
```

## Setup (after implementation)

```bash
cd falcon && uv sync
python -m falcon_cli.cli GET /ping
python -m falcon_cli.cli GET /calculate x=10 y=3 op=div
```

