#!/usr/bin/env python3
"""
Benchmark: web-API-as-CLI cold-start comparison
=============================================

Measures subprocess cold-start time for each solution (what a user waits for on each
CLI invocation): Python startup, imports, app wiring, and one request.

Baselines (same interpreter as this script):

  * ``python -c pass`` — interpreter + OS overhead only
  * stdlib-only subprocess — minimal work without third-party deps

Each solution row uses that solution's ``.venv`` Python so dependency graphs match
real usage.

Run
---
  # from the repo root:
  python benchmark/bench.py
  python benchmark/bench.py --runs 30 --warmup 5
  python benchmark/bench.py --solution fastapi-testclient

Solutions without ``<name>/.venv`` are skipped with a warning (run ``uv sync`` there).
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

# Subprocess argv fragments after ``python`` (module mode ``-m ...``).
SOLUTION_COMMANDS: list[dict[str, str | list[str]]] = [
    {
        "name": "fastapi-testclient",
        "ping": ["-m", "fastapi_cli.cli", "/ping"],
        "calculate": ["-m", "fastapi_cli.cli", "/calculate", "x=10", "y=3", "op=add"],
    },
    {
        "name": "cyclopts",
        "ping": ["-m", "cyclopts_cli", "ping"],
        "calculate": ["-m", "cyclopts_cli", "calculate", "10", "3"],
    },
    {
        "name": "falcon",
        "ping": ["-m", "falcon_cli.cli", "/ping"],
        "calculate": ["-m", "falcon_cli.cli", "GET", "/calculate", "x=10", "y=3"],
    },
    {
        "name": "robyn",
        "ping": ["-m", "robyn_cli.cli", "/ping"],
        "calculate": ["-m", "robyn_cli.cli", "GET", "/calculate", "x=10", "y=3"],
    },
    {
        "name": "starlette",
        "ping": ["-m", "starlette_cli.cli", "GET", "/ping"],
        "calculate": ["-m", "starlette_cli.cli", "GET", "/calculate", "x=10", "y=3"],
    },
]


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
    print(
        f"  Threshold legend:  {GREEN}green < 100 ms{RESET}  "
        f"{YELLOW}yellow < 500 ms{RESET}  {RED}red ≥ 500 ms{RESET}"
    )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _venv_python(solution_name: str) -> Path | None:
    """Return path to solution venv Python, or None if missing."""
    sol = REPO_ROOT / solution_name
    py = sol / ".venv" / "bin" / "python"
    if py.is_file():
        return py
    print(
        f"WARNING: skipping {solution_name}: no .venv at {sol}\n"
        f"         Run: cd {sol} && uv sync",
        file=sys.stderr,
    )
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--runs", type=int, default=20, help="measurement repetitions (default: 20)")
    p.add_argument("--warmup", type=int, default=3, help="throw-away warmup runs (default: 3)")
    p.add_argument(
        "--solution",
        metavar="NAME",
        default=None,
        help="run only this solution directory name (e.g. starlette)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    known = {str(s["name"]) for s in SOLUTION_COMMANDS}
    if args.solution is not None and args.solution not in known:
        print(
            f"ERROR: unknown solution {args.solution!r}. Choose one of: {sorted(known)}",
            file=sys.stderr,
        )
        sys.exit(1)

    solutions = (
        [s for s in SOLUTION_COMMANDS if s["name"] == args.solution]
        if args.solution
        else list(SOLUTION_COMMANDS)
    )

    bench_py = sys.executable

    print(
        textwrap.dedent(
            f"""
    {BOLD}{CYAN}Web-API-as-CLI cold-start benchmark{RESET}
    runs={args.runs}  warmup={args.warmup}  baseline_python={bench_py}
    solutions={", ".join(str(s["name"]) for s in solutions)}
    """
        )
    )

    samples: list[Sample] = []
    ping_samples: list[Sample] = []

    print("  Measuring baselines and subprocess cold-starts…")

    s = bench_subprocess(
        [bench_py, "-c", "pass"],
        runs=args.runs,
        warmup=args.warmup,
        label="subprocess: python -c pass  (baseline)",
        cwd=REPO_ROOT,
    )
    samples.append(s)

    s = bench_subprocess(
        [
            bench_py,
            "-c",
            "import json, sys; print(json.dumps({'result': 1+2}))",
        ],
        runs=args.runs,
        warmup=args.warmup,
        label="subprocess: stdlib only  (no framework)",
        cwd=REPO_ROOT,
    )
    samples.append(s)

    for sol in solutions:
        name = str(sol["name"])
        vpy = _venv_python(name)
        if vpy is None:
            continue
        sol_dir = REPO_ROOT / name
        ping_args = sol["ping"]
        calc_args = sol["calculate"]
        assert isinstance(ping_args, list)
        assert isinstance(calc_args, list)

        s_ping = bench_subprocess(
            [str(vpy), *ping_args],
            runs=args.runs,
            warmup=args.warmup,
            label=f"{name}  ping",
            cwd=sol_dir,
        )
        samples.append(s_ping)
        ping_samples.append(s_ping)

        s_calc = bench_subprocess(
            [str(vpy), *calc_args],
            runs=args.runs,
            warmup=args.warmup,
            label=f"{name}  calculate",
            cwd=sol_dir,
        )
        samples.append(s_calc)

    print_report(samples)

    if ping_samples:
        fastest = min(ping_samples, key=lambda x: x.median)
        slowest = max(ping_samples, key=lambda x: x.median)
        spread = slowest.median - fastest.median
        print(f"  {BOLD}Ping cold-start (median): fastest{RESET} {fastest.label} "
              f"({color_ms(fastest.median)})  {BOLD}slowest{RESET} {slowest.label} "
              f"({color_ms(slowest.median)})  {BOLD}spread{RESET} {color_ms(spread)}")
        print()


if __name__ == "__main__":
    main()
