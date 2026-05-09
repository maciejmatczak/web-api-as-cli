"""
Starlette app exposing the calculator domain logic (no Pydantic).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

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


def _bad_request(msg: str) -> JSONResponse:
    return JSONResponse(asdict(ErrorResponse(detail=msg)), status_code=400)


def _unprocessable(msg: str) -> JSONResponse:
    return JSONResponse(asdict(ErrorResponse(detail=msg)), status_code=422)


def _parse_calculate_query(request: Request) -> tuple[float, float, str] | JSONResponse:
    """Parse x, y, op from query parameters; return (x, y, op) or an error JSONResponse."""
    qp = request.query_params
    try:
        x = float(qp["x"])
        y = float(qp["y"])
    except KeyError:
        return _unprocessable("Missing required query parameters 'x' and/or 'y'.")
    except ValueError:
        return _unprocessable("Query parameters 'x' and 'y' must be valid floats.")
    op = qp.get("op", "add")
    return x, y, op


async def ping(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def calculate(request: Request) -> JSONResponse:
    parsed = _parse_calculate_query(request)
    if isinstance(parsed, JSONResponse):
        return parsed
    x, y, op = parsed

    known = ("add", "sub", "mul", "div")
    if op not in known:
        return _bad_request(
            f"Unknown op '{op}'. Choose from: {list(known)}",
        )

    if op == "div" and y == 0:
        return _unprocessable("Division by zero")

    if op == "add":
        result = x + y
    elif op == "sub":
        result = x - y
    elif op == "mul":
        result = x * y
    else:
        result = x / y

    return JSONResponse(
        asdict(CalculateResponse(op=op, x=x, y=y, result=result)),
    )


app = Starlette(
    routes=[
        Route("/ping", ping, methods=["GET", "HEAD"]),
        Route("/calculate", calculate, methods=["GET"]),
    ],
)
