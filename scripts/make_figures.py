"""Figures for the README and the write-up (analysis_plan.md §12). Writes results/figures/*.png.

Usage: uv run python -I scripts/make_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402

R = ROOT / "results"
FIG = R / "figures"
NAMES = {"R1": "Black–Scholes delta (R1)", "R2": "Hull–White MV delta (R2)", "R3": "Ruf–Wang 0.9δ / 1.1δ (R3)", "R4": "Ruf–Wang fitted a·δ (R4)"}
COLORS = {"R1": "#444444", "R2": "#1f77b4", "R3": "#d62728", "R4": "#2ca02c"}


def cumulative_2020():
    err = pd.read_parquet(R / "2020/errors.parquet")
    P = h.load_pairs(range(2015, 2021), columns=["quote_date", "cp", "next_status", "E7"])
    e = err.join(P[["quote_date", "cp"]])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=False)
    for ax, cp in zip(axes, "CP"):
        d = e[e.cp == cp].groupby("quote_date")[list(NAMES)].apply(lambda x: (x**2).sum()).cumsum()
        for r in NAMES:
            ax.plot(d.index, d[r] / d.R1.iloc[-1], color=COLORS[r], lw=1.8 if r in ("R1", "R2") else 1.2, label=NAMES[r])
        ax.axvspan(*h.STRESS, color="0.9", zorder=0)
        ax.set_title(f"{'Calls' if cp == 'C' else 'Puts'}: cumulative squared hedging error, 2020")
        ax.set_ylabel("share of R1's full-year total")
        ax.grid(alpha=0.3)
        ax.tick_params(axis="x", rotation=30)
    axes[0].legend(fontsize=8, loc="lower right")
    fig.text(0.5, -0.02, "Shaded: the stress period, 2020-02-24 to 04-30. Normalized hedging errors, 1.06M SPX option pairs.", ha="center", fontsize=8)
    plt.tight_layout()
    fig.savefig(FIG / "cumulative_sse_2020.png", dpi=150, bbox_inches="tight")


def monthly_2020():
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for cp, c in (("C", "#1f77b4"), ("P", "#ff7f0e")):
        m = pd.read_csv(R / f"2020/monthly_{cp}.csv")
        ax.plot(m.month.str[5:], m.G_R2_R1, marker="o", color=c, label=f"{'calls' if cp == 'C' else 'puts'} (mean of months {m.G_R2_R1.mean():+.2f})")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("2020"); ax.set_ylabel("Gain of R2 over R1")
    ax.set_title("Hull–White over Black–Scholes, month by month"); ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(FIG / "monthly_gain_2020.png", dpi=150)


def walkforward():
    f = R / "walkforward/gains_by_year.csv"
    if not f.exists():
        return
    g = pd.read_csv(f)
    g = g[(g.rule == "R2") & (g.base == "R1")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, cp in zip(axes, "CP"):
        for W, c, off in ((12, "#1f77b4", -0.2), (36, "#ff7f0e", 0.0), (60, "#2ca02c", 0.2)):
            x = g[(g.cp == cp) & (g.window == W)]
            ax.errorbar(x.year + off, x.gain, yerr=[x.gain - x.lo, x.hi - x.gain], fmt="o", color=c, capsize=2, label=f"{W}-month window")
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title(f"{'Calls' if cp == 'C' else 'Puts'}: Gain of R2 over R1 by year (95% session-block intervals)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(FIG / "walkforward_by_year.png", dpi=150)


def walkforward_summary():
    """The executive summary's figure: the walk-forward by year, with descriptive labels (PDF and PNG)."""
    f = R / "walkforward/gains_by_year.csv"
    if not f.exists():
        return
    g = pd.read_csv(f)
    g = g[(g.rule == "R2") & (g.base == "R1")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharey=True)
    for ax, cp in zip(axes, "CP"):
        for yr in (2011, 2012, 2013, 2021, 2022, 2023):
            ax.axvspan(yr - 0.45, yr + 0.45, color="0.93", zorder=0, lw=0)
        ax.axvspan(2019.55, 2020.45, color="#fde2c8", zorder=0, lw=0)
        for W, c, off in ((12, "#1f77b4", -0.2), (36, "#ff7f0e", 0.0), (60, "#2ca02c", 0.2)):
            x = g[(g.cp == cp) & (g.window == W)]
            ax.errorbar(x.year + off, x.gain, yerr=[x.gain - x.lo, x.hi - x.gain], fmt="o", ms=4, color=c, capsize=2, lw=1, label=f"{W}-month fits")
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title("Calls" if cp == "C" else "Puts", fontsize=11)
        ax.set_xticks(range(2011, 2024, 2))
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Gain over the Black–Scholes delta")
    axes[0].legend(fontsize=8, loc="lower left")
    plt.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"summary_yearly_gain.{ext}", dpi=200, bbox_inches="tight")


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    cumulative_2020()
    monthly_2020()
    walkforward()
    walkforward_summary()
    print("figures in", FIG)
