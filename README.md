# rnd-web-api-as-cli

Exploring whether a web API framework can double as a local CLI runtime, with no network socket.

The core idea: instead of starting a real HTTP server, route CLI arguments directly into an
in-process app object (`TestClient` / `ASGITransport`). The framework still handles routing,
validation, and serialization, while users invoke it like a normal command.

## Common contract

Every solution implements the same domain operations:

- `ping` / `/ping` returns `{"status": "ok"}`
- `calculate` / `/calculate` computes on `x`, `y`, and `op`
  - `op` supports: `add`, `sub`, `mul`, `div` (default `add`)
  - response shape: `{"op": "...", "x": ..., "y": ..., "result": ...}`
  - errors are reported for unknown operations and division by zero

Across **HTTP-layer** implementations (`fastapi-testclient/`, `falcon/`, `robyn/`, `starlette/`),
`/calculate` is exposed as **`GET` only**, with **`x`**, **`y`**, and optional **`op`** as **query
parameters** — no JSON body on `/calculate` in the mounted apps. CLI shims may still accept other
HTTP method tokens for transport; non-`GET` requests to `/calculate` should fail at routing (for
example **405 Method Not Allowed**).

## Implemented solutions

Each subdirectory is a self-contained experiment with its own `uv`-managed `.venv`.

### `fastapi-testclient/`

Framework: [FastAPI](https://fastapi.tiangolo.com/) with in-process `TestClient`.

CLI examples:

```bash
python -m fastapi_cli.cli /ping
python -m fastapi_cli.cli /calculate x=10 y=3
python -m fastapi_cli.cli /calculate x=10 y=3 op=div
```

### `cyclopts/`

Framework: [cyclopts](https://github.com/BrianPugh/cyclopts) baseline (pure CLI, no web layer).

CLI examples:

```bash
python -m cyclopts_cli ping
python -m cyclopts_cli calculate 10 3
python -m cyclopts_cli calculate 10 3 --op div
```

### `falcon/`

Framework: [Falcon ASGI](https://falcon.readthedocs.io/) with `httpx.ASGITransport`.

Implemented API routes:

- `GET /ping`
- `GET /calculate?x=&y=&op=`

CLI examples:

```bash
python -m falcon_cli.cli /ping
python -m falcon_cli.cli GET /calculate x=10 y=3
python -m falcon_cli.cli GET /calculate x=10 y=3 op=div
```

### `robyn/`

Framework: [Robyn](https://robyn.tech/) wrapped into an ASGI3 callable for `httpx.ASGITransport`.

Implemented API routes:

- `GET /ping`
- `GET /calculate?x=&y=&op=`

CLI examples:

```bash
python -m robyn_cli.cli /ping
python -m robyn_cli.cli GET /calculate x=10 y=3
python -m robyn_cli.cli GET /calculate x=10 y=3 op=div
```

### `starlette/`

Framework: [Starlette](https://www.starlette.io/) with `httpx.ASGITransport`.

Implemented API routes:

- `GET`, `HEAD` on `/ping`
- `GET /calculate?x=&y=&op=`

CLI examples:

```bash
python -m starlette_cli.cli GET /ping
python -m starlette_cli.cli GET /calculate x=10 y=3
python -m starlette_cli.cli GET /calculate x=10 y=3 op=div
```

## HTTP method handling in CLI shims

For `falcon_cli`, `robyn_cli`, and `starlette_cli`:

- supported method tokens: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`
- if omitted, method defaults to `GET`
- `GET`/`DELETE`/`HEAD` send `key=value` tokens as query parameters
- `POST`/`PUT`/`PATCH` send `key=value` tokens as JSON body

The mounted apps all expose **`/calculate` as `GET` only** (see **Common contract**). The shim may
still send `POST`/`PUT`/`PATCH` with a JSON body for transport, but those requests receive **405**
(or equivalent) from the Starlette/Falcon/Robyn/FastAPI apps on `/calculate`.

## Benchmark

`benchmark/bench.py` compares **subprocess cold-start** across every solution (`ping` and
`calculate`). Baselines use the same interpreter as the benchmark script (`python -c pass` and a tiny
stdlib snippet); each solution row uses that solution’s `.venv` Python.

```bash
# from repo root (ensure each solution has been `uv sync`’d)
python3 benchmark/bench.py
python3 benchmark/bench.py --runs 30 --warmup 5
python3 benchmark/bench.py --solution starlette
```

Example ballpark on one machine (Python 3.12, WSL2):

| what | median |
|---|---|
| bare `python -c pass` | ~9 ms |
| stdlib only | ~15 ms |
| FastAPI shim `/ping` | ~220 ms |

Most of the gap vs bare Python is import + wiring cost inside each CLI process.
