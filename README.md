# rnd-web-api-as-cli

Exploring whether a web API framework can double as a local CLI runtime — with zero network overhead.

The core idea: instead of spinning up a real HTTP server, wire a CLI shim directly to the
ASGI/WSGI application object via an in-process test client. The framework handles routing,
validation, and serialisation; the shim translates `argv` into a request and prints the
response. If the overhead is acceptable, you get OpenAPI docs, type-safe handlers, and a
real HTTP API for free, while users interact with it as a plain command.

## Solutions

Each subdirectory is a self-contained experiment with its own `uv`-managed virtual
environment. Add new alternatives alongside the existing ones; the benchmark can target any
of them via `--solution-dir`.

### `fastapi-testclient/`

Uses [FastAPI](https://fastapi.tiangolo.com/) as the routing and validation layer, accessed
through Starlette's `TestClient` (backed by `httpx`). No socket is opened — the ASGI app
is called in-process. FastAPI's automatic query-parameter coercion and Pydantic validation
are available to every route with no extra code.

## Benchmark

`benchmark/bench.py` measures four cost buckets: subprocess cold-start (what the user
actually waits for), import time, app + client construction, and per-request latency once
everything is warm. It also runs a bare-Python and stdlib-only baseline so the net
framework overhead is isolated.

```
# from the repo root
uv run --project fastapi-testclient python benchmark/bench.py

# point at a different solution or tune the run count
python benchmark/bench.py --solution-dir fastapi-testclient --runs 30 --warmup 5
```

Results on this machine (Python 3.12, WSL2):

| what | median |
|---|---|
| bare `python -c pass` | ~9 ms |
| stdlib only (no FastAPI) | ~15 ms |
| full FastAPI shim `/ping` | ~218 ms |
| **net framework overhead** | **~210 ms** |

The cost is dominated by importing FastAPI and its dependencies (pydantic-core, anyio,
starlette). Once warm, app construction is < 0.1 ms and a single request is ~1.7 ms.
