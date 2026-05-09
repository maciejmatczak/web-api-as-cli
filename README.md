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

Sample run on one machine (WSL2, `python3 benchmark/bench.py --runs 30 --warmup 5`, each solution’s own `.venv`):

| benchmark | min | mean | median | p95 | max |
|---|---:|---:|---:|---:|---:|
| `python -c pass` (baseline) | 12.28 ms | 12.81 ms | 12.79 ms | 13.20 ms | 13.26 ms |
| stdlib only (no framework) | 15.02 ms | 15.80 ms | 15.58 ms | 17.29 ms | 17.45 ms |
| fastapi-testclient ping | 216.30 ms | 220.54 ms | 219.94 ms | 225.26 ms | 227.23 ms |
| fastapi-testclient calculate | 221.34 ms | 227.43 ms | 226.90 ms | 234.17 ms | 242.22 ms |
| cyclopts ping | 56.49 ms | 58.79 ms | 58.70 ms | 60.98 ms | 62.62 ms |
| cyclopts calculate | 57.70 ms | 59.67 ms | 59.39 ms | 61.29 ms | 63.81 ms |
| falcon ping | 85.94 ms | 88.81 ms | 88.44 ms | 91.51 ms | 94.14 ms |
| falcon calculate | 86.01 ms | 88.35 ms | 88.05 ms | 91.43 ms | 95.58 ms |
| robyn ping | 92.41 ms | 94.46 ms | 94.46 ms | 95.90 ms | 97.69 ms |
| robyn calculate | 91.88 ms | 94.77 ms | 94.56 ms | 96.76 ms | 99.33 ms |
| starlette ping | 87.08 ms | 89.19 ms | 89.03 ms | 91.11 ms | 92.06 ms |
| starlette calculate | 85.72 ms | 88.79 ms | 88.91 ms | 90.91 ms | 92.52 ms |

**Ping cold-start (median):** fastest cyclopts (58.70 ms), slowest fastapi-testclient (219.94 ms), spread 161.24 ms.

Most of the gap vs bare Python for the web-style shims is import and framework wiring inside each cold subprocess.
