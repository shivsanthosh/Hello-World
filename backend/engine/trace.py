"""Trace helpers: every calculated quantity carries formula, units and source."""
from __future__ import annotations
from typing import Any


def step(id: str, title: str, formula: str, substitution: str, value: float, unit: str,
         reference: str, note: str = "") -> dict[str, Any]:
    return {"id": id, "title": title, "formula": formula, "substitution": substitution,
            "value": value, "unit": unit, "reference": reference, "note": note}


def check(id: str, title: str, demand: float, capacity: float, unit: str, formula: str,
          reference: str, note: str = "") -> dict[str, Any]:
    """Demand/capacity check. PASS when demand <= capacity (DCR <= 1.0)."""
    if capacity <= 0:
        raise ValueError(f"check '{id}': capacity must be positive, got {capacity}")
    dcr = abs(demand) / capacity
    return {"id": id, "title": title, "demand": abs(demand), "capacity": capacity, "unit": unit,
            "dcr": dcr, "status": "PASS" if dcr <= 1.0 else "FAIL", "formula": formula,
            "reference": reference, "note": note}


def fmt(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}"
