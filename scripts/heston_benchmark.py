"""Timing benchmark, old calibration B against B2 (analysis_plan.md §16.5), run alone in one process.

The same sessions for both: every 25th session of 2019–2020, plus 2020-03-16. Old: the Lecture 12 library
pricer and §16.2's calibration B with its three starts (that session's L-iv solution and the previous
month's median B solution, both from results/heston/params.csv, and the lecture default). New: B2 from a
cold start (the data start and the lecture default, as on a year's first session). Wall-clock
(perf_counter) and CPU (process_time) per session, evaluations, cost and IV RMSE.
Writes results/heston2/benchmark.csv.

Usage: uv run python -I scripts/heston_benchmark.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import heston_calibrate as old  # noqa: E402
import heston2_calibrate as new  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402


def old_b(day: pd.Timestamp, prm: pd.DataFrame) -> dict:
    w0, c0 = time.perf_counter(), time.process_time()
    d = old.day_quotes(day)
    two = (d.bid > 0) & (d.ask >= d.bid)
    B = d[two & (d.tau * 365).between(14, 365) & ((d.volume > 0) | (d.volume.isna() & (d["last"] > 0)))
          & (((d.cp == "C") & (d.strike >= d.F)) | ((d.cp == "P") & (d.strike < d.F)))].copy()
    B["px"] = (B.bid + B.ask) / 2
    B["sgn"] = np.where(B.cp == "C", 1.0, -1.0)
    liv = prm[(prm.session == day) & (prm.fit == "L-iv")]
    prev = prm[(prm.fit == "B-iv") & prm.ok.fillna(False).astype(bool) & (prm.session.dt.to_period("M") == day.to_period("M") - 1)]
    starts = [old.X0] + ([liv[old.NAMES].iloc[0].to_numpy()] if len(liv) else []) + ([prev[old.NAMES].median().to_numpy()] if len(prev) else [])
    fits = [old.fit(B, "iv", x) for x in starts]
    best = min(fits, key=lambda r: r["cost"])
    return {"session": day, "method": "old B (library, 3 starts)", "n": best["n"], "starts": len(starts),
            "nfev_total": int(sum(f["nfev"] for f in fits)), "ok": best["ok"], "iv_rmse": best["iv_rmse"],
            **{k: best[k] for k in old.NAMES}, "wall_s": time.perf_counter() - w0, "cpu_s": time.process_time() - c0}


def main() -> None:
    days = []
    for y in (2019, 2020):
        days += pd.to_datetime(pd.read_parquet(new.GREEKS / f"sessions_{y}.parquet").quote_date).tolist()
    days = pd.DatetimeIndex(days).sort_values()
    pick = sorted(set(days[::25]) | {pd.Timestamp("2020-03-16")})
    prm = pd.read_csv(ROOT / "results/heston/params.csv", parse_dates=["session"])
    rows = []
    with timed("heston_benchmark", inputs=f"{len(pick)} sessions 2019-2020, old B vs B2, one process", rows_in=len(pick)) as run:
        for d in pick:
            r = new.calibrate_session(d, None)
            rows.append({"session": d, "method": "B2 (project pricer, 2 cold starts)", "n": r["n"], "starts": 2,
                         "nfev_total": r.get("nfev"), "ok": r.get("ok"), "iv_rmse": r.get("iv_rmse"),
                         **{k: r.get(k) for k in new.H.NAMES}, "wall_s": r["wall_s"], "cpu_s": r["cpu_s"]})
            rows.append(old_b(d, prm))
            print(d.date(), f"new {rows[-2]['wall_s']:.1f} s, old {rows[-1]['wall_s']:.1f} s", flush=True)
        T = pd.DataFrame(rows)
        T.to_csv(ROOT / "results/heston2/benchmark.csv", index=False)
        s = T.groupby("method")[["wall_s", "cpu_s"]].agg(["median", "sum"])
        run["notes"] = "; ".join(f"{m}: wall median {s.loc[m, ('wall_s', 'median')]:.1f} s, total {s.loc[m, ('wall_s', 'sum')]:.0f} s" for m in s.index)
    print(T.groupby("method")[["wall_s", "cpu_s", "iv_rmse", "nfev_total"]].describe().T.round(3).to_string())


if __name__ == "__main__":
    main()
