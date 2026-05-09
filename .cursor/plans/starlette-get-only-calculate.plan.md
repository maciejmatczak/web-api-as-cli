<!-- dff5240b-8a73-4703-8f7c-05863f9b0797 -->
---
todos:
  - id: "app-get-only"
    content: "Restrict Route /calculate to GET only; remove JSON body branch and _CALC_METHODS from starlette_cli/app.py"
    status: pending
  - id: "cli-docstring"
    content: "Update starlette_cli/cli.py module docstring to GET-only examples"
    status: pending
  - id: "readme-starlette"
    content: "Update README: Starlette routes/examples + HTTP-method note + explicit shared web-verb methodology across all HTTP solutions"
    status: pending
isProject: true
---
# Starlette: GET-only `/calculate`

## Shared methodology (all web implementations)

**Principle:** Every **HTTP-layer** solution in this repo ([`fastapi-testclient/`](fastapi-testclient/), [`falcon/`](falcon/), [`robyn/`](robyn/), [`starlette/`](starlette/)) should follow the **same HTTP verb policy** for the demo API surface:

- **`/ping`:** exposed as **`GET`** (and **`HEAD`** where the app already defines it, e.g. Starlette/FastAPI-style health checks).
- **`/calculate`:** exposed as **`GET` only**, with **`x`**, **`y`**, and optional **`op`** as **query parameters** — no POST/PUT/PATCH JSON body path for this resource in any mounted app.

**CLI shims** may still accept a leading `METHOD` token and map verbs to query vs JSON body (generic transport); that does not change the rule above: **the mounted routes for `/calculate` must not accept non-GET methods** for the calculator operation.

**Current gap:** Starlette is the outlier (multi-method route + JSON body parsing). FastAPI, Falcon, and Robyn already match this methodology at the app layer; this work **closes Starlette** and **documents the single policy** in the README so readers do not infer framework-specific verb matrices for `/calculate`.

## Goal

Align [`starlette/starlette_cli/app.py`](starlette/starlette_cli/app.py) with that shared policy: **`/calculate` is only `GET` with query parameters**. Remove the JSON-body code path and the extra verbs on that route.

## Code changes

### 1. App: route and parsing ([`starlette/starlette_cli/app.py`](starlette/starlette_cli/app.py))

- Change the `/calculate` route from `methods=list(_CALC_METHODS)` to **`methods=["GET"]`** only (drop `_CALC_METHODS` constant entirely).
- Simplify `_parse_calculate_inputs` (or fold into `calculate`):
  - **Remove** the branch that calls `await request.json()` and parses `x`/`y`/`op` from a JSON body (lines 50–67 today).
  - **Keep** query-parameter parsing only (today’s `GET`-style path using `request.query_params`).
  - Remove the `request.method in ("GET", "HEAD", "DELETE")` split; with GET-only registration, only GET hits this handler (no need to treat DELETE as query-driven for this resource).
- Leave **`/ping`** as-is: `Route("/ping", ping, methods=["GET", "HEAD"])` is unchanged and unrelated to the calculate alignment.

### 2. CLI ([`starlette/starlette_cli/cli.py`](starlette/starlette_cli/cli.py))

- **Behavior**: No functional change required for parity with Falcon/Robyn — the shim can still parse optional `METHOD` and send POST/JSON, but **`POST /calculate` will correctly receive 405** once the route is GET-only (same pattern as Falcon’s CLI vs `on_get`-only resource).
- **Docs**: Update the module docstring (lines 7–10) to **remove POST example** and show only GET-style invocations, mirroring [`falcon/falcon_cli/cli.py`](falcon/falcon_cli/cli.py) / [`robyn/robyn_cli/cli.py`](robyn/robyn_cli/cli.py).

## Documentation

### 3. README ([`README.md`](README.md))

- **Starlette section** (implemented routes + CLI examples): Replace the long “`GET`, `HEAD`, `DELETE`, `POST`, … on `/calculate`” bullet with **`GET /calculate?x=&y=&op=`** (and keep `GET`, `HEAD` on `/ping` if still accurate).
- Drop POST/PATCH CLI examples for Starlette; use **only GET** lines, consistent with Falcon/Robyn blocks.
- **“HTTP method handling in CLI shims”** (lines ~99–109): Reword so it reflects **one methodology for mounted apps**: shims may support multiple method tokens for **transport**, but **this repo’s web apps all expose `/calculate` as GET-only**; remove any wording that singles out Starlette as having a broader verb set on `/calculate`.
- **Cross-solution clarity:** In **Common contract** (or a short sentence under **Implemented solutions**), state explicitly that **all HTTP implementations use the same verb pattern** for `/ping` and `/calculate` (GET query-driven calculator; no POST body on `/calculate` in the apps), so the domain contract and the **HTTP surface** stay aligned across FastAPI, Falcon, Robyn, and Starlette.

## Verification

- Manually (or a one-off script): `uv run` from [`starlette/pyproject.toml`](starlette/pyproject.toml) project root — `GET /calculate` succeeds; **`POST /calculate`** returns **405** (or framework-consistent non-success) and does not run calculate logic.
- Optional: grep the repo for `POST /calculate` / `PATCH /calculate` under `starlette` or README to ensure no stale references.

## Out of scope

- Changing Falcon/Robyn CLI generic method handling.
- Adding automated tests (none exist under `starlette/` today); only add if you want regression coverage as a follow-up.
