"""
Falcon ASGI app exposing ping and calculate with inline dataclass response models.
"""

from __future__ import annotations

import dataclasses

import falcon.asgi


@dataclasses.dataclass
class PingResponse:
    status: str


@dataclasses.dataclass
class CalculateResponse:
    op: str
    x: float
    y: float
    result: float


class PingResource:
    async def on_get(self, req: falcon.asgi.Request, resp: falcon.asgi.Response) -> None:
        resp.media = dataclasses.asdict(PingResponse(status="ok"))


class CalculateResource:
    async def on_get(self, req: falcon.asgi.Request, resp: falcon.asgi.Response) -> None:
        try:
            x = float(req.get_param("x", required=True))
            y = float(req.get_param("y", required=True))
        except (TypeError, ValueError) as e:
            raise falcon.HTTPBadRequest(description=str(e))
        op = req.get_param("op") or "add"
        if op == "div" and y == 0:
            raise falcon.HTTPUnprocessableEntity(description="Division by zero")
        ops = {"add": x + y, "sub": x - y, "mul": x * y, "div": x / y}
        if op not in ops:
            raise falcon.HTTPBadRequest(description=f"Unknown op '{op}'")
        resp.media = dataclasses.asdict(
            CalculateResponse(op=op, x=x, y=y, result=ops[op])
        )


def create_app() -> falcon.asgi.App:
    app = falcon.asgi.App()
    app.add_route("/ping", PingResource())
    app.add_route("/calculate", CalculateResource())
    return app


app = create_app()
