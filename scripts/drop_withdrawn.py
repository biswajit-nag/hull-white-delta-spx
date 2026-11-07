"""Apply the withdrawal of 2026-11-06 (analysis_plan.md §15) to the result tables.

The regression tree R7 and every Heston rule (H_model, H_mv, H_fit) were withdrawn from the submission,
but their code stays in scripts/ and src/, so a rerun of the pipeline writes their rows again. This
script removes them, exactly as was done to the committed tables:
- a row is dropped if any field names a withdrawn rule (e.g. rule R7, base R7, h_R7);
- a column is dropped if it is a withdrawn rule or ends in one (e.g. sse_R7);
- the held positions' subset "heston" (the paths whose every day is in the analysis sample) is
  relabelled "in_band", and the column heston_complete becomes in_band_complete.
Fields are read and written as text, so every number keeps its exact digits. Running it twice is harmless.

Usage: uv run python -I scripts/drop_withdrawn.py [FILE_OR_DIR ...]   (default: results/)
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITHDRAWN = ("R7", "H_model", "H_mv", "H_fit")
CELLS = set(WITHDRAWN) | {f"h_{r}" for r in WITHDRAWN}
RENAME_COLUMNS = {"heston_complete": "in_band_complete"}
RELABEL = {"subset": {"heston": "in_band"}}


def withdrawn_column(name: str) -> bool:
    return name in WITHDRAWN or any(name.endswith(f"_{r}") for r in WITHDRAWN)


def filter_text(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return text
    header = rows[0]
    keep = [i for i, c in enumerate(header) if not withdrawn_column(c)]
    out = [[RENAME_COLUMNS.get(header[i], header[i]) for i in keep]]
    for row in rows[1:]:
        if any(f in CELLS for f in row):
            continue
        row = [RELABEL.get(header[i], {}).get(row[i], row[i]) if i < len(row) else "" for i in keep]
        out.append(row)
    if out == rows:  # nothing withdrawn: leave the file exactly as it is
        return text
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator=newline).writerows(out)
    return buf.getvalue()


def main(paths: list[Path]) -> None:
    files = [f for p in paths for f in (sorted(p.rglob("*.csv")) if p.is_dir() else [p])]
    changed = 0
    for f in files:
        text = f.read_bytes().decode("utf-8")
        new = filter_text(text)
        if new != text:
            f.write_bytes(new.encode("utf-8"))
            changed += 1
            print("filtered", f.relative_to(ROOT) if f.is_relative_to(ROOT) else f)
    print(f"{changed} of {len(files)} files changed")


if __name__ == "__main__":
    main([Path(a).resolve() for a in sys.argv[1:]] or [ROOT / "results"])
