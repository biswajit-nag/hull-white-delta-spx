"""Runtime log: one row per timed run of a pipeline step, fit, bootstrap or tuning study.

Usage, in a script or notebook:

    from erdos_quant_finance_project.runlog import timed

    with timed("iv_greeks", inputs="spx 2019-2020") as run:
        ...
        run["rows_out"] = len(panel)

The row is appended to results/runtime_log.csv when the block exits, with status "failed" if it
raised. Peak memory is the process's peak working set (Windows) or peak RSS, read with psutil when
it is installed; otherwise the column is left empty.
"""

from __future__ import annotations

import contextlib
import csv
import datetime as dt
import platform
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "results" / "runtime_log.csv"
FIELDS = ["started_at", "step", "status", "wall_seconds", "peak_mem_gb", "rows_in", "rows_out", "inputs",
          "git_hash", "git_dirty", "python", "machine", "notes"]


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _peak_mem_gb() -> str:
    try:
        import psutil
    except ImportError:
        return ""
    info = psutil.Process().memory_info()
    peak = getattr(info, "peak_wset", None) or getattr(info, "rss", 0)
    return f"{peak / 1024 ** 3:.2f}"


@contextlib.contextmanager
def timed(step: str, *, inputs: str = "", rows_in: int | None = None, notes: str = "",
          log: Path = LOG) -> Iterator[dict]:
    """Time the enclosed block and append one row to the runtime log.

    The yielded dict may be filled in by the caller: rows_in, rows_out, notes.
    """
    run = {"rows_in": rows_in, "rows_out": None, "notes": notes}
    started = dt.datetime.now().astimezone()
    t0 = time.perf_counter()
    status = "failed"
    try:
        yield run
        status = "ok"
    finally:
        row = {
            "started_at": started.isoformat(timespec="seconds"),
            "step": step,
            "status": status,
            "wall_seconds": f"{time.perf_counter() - t0:.1f}",
            "peak_mem_gb": _peak_mem_gb(),
            "rows_in": "" if run["rows_in"] is None else run["rows_in"],
            "rows_out": "" if run["rows_out"] is None else run["rows_out"],
            "inputs": inputs,
            "git_hash": _git("rev-parse", "--short", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
            "python": platform.python_version(),
            "machine": platform.platform(terse=True),
            "notes": run["notes"],
        }
        new = not log.exists()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
