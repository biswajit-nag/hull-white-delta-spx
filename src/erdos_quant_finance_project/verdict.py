"""The secondary tests and the verdict table of analysis_plan.md §8."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .hedging import holm

M_MATERIAL, EQUIV = 0.05, 0.02


def secondary_tests(g: pd.DataFrame) -> pd.DataFrame:
    """R2 against R3 and R4, calls and puts: Holm within the four superiority tests (p₊) and,
    separately, within the four inferiority tests (p₋), each at one-sided 0.025."""
    s = g[(g.rule == "R2") & g.base.isin(["R3", "R4"])].copy()
    s["p_plus_holm"] = holm(s.p_plus.to_numpy())
    s["p_minus_holm"] = holm(s.p_minus.to_numpy())
    s["reading"] = np.where(s.p_plus_holm < 0.025, "R2 beats",
                            np.where(s.p_minus_holm < 0.025, "R2 worse", "not distinguished"))
    s["equivalent"] = (s.lo > -EQUIV) & (s.hi < EQUIV)
    return s


def verdict(g: pd.DataFrame) -> dict:
    """The first row of the verdict table that applies, from a gain_table() with R2–R1, R2–R3, R2–R4."""
    p = g[(g.rule == "R2") & (g.base == "R1")].set_index("cp")
    s = secondary_tests(g).set_index(["cp", "base"])
    h1 = bool((p.lo > 0).all())
    if (p.hi < 0).any():
        v = "Reject (a)"
    elif (p.hi < M_MATERIAL).all():
        v = "Reject (b)"
    elif h1 and (s.reading == "R2 worse").any():
        v = "Reject (c)"
    elif h1 and (p.gain >= M_MATERIAL).all() and all(s.loc[(cp, "R4"), "reading"] == "R2 beats" for cp in "CP"):
        v = "Approve"
    elif h1 and (p.gain >= M_MATERIAL).all():
        v = "Approve with conditions"
    else:
        v = "Inconclusive"
    out = {"verdict": v, "H1": h1}
    for cp in "CP":
        out |= {f"G_{cp}": p.loc[cp, "gain"], f"G_{cp}_lo": p.loc[cp, "lo"], f"G_{cp}_hi": p.loc[cp, "hi"]}
        out |= {f"{cp}_vs_{b}": s.loc[(cp, b), "reading"] for b in ("R3", "R4")}
    return out
