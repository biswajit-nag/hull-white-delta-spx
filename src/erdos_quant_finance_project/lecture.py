"""Load the boot camp's final option-pricing library (Lecture 12) from a local clone.

The lecture repository (github.com/TheErdosInstitute/quant-finance) has no licence file, so the
library is imported from the clone rather than copied here (analysis_plan.md §4). Point
ERDOS_LECTURE12 at the folder holding option_pricing.py if the clone lives elsewhere.
"""

from __future__ import annotations

import importlib.util
import os
from functools import cache
from pathlib import Path

DEFAULT = Path(r"D:\My Code\quant-finance\Fall 2026\Lecture 12")
VERSION = "2026.11.02.1"  # commit b2709e9, 2026-11-03


def lecture12_path() -> Path:
    return Path(os.environ.get("ERDOS_LECTURE12", DEFAULT)) / "option_pricing.py"


@cache
def option_pricing():
    """The lecture module, after checking it is the pinned version."""
    path = lecture12_path()
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; clone the lecture repository or set ERDOS_LECTURE12")
    spec = importlib.util.spec_from_file_location("option_pricing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.__version__ != VERSION:
        raise RuntimeError(f"option_pricing {module.__version__} found; the plan pins {VERSION}")
    return module
