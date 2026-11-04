"""Step 3: build the long contract-day panel from the interim Parquet files.

Writes data/processed/optionsdx_long/underlying=<u>/year=<y>/ and a per-year count
of every flag and next-session status to results/processed_summary_<u>.csv.
The rules are in DATA.md and src/erdos_quant_finance_project/processed.py.

Run from the repository root:  uv run python -I scripts/build_processed.py --underlying spx
"""

import argparse
import csv
from pathlib import Path

try:
    import psutil  # dev dependency; only used to report memory
except ImportError:
    psutil = None

from erdos_quant_finance_project.processed import build_year, nyse_sessions, official_closes, write_year

ROOT = Path(__file__).resolve().parents[1]


def summarize(long, underlying: str, year: int) -> dict:
    row = {"underlying": underlying, "year": year, "rows": len(long), "quote_dates": long.quote_date.nunique(),
           "am_settled": int(long.am_settled.sum())}
    row |= {c: int(long[c].sum()) for c in long.columns if c.startswith("f_")}
    row |= {f"next_{k}": int(v) for k, v in long.next_status.value_counts().items()}
    row["S_close_missing"] = int(long.S_close.isna().sum())
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="spx", choices=["spx", "spy"])
    ap.add_argument("--years", default="2010-2023", help="e.g. 2019-2020")
    args = ap.parse_args()
    first, last = (int(y) for y in args.years.split("-"))

    sessions = nyse_sessions(f"{first - 1}-11-01", f"{last + 10}-12-31")  # LEAPS run years ahead
    closes = official_closes(ROOT / "data/external", args.underlying)
    out_root = ROOT / "data/processed/optionsdx_long"
    rows = []
    for year in range(first, last + 1):
        long = build_year(ROOT / "data/interim/optionsdx", args.underlying, year, sessions, closes)
        out = write_year(long, out_root, args.underlying, year)
        rows.append(summarize(long, args.underlying, year))
        peak = f" (peak memory so far {psutil.Process().memory_info().peak_wset / 1024 ** 3:.1f} GB)" if psutil else ""
        print(f"{args.underlying} {year}: {len(long):,} rows -> {out.relative_to(ROOT)}{peak}", flush=True)
        del long

    summary = ROOT / f"results/processed_summary_{args.underlying}.csv"
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("underlying", "year", "rows", "quote_dates"), k))
    with open(summary, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval=0)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {summary.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
