"""
Robyn app exposing the calculator domain logic.

Robyn is not a native ASGI application; see ``asgi_bridge`` for the
``httpx.ASGITransport`` surface used by the CLI.
"""

import dataclasses
import json
import logging

from robyn import Response, Robyn

from robyn_cli.asgi_bridge import robyn_to_asgi

logging.getLogger("robyn").setLevel(logging.WARNING)

app = Robyn(__file__)


@dataclasses.dataclass
class PingResponse:
    status: str = "ok"


@dataclasses.dataclass
class CalculateResponse:
    op: str
    x: float
    y: float
    result: float


@dataclasses.dataclass
class ErrorResponse:
    detail: str

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@app.get("/ping")
def ping():
    return dataclasses.asdict(PingResponse())


@app.get("/calculate")
def calculate(x: float, y: float, op: str = "add"):
    ops: dict[str, float | None] = {
        "add": x + y,
        "sub": x - y,
        "mul": x * y,
        "div": None,
    }
    if op not in ops:
        return Response(
            status_code=400,
            headers={},
            description=ErrorResponse(f"Unknown op '{op}'").to_json(),
        )
    if op == "div" and y == 0:
        return Response(
            status_code=422,
            headers={},
            description=ErrorResponse("Division by zero").to_json(),
        )
    result = x / y if op == "div" else ops[op]
    assert result is not None
    return dataclasses.asdict(
        CalculateResponse(op=op, x=x, y=y, result=float(result))
    )


# Callable ASGI3 app for httpx.ASGITransport (wraps Robyn via TestClient).
asgi_app = robyn_to_asgi(app)
