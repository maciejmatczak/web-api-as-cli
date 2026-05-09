---
name: "Starlette: GET-only `/calculate`"
overview: "Align starlette/starlette_cli/app.py with the shared GET-only policy for /calculate, and document the single verb methodology across all HTTP solutions."
todos:
  - id: "app-get-only"
    content: "Restrict Route /calculate to GET only; remove JSON body branch and _CALC_METHODS from starlette_cli/app.py"
    status: completed
  - id: "cli-docstring"
    content: "Update starlette_cli/cli.py module docstring to GET-only examples"
    status: completed
  - id: "readme-starlette"
    content: "Update README: Starlette routes/examples + HTTP-method note + explicit shared web-verb methodology across all HTTP solutions"
    status: completed
isProject: true
---
# Starlette: GET-only `/calculate`

> **All three tasks are complete.** The plan is kept as a record of the design decision.

## Shared methodology (all web implementations)

**Principle:** Every **HTTP-layer** solution in this repo ([`fastapi-testclient/`](fastapi-testclient/), [`falcon/`](falcon/), [`robyn/`](robyn/), [`starlette/`](starlette/)) follows the **same HTTP verb policy** for the demo API surface:

- **`/ping`:** exposed as **`GET`** (and **`HEAD`** where the app already defines it, e.g. Starlette/FastAPI-style health checks).
- **`/calculate`:** exposed as **`GET` only**, with **`x`**, **`y`**, and optional **`op`** as **query parameters** — no POST/PUT/PATCH JSON body path for this resource in any mounted app.

**CLI shims** may still accept a leading `METHOD` token and map verbs to query vs JSON body (generic transport); that does not change the rule above: **the mounted routes for `/calculate` must not accept non-GET methods** for the calculator operation.

## What was done

### 1. App: route and parsing ([`starlette/starlette_cli/app.py`](starlette/starlette_cli/app.py))

- `/calculate` route is registered as `Route("/calculate", calculate, methods=["GET"])` — GET-only, no `_CALC_METHODS` constant.
- Input parsing uses `_parse_calculate_query(request)` which reads `request.query_params` only (no `await request.json()` branch).
- `/ping` remains `Route("/ping", ping, methods=["GET", "HEAD"])`, unchanged.

### 2. CLI ([`starlette/starlette_cli/cli.py`](starlette/starlette_cli/cli.py))

- Module docstring shows only GET-style invocations:
  ```
  python -m starlette_cli.cli GET /ping
  python -m starlette_cli.cli GET /calculate x=10 y=3
  python -m starlette_cli.cli GET /calculate x=10 y=3 op=div
  ```
- The shim still supports other METHOD tokens (generic transport); `POST /calculate` receives **405** from the app.

### 3. README ([`README.md`](README.md))

- Starlette section lists `GET /calculate?x=&y=&op=` and GET-only CLI examples.
- "HTTP method handling in CLI shims" section explicitly states: *"The mounted apps all expose `/calculate` as `GET` only"* and that non-GET requests receive **405**.

## Verification

```bash
# from starlette/ project root
uv run python -m starlette_cli.cli GET /calculate x=10 y=3          # → 200
uv run python -m starlette_cli.cli POST /calculate x=10 y=3         # → 405
```

## Out of scope

- Changing Falcon/Robyn CLI generic method handling.
- Adding automated tests (none exist under `starlette/` today).
