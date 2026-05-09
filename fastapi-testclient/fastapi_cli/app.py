"""
FastAPI app exposing the calculator domain logic.

Keeping the app definition separate from the CLI shim means the same routes
can be unit-tested or served over HTTP without touching the CLI layer.
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="calc", version="0.1.0")


@app.get("/calculate")
def calculate(x: float, y: float, op: str = "add"):
    """Perform a binary arithmetic operation on two numbers."""
    ops = {
        "add": x + y,
        "sub": x - y,
        "mul": x * y,
        "div": x / y if y != 0 else None,
    }
    if op not in ops:
        raise HTTPException(status_code=400, detail=f"Unknown op '{op}'. Choose from: {list(ops)}")
    result = ops[op]
    if result is None:
        raise HTTPException(status_code=422, detail="Division by zero")
    return {"op": op, "x": x, "y": y, "result": result}


@app.get("/ping")
def ping():
    """Minimal no-op endpoint – useful for measuring pure framework overhead."""
    return {"status": "ok"}
