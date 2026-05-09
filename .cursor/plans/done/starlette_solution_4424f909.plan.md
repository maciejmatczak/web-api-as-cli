---
name: Starlette solution
overview: Create a bare-Starlette CLI solution mirroring `fastapi-testclient/`, with optional HTTP method-prefix argv (`[METHOD] <path> key=value...`) for cross-framework CLI consistency.
todos:
  - id: starlette-pkg
    content: "Create starlette/ solution: pyproject.toml, starlette_cli/__init__.py, app.py, cli.py with optional method-prefix argv parsing"
    status: completed
isProject: false
---

# Starlette Solution Implementation

## Files to create

### `starlette/pyproject.toml`

- `name = "starlette-testclient"`, `requires-python = ">=3.12"`
- `dependencies = ["starlette", "httpx"]`

### `starlette/starlette_cli/__init__.py`

Empty.

### `starlette/starlette_cli/app.py`

Bare Starlette app — dataclasses defined at the top of this file, manual `request.query_params` parsing below:

```python
from dataclasses import dataclass, asdict
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

@dataclass
class CalculateResponse:
    op: str
    x: float
    y: float
    result: float

@dataclass
class ErrorResponse:
    detail: str

async def ping(request: Request):
    return JSONResponse({"status": "ok"})

async def calculate(request: Request):
    try:
        x = float(request.query_params["x"])
        y = float(request.query_params["y"])
    except (KeyError, ValueError) as e:
        return JSONResponse(asdict(ErrorResponse(detail=str(e))), status_code=422)
    op = request.query_params.get("op", "add")
    ...
    return JSONResponse(asdict(CalculateResponse(op=op, x=x, y=y, result=result)))

app = Starlette(routes=[Route("/ping", ping), Route("/calculate", calculate)])
```

Unknown op → `status_code=400`. Division by zero → `status_code=422`.

### `starlette/starlette_cli/cli.py`

Transport layer stays fully async — no `starlette.testclient`, no sync wrapper.

Argv contract:

```text
[METHOD] <path> [key=value ...]
```

- `METHOD` is optional and defaults to `GET`
- `GET` / `DELETE` / `HEAD`: `key=value` tokens become query params
- `POST` / `PUT` / `PATCH`: `key=value` tokens become JSON body fields

```python
import asyncio, json, sys
import httpx
from starlette_cli.app import app

_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

def _parse_argv(argv: list[str]) -> tuple[str, str, dict[str, str]]:
    method = "GET"
    if argv and argv[0].upper() in _METHODS:
        method, argv = argv[0].upper(), argv[1:]
    # parse <path> and key=value tokens
    ...
    return method, path, params

async def _request(method: str, path: str, params: dict[str, str]) -> httpx.Response:
    query = params if method in ("GET", "DELETE", "HEAD") else None
    body = params if method not in ("GET", "DELETE", "HEAD") else None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, params=query, json=body)

def main(argv: list[str] | None = None) -> None:
    ...
    method, path, params = _parse_argv(argv if argv is not None else sys.argv[1:])
    response = asyncio.run(_request(method, path, params))
    ...
```

`asyncio.run()` keeps `main()` synchronous for the `if __name__ == "__main__"` entry point. Each CLI invocation creates and tears down the client (acceptable for a subprocess-per-call model).


## Resulting usage

```bash
cd starlette && uv sync
python -m starlette_cli.cli GET /ping
python -m starlette_cli.cli GET /calculate x=10 y=3 op=div
```
