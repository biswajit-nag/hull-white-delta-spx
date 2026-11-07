"""Check that your input files are the ones this study used, before running the pipeline (REPRODUCING.md).

- The OptionsDX archives against results/data_manifest.csv (SPX and SPY) and results/stocks/data_manifest_stocks.csv
  (AAPL, NVDA, TSLA, QQQ, SLV): every archive present, with the listed SHA-256 checksum.
- The external files (index closes, SPY's history and distributions, dividends) against results/external_manifest.csv.
A folder that is absent is reported and skipped, so you can check only the inputs of the stages you run.

scripts/build_interim.py needs a SHA256SUMS file beside the archives. With --write-sums, a raw folder whose
archives all match gets one, written from the manifest, if it has none.

The author writes results/external_manifest.csv with --write-external (from data/external/SOURCES.csv).

Usage: uv run python -I scripts/check_inputs.py [--raw DIR] [--stocks-raw DIR] [--external DIR] [--write-sums]
       uv run python -I scripts/check_inputs.py --write-external
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = {"raw": ROOT / "results/data_manifest.csv", "stocks_raw": ROOT / "results/stocks/data_manifest_stocks.csv"}
EXTERNAL_MANIFEST = ROOT / "results/external_manifest.csv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_archives(folder: Path, manifest: Path, write_sums: bool) -> int:
    want = {r["archive"]: r["archive_sha256"] for r in read_rows(manifest)}
    if not folder.is_dir():
        print(f"SKIP  {folder}: not found ({len(want)} archives listed in {manifest.relative_to(ROOT)})")
        return 0
    bad = 0
    for name, sha in sorted(want.items()):
        f = folder / name
        if not f.exists():
            print(f"MISSING  {name}"); bad += 1
        elif sha256(f) != sha:
            print(f"CHECKSUM MISMATCH  {name}"); bad += 1
    extra = sorted(p.name for p in folder.glob("*.7z") if p.name not in want)
    for name in extra:
        print(f"EXTRA (not in the manifest; build_interim.py will refuse it)  {name}"); bad += 1
    print(f"{'OK   ' if not bad else 'FAIL '} {folder}: {len(want) - bad} of {len(want)} archives match {manifest.relative_to(ROOT)}")
    sums = folder / "SHA256SUMS"
    if not sums.exists():
        if write_sums and not bad:
            sums.write_text("".join(f"{sha} *{name}\n" for name, sha in sorted(want.items())))
            print(f"      wrote {sums}")
        else:
            print(f"      {sums.name} absent: build_interim.py needs it (rerun with --write-sums once all archives match)")
    return bad


def describe(path: Path) -> tuple[int, str, str]:
    """Rows, first date and last date of an external file (dates in ISO form)."""
    if path.suffix == ".json":
        rows = ((json.loads(path.read_text(encoding="utf-8")).get("data") or {}).get("dividends") or {}).get("rows") or []
        dates = sorted(f"{d[6:10]}-{d[0:2]}-{d[3:5]}" for d in (r.get("exOrEffDate", "") for r in rows) if len(d) == 10)
        return len(rows), (dates[0] if dates else ""), (dates[-1] if dates else "")
    with open(path, newline="", encoding="utf-8") as f:
        first_col = [r[0] for r in list(csv.reader(f))[1:] if r]
    iso = sorted(d if d[4:5] == "-" else f"{d[6:10]}-{d[0:2]}-{d[3:5]}" for d in first_col if len(d) == 10)
    return len(first_col), (iso[0] if iso else ""), (iso[-1] if iso else "")


def write_external(folder: Path) -> None:
    rows = []
    for s in read_rows(folder / "SOURCES.csv"):
        f = folder / s["source"]
        n, first, last = describe(f)
        rows.append({"file": f.name, "bytes": f.stat().st_size, "sha256": sha256(f), "rows": n, "first_date": first,
                     "last_date": last, "url": s["url"], "downloaded": s["downloaded"], "description": s["description"]})
    with open(EXTERNAL_MANIFEST, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    print(f"wrote {EXTERNAL_MANIFEST.relative_to(ROOT)} ({len(rows)} files)")


def check_external(folder: Path) -> int:
    want = read_rows(EXTERNAL_MANIFEST)
    if not folder.is_dir():
        print(f"SKIP  {folder}: not found"); return 0
    bad = 0
    for r in want:
        f = folder / r["file"]
        if not f.exists():
            print(f"MISSING  {r['file']}  ({r['url']})"); bad += 1
        elif sha256(f) != r["sha256"]:
            n, first, last = describe(f)
            print(f"DIFFERS  {r['file']}: rows {n}, {first} to {last}; the study's had {r['rows']}, {r['first_date']} to "
                  f"{r['last_date']} (DATA.md says what a later download changes)"); bad += 1
    print(f"{'OK   ' if not bad else 'FAIL '} {folder}: {len(want) - bad} of {len(want)} external files match "
          f"{EXTERNAL_MANIFEST.relative_to(ROOT)}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "data/raw/optionsdx")
    ap.add_argument("--stocks-raw", type=Path, default=ROOT / "data/raw/optionsdx_stocks")
    ap.add_argument("--external", type=Path, default=ROOT / "data/external")
    ap.add_argument("--write-sums", action="store_true")
    ap.add_argument("--write-external", action="store_true")
    a = ap.parse_args()
    if a.write_external:
        write_external(a.external); return
    bad = check_archives(a.raw, MANIFESTS["raw"], a.write_sums)
    bad += check_archives(a.stocks_raw, MANIFESTS["stocks_raw"], a.write_sums)
    bad += check_external(a.external)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
