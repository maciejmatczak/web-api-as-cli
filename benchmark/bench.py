#!/usr/bin/env python3
"""
Benchmark: FastAPI-as-CLI overhead analysis
============================================

Measures four conceptually distinct cost buckets:

  1. subprocess cold-start  – what the user actually waits for
                              (Python launch + all imports + app init + request)
  2. import cost            – time to `import fastapi` and friends in-process
  3. app + client init      – FastAPI() + TestClient() construction after imports
  4. per-request latency    – a single GET once everything is warm

Each bucket is sampled N times and reported as min / mean / median / p95 / max.

Baseline comparisons
--------------------
  * bare Python subprocess  (python -c "pass")  → interpreter + OS overhead only
  * stdlib-only subprocess  (no FastAPI at all) → shows import cost in isolation

Run
---
  # from the repo root:
  python benchmark/bench.py
  python benchmark/bench.py --solution-dir fastapi-testclient --runs 30 --warmup 5

Each solution directory must contain a uv-managed .venv with the required deps.
The benchmark locates <solution-dir>/.venv/bin/python automatically.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Repo-relative paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOLUTION = "fastapi-testclient"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


def ms(seconds: float) -> str:
    return f"{seconds * 1000:.2f} ms"


def color_ms(seconds: float, *, warn: float = 0.1, bad: float = 0.5) -> str:
    """Color-code a duration relative to warn/bad thresholds (in seconds)."""
    raw = ms(seconds)
    if seconds >= bad:
        return f"{RED}{raw}{RESET}"
    if seconds >= warn:
        return f"{YELLOW}{raw}{RESET}"
    return f"{GREEN}{raw}{RESET}"


@dataclass
class Sample:
    label: str
    times: list[float] = field(default_factory=list)

    def record(self, t: float) -> None:
        self.times.append(t)

    # statistics (seconds)
    @property
    def n(self) -> int:
        return len(self.times)

    @property
    def minimum(self) -> float:
        return min(self.times)

    @property
    def mean(self) -> float:
        return statistics.mean(self.times)

    @property
    def median(self) -> float:
        return statistics.median(self.times)

    @property
    def p95(self) -> float:
        sorted_t = sorted(self.times)
        idx = max(0, int(len(sorted_t) * 0.95) - 1)
        return sorted_t[idx]

    @property
    def maximum(self) -> float:
        return max(self.times)

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.times) if self.n > 1 else 0.0


def _time(fn: Callable[[], object]) -> float:
    """Return wall-clock seconds for a single call of fn()."""
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def _measure(label: str, fn: Callable[[], object], runs: int, warmup: int) -> Sample:
    sample = Sample(label)
    for _ in range(warmup):
        fn()
    for _ in range(runs):
        sample.record(_time(fn))
    return sample


# ---------------------------------------------------------------------------
# Benchmark definitions
# ---------------------------------------------------------------------------

def bench_subprocess(
    cmd: list[str],
    runs: int,
    warmup: int,
    label: str,
    cwd: Path | None = None,
) -> Sample:
    """Time a full subprocess invocation (cold-start per call)."""
    def run():
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            cwd=cwd,
        )
        if result.returncode not in (0, 1):
            # exit-code 1 is acceptable (e.g. HTTP 4xx from CLI)
            raise RuntimeError(
                f"Subprocess failed (rc={result.returncode}):\n"
                + result.stderr.decode(errors="replace")
            )

    return _measure(label, run, runs=runs, warmup=warmup)


def bench_import(runs: int, warmup: int) -> Sample:
    """In-process: time to import fastapi and starlette from a cold sys.modules."""

    def run():
        # Remove cached modules to simulate a fresh import each time.
        to_remove = [k for k in sys.modules if k.startswith(("fastapi", "starlette", "anyio"))]
        for k in to_remove:
            del sys.modules[k]
        import fastapi  # noqa: F401  (we want the side-effect timing)
        from fastapi.testclient import TestClient  # noqa: F401

    return _measure("import fastapi + TestClient (in-process)", run, runs=runs, warmup=warmup)


def bench_app_init(runs: int, warmup: int) -> Sample:
    """In-process: FastAPI() construction (imports already cached)."""
    import fastapi  # ensure already imported

    def run():
        fastapi.FastAPI()

    return _measure("FastAPI() construction (imports warm)", run, runs=runs, warmup=warmup)


def bench_client_init(runs: int, warmup: int) -> Sample:
    """In-process: TestClient() construction around a minimal app."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    def run():
        _app = FastAPI()

        @_app.get("/ping")
        def _ping():
            return {}

        TestClient(_app)

    return _measure(
        "FastAPI() + @route + TestClient() (imports warm)",
        run,
        runs=runs,
        warmup=warmup,
    )


def bench_per_request(runs: int, warmup: int) -> Sample:
    """In-process: single GET once app + client are fully warm."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _app = FastAPI()

    @_app.get("/calculate")
    def calculate(x: float, y: float, op: str = "add"):
        ops = {"add": x + y, "sub": x - y, "mul": x * y}
        return {"result": ops.get(op, 0)}

    client = TestClient(_app)
    # one dummy request so the ASGI lifespan is already running
    client.get("/calculate", params={"x": 1, "y": 1})

    def run():
        client.get("/calculate", params={"x": 10, "y": 3, "op": "add"})

    return _measure("single GET (app + client fully warm)", run, runs=runs, warmup=warmup)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

COL_WIDTHS = (46, 11, 11, 11, 11, 11, 11)

def _row(*cells: str) -> str:
    return "  ".join(c.ljust(w) for c, w in zip(cells, COL_WIDTHS))


def _hline() -> str:
    return "-" * (sum(COL_WIDTHS) + 2 * (len(COL_WIDTHS) - 1))


def print_report(samples: list[Sample]) -> None:
    header = _row("benchmark", "n", "min", "mean", "median", "p95", "max")
    print()
    print(BOLD + _hline() + RESET)
    print(BOLD + header + RESET)
    print(BOLD + _hline() + RESET)

    for s in samples:
        row = _row(
            s.label,
            str(s.n),
            color_ms(s.minimum),
            color_ms(s.mean),
            color_ms(s.median),
            color_ms(s.p95),
            color_ms(s.maximum),
        )
        print(row)

    print(_hline())
    print(f"  Threshold legend:  {GREEN}green < 100 ms{RESET}  "
          f"{YELLOW}yellow < 500 ms{RESET}  {RED}red ≥ 500 ms{RESET}")
    print()


def print_overhead_breakdown(samples_by_key: dict[str, Sample]) -> None:
    """Show a cumulative overhead waterfall for the in-process path."""
    keys = ["import", "app_init", "client_init", "per_request"]
    labels = {
        "import":       "  imports only",
        "app_init":     "+ app construction",
        "client_init":  "+ TestClient construction",
        "per_request":  "  per-request (warm)",
    }
    print(BOLD + "  Overhead waterfall (in-process medians)" + RESET)
    print("  " + "-" * 50)
    cumulative = 0.0
    for k in keys:
        s = samples_by_key.get(k)
        if s is None:
            continue
        if k != "per_request":
            cumulative += s.median
            print(f"  {labels[k]:<32} {color_ms(s.median):>16}   cumulative: {color_ms(cumulative)}")
        else:
            print(f"  {labels[k]:<32} {color_ms(s.median):>16}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _resolve_solution(solution_dir: str) -> tuple[Path, Path]:
    """
    Return (solution_path, venv_python) for the given solution directory name
    (relative to repo root) or an absolute path.
    """
    sol = Path(solution_dir)
    if not sol.is_absolute():
        sol = REPO_ROOT / sol
    sol = sol.resolve()

    if not sol.is_dir():
        print(f"ERROR: solution directory not found: {sol}", file=sys.stderr)
        sys.exit(1)

    venv_python = sol / ".venv" / "bin" / "python"
    if not venv_python.exists():
        print(
            f"ERROR: no .venv found in {sol}\n"
            f"Run: cd {sol} && uv sync",
            file=sys.stderr,
        )
        sys.exit(1)

    return sol, venv_python


def _inject_solution_site_packages(venv_python: Path) -> None:
    """Add the solution venv's site-packages to sys.path for in-process imports."""
    try:
        site_pkgs = subprocess.check_output(
            [str(venv_python), "-c",
             "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True,
        ).strip()
    except subprocess.CalledProcessError as e:
        print(f"WARNING: could not determine site-packages: {e}", file=sys.stderr)
        return
    if site_pkgs not in sys.path:
        sys.path.insert(0, site_pkgs)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--solution-dir",
        default=DEFAULT_SOLUTION,
        metavar="DIR",
        help=f"solution directory containing a uv .venv (default: {DEFAULT_SOLUTION})",
    )
    p.add_argument("--runs",   type=int, default=20, help="measurement repetitions (default: 20)")
    p.add_argument("--warmup", type=int, default=3,  help="throw-away warmup runs (default: 3)")
    p.add_argument(
        "--no-subprocess",
        action="store_true",
        help="skip subprocess benchmarks (faster, skips cold-start measurement)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sol_dir, sol_python = _resolve_solution(args.solution_dir)

    # Make solution's packages available for in-process benchmarks.
    _inject_solution_site_packages(sol_python)
    # Make solution's source importable (fastapi_cli package lives here).
    if str(sol_dir) not in sys.path:
        sys.path.insert(0, str(sol_dir))

    print(textwrap.dedent(f"""
    {BOLD}{CYAN}FastAPI-as-CLI overhead benchmark{RESET}
    solution  = {sol_dir.name}
    runs={args.runs}  warmup={args.warmup}  Python={sys.version.split()[0]}
    """))

    samples: list[Sample] = []
    samples_by_key: dict[str, Sample] = {}

    # -- subprocess baselines ------------------------------------------------
    if not args.no_subprocess:
        print("  Measuring subprocess cold-starts (this takes a moment)…")

        s = bench_subprocess(
            [str(sol_python), "-c", "pass"],
            runs=args.runs,
            warmup=args.warmup,
            label="subprocess: python -c pass  (baseline)",
            cwd=sol_dir,
        )
        samples.append(s)

        s = bench_subprocess(
            [str(sol_python), "-c",
             "import json, sys; print(json.dumps({'result': 1+2}))"],
            runs=args.runs,
            warmup=args.warmup,
            label="subprocess: stdlib only  (no FastAPI)",
            cwd=sol_dir,
        )
        samples.append(s)

        s = bench_subprocess(
            [str(sol_python), "-m", "fastapi_cli.cli", "/ping"],
            runs=args.runs,
            warmup=args.warmup,
            label=f"subprocess: {sol_dir.name} /ping  (full shim)",
            cwd=sol_dir,
        )
        samples.append(s)

        s = bench_subprocess(
            [str(sol_python), "-m", "fastapi_cli.cli",
             "/calculate", "x=10", "y=3", "op=add"],
            runs=args.runs,
            warmup=args.warmup,
            label=f"subprocess: {sol_dir.name} /calculate x=10 y=3",
            cwd=sol_dir,
        )
        samples.append(s)

    # -- in-process breakdown ------------------------------------------------
    print("  Measuring in-process overhead breakdown…")

    s = bench_import(runs=args.runs, warmup=args.warmup)
    samples.append(s)
    samples_by_key["import"] = s

    s = bench_app_init(runs=args.runs, warmup=args.warmup)
    samples.append(s)
    samples_by_key["app_init"] = s

    s = bench_client_init(runs=args.runs, warmup=args.warmup)
    samples.append(s)
    samples_by_key["client_init"] = s

    s = bench_per_request(runs=args.runs, warmup=args.warmup)
    samples.append(s)
    samples_by_key["per_request"] = s

    # -- report --------------------------------------------------------------
    print_report(samples)
    print_overhead_breakdown(samples_by_key)

    # -- key insight ---------------------------------------------------------
    if not args.no_subprocess:
        baseline = samples[0].median      # python -c pass
        full_shim = samples[2].median     # full CLI shim /ping
        net_overhead = full_shim - baseline
        print(f"  {BOLD}Net FastAPI shim overhead vs bare Python:{RESET} {color_ms(net_overhead)}")
        print(f"  (subprocess full-shim median minus bare-python median)")
        print()


if __name__ == "__main__":
    main()
