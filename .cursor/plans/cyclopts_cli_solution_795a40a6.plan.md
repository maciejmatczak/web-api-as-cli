---
name: cyclopts CLI solution
overview: Create a `cyclopts/` solution directory with a pure-CLI `cyclopts_cli` package implementing ping and calculate with stdlib dataclass response models.
todos:
  - id: create-pyproject
    content: Create cyclopts/pyproject.toml with cyclopts dependency
    status: pending
  - id: create-init
    content: Create cyclopts/cyclopts_cli/__init__.py (empty package marker)
    status: pending
  - id: create-main
    content: Create cyclopts/cyclopts_cli/__main__.py with ping + calculate commands
    status: pending
isProject: false
---

# cyclopts CLI Solution Plan

## What needs building

### New solution: `cyclopts/`

Mirror the layout of `fastapi-testclient/`:

```
cyclopts/
├── pyproject.toml
└── cyclopts_cli/
    ├── __init__.py        (empty — makes it a package)
    └── __main__.py        (entry point; `python -m cyclopts_cli` invokes this)
```

**[`cyclopts/pyproject.toml`](cyclopts/pyproject.toml)**
```toml
[project]
name = "cyclopts-cli"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["cyclopts>=3"]
```

**[`cyclopts/cyclopts_cli/__main__.py`](cyclopts/cyclopts_cli/__main__.py)**

Response models use **stdlib `dataclasses`** with `slots=True` (Python 3.10+, project requires 3.12).
This gives a centralized, typed response contract at zero import cost — Pydantic would add cold-start
overhead that undermines the benchmark's purpose.

```python
import json, sys
from dataclasses import dataclass, asdict
import cyclopts

# --- Centralized response models -------------------------------------------

@dataclass(slots=True)
class PingResponse:
    status: str = "ok"

@dataclass(slots=True)
class CalculateResponse:
    op: str
    x: float
    y: float
    result: float

@dataclass(slots=True)
class ErrorResponse:
    error: str

# --- CLI app ----------------------------------------------------------------

app = cyclopts.App(add_completion=False)

@app.command
def ping() -> PingResponse:
    return PingResponse()

@app.command
def calculate(x: float, y: float, *, op: str = "add") -> CalculateResponse:
    ops = {"add": x + y, "sub": x - y, "mul": x * y}
    if op == "div":
        if y == 0:
            raise ValueError("Division by zero")
        return CalculateResponse(op=op, x=x, y=y, result=x / y)
    if op not in ops:
        raise ValueError(f"Unknown op '{op}'. Choose from: add, sub, mul, div")
    return CalculateResponse(op=op, x=x, y=y, result=ops[op])

# --- Top-level dispatcher ---------------------------------------------------

if __name__ == "__main__":
    try:
        result = app()                       # cyclopts returns the handler's dataclass
        print(json.dumps(asdict(result)))    # single serialization point
        sys.exit(0)
    except SystemExit as e:
        sys.exit(e.code)                     # --help / arg validation exits untouched
    except Exception as e:
        print(json.dumps(asdict(ErrorResponse(error=str(e)))))
        sys.exit(1)
```

Key properties:
- **Centralized response contract**: every possible output shape is declared once as a dataclass; adding a new command means adding a new `*Response` class
- **`slots=True`**: faster attribute access, slightly lower memory — measurable at the scale this benchmark cares about
- **`asdict()`** is stdlib, no third-party serializer import; the single call site in the dispatcher is the only place JSON is emitted
- `SystemExit` re-raised as-is: cyclopts `--help` and argument validation print to stderr and exit without touching stdout
- Response shapes match the TODO contract (`{"status":"ok"}` / `{"op":…,"x":…,"y":…,"result":…}`)


## After implementation

Run `uv sync` inside `cyclopts/` to create the `.venv`, then verify manually:
```bash
cyclopts/.venv/bin/python -m cyclopts_cli ping
cyclopts/.venv/bin/python -m cyclopts_cli calculate 10 3 --op add
cyclopts/.venv/bin/python -m cyclopts_cli calculate 10 0 --op div
```
