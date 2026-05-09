"""Pure cyclopts CLI: ping and calculate with centralized dataclass responses."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass

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

# cyclopts v4 removed add_completion; completion is opt-in / not auto-run on import.
# Default result_action prints non-int returns — use return_value so we emit JSON only once.
app = cyclopts.App(result_action="return_value")


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
        result = app()
        print(json.dumps(asdict(result)))
        sys.exit(0)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        print(json.dumps(asdict(ErrorResponse(error=str(e)))))
        sys.exit(1)
