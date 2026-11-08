"""Step 2: convert every OptionsDX archive in data/raw/optionsdx (or --raw) to monthly Parquet files.

Each archive is extracted into its own fresh temporary directory, its month files
are converted, and the directory is deleted. Writes the data manifest to
results/data_manifest.csv.

Run from the repository root:
  uv run python -I scripts/build_interim.py [--raw DIR] [--out DIR] [--manifest CSV] [--workers N]
Defaults: data/raw/optionsdx, data/interim/optionsdx, results/data_manifest.csv, 4 workers. For the five
underlyings (REPRODUCING.md, Stage 5): --raw data/raw/optionsdx_stocks --manifest results/stocks/data_manifest_stocks.csv
"""

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from erdos_quant_finance_project.runlog import timed
from erdos_quant_finance_project.optionsdx import MEMBER_RE, month_summary, read_month, write_month

ROOT = Path(__file__).resolve().parents[1]
TAR = r"C:\Windows\System32\tar.exe"  # bsdtar reads 7z; Git Bash's GNU tar does not


def read_checksums(raw_dir: Path) -> dict[str, str]:
    sums = {}
    for line in (raw_dir / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name.lstrip("*")] = digest
    return sums


def convert_archive(archive: Path, out_root: Path, tmp_root: Path, sha256: str) -> list[dict]:
    rows = []
    with tempfile.TemporaryDirectory(dir=tmp_root, prefix=archive.stem + "-") as tmp:
        subprocess.run([TAR, "-xf", str(archive), "-C", tmp], check=True)
        for member in sorted(Path(tmp).iterdir()):
            m = MEMBER_RE.match(member.name)
            if not m:
                raise ValueError(f"{archive.name}: unexpected member {member.name}")
            underlying, year, month = m.groups()
            if member.stat().st_size == 0:  # e.g. tsla_eod_202107.txt in tsla_eod_2021.7z: the month is in another archive
                print(f"skipped empty member {member.name} in {archive.name}", flush=True)
                continue
            table, diag = read_month(member)
            summary = month_summary(table)
            out = write_month(table, out_root, underlying, year, member.stem)
            outside = sum(1 for d in (summary["first_quote_date"], summary["last_quote_date"])
                          if d[:7] != f"{year}-{month}")
            rows.append({
                "underlying": underlying, "year": int(year), "month": int(month),
                "archive": archive.name, "archive_sha256": sha256, "member": member.name,
                "member_bytes": member.stat().st_size, **summary, **diag,
                "quote_dates_outside_month": outside,
                "parquet_path": out.relative_to(ROOT).as_posix(), "parquet_bytes": out.stat().st_size,
            })
    print(f"done {archive.name}: {len(rows)} months", flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data/raw/optionsdx")
    ap.add_argument("--out", type=Path, default=ROOT / "data/interim/optionsdx")
    ap.add_argument("--manifest", type=Path, default=ROOT / "results/data_manifest.csv")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    sums = read_checksums(args.raw)
    archives = sorted(args.raw.glob("*.7z"))
    if sorted(a.name for a in archives) != sorted(sums):
        sys.exit("archives in data/raw/optionsdx do not match SHA256SUMS")
    tmp_root = ROOT / "data/_extract"
    tmp_root.mkdir(parents=True, exist_ok=True)
    with timed("build_interim", inputs=f"{args.raw.name}, {len(archives)} archives") as run:
        with ThreadPoolExecutor(args.workers) as pool:
            results = pool.map(lambda a: convert_archive(a, args.out, tmp_root, sums[a.name]), archives)
            rows = [r for batch in results for r in batch]
        run["rows_out"] = sum(r["rows"] for r in rows)
    shutil.rmtree(tmp_root)

    rows.sort(key=lambda r: (r["underlying"], r["year"], r["month"]))
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(args.manifest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} months to {args.manifest.resolve().relative_to(ROOT)}")


if __name__ == "__main__":
    main()
