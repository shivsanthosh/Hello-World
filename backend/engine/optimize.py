"""Support-spacing and secondary-steel optimisation by exhaustive, deterministic enumeration.

Search space: number of equal panel spans n (i.e. girt spacing H/n) x every girt section in
the library. Each candidate is evaluated with the same design_wall() used for reporting, so
the optimiser cannot return a layout the engine would fail. Objective: minimum secondary
steel mass; ties broken by fewer girt lines, then fewer fasteners.
"""
from __future__ import annotations
import math
from .wall import design_wall

DEFAULT_MIN_SPACING_M = 0.9   # practical constructability limit; user-adjustable per run
MAX_SPANS = 16


def optimise_wall(base_inp: dict, sections: list[dict], min_spacing_m: float = DEFAULT_MIN_SPACING_M) -> dict:
    if not sections:
        raise ValueError("at least one girt section is required")
    if not 0.3 <= min_spacing_m <= 6.0:
        raise ValueError("minimum girt spacing must be between 0.3 and 6.0 m")
    H = base_inp["wall"]["height_m"]
    n_lo = max(1, math.ceil(round(H / base_inp["product"]["max_span_m"], 9)))
    n_hi = min(MAX_SPANS, math.floor(round(H / min_spacing_m, 9)))
    candidates = []
    for n in range(n_lo, n_hi + 1):
        for sec in sections:
            inp = {**base_inp, "design": {**base_inp["design"], "n_spans": n}, "section": sec}
            r = design_wall(inp)
            fails = [c["id"] for c in r["checks"] if c["status"] == "FAIL"]
            candidates.append({"n_spans": n, "girt_spacing_m": r["girt_spacing_m"], "section_id": sec.get("id"),
                               "section_name": sec.get("name"), "feasible": not fails, "failed_checks": fails,
                               "max_dcr": r["summary"]["max_dcr"], "governing_check": r["summary"]["governing_check"],
                               "steel_mass_kg": r["quantities"]["secondary_steel_mass_kg"],
                               "girt_lines": r["quantities"]["girt_lines"],
                               "fastener_count": r["quantities"]["fastener_count"]})
    feasible = [c for c in candidates if c["feasible"]]
    best = min(feasible, key=lambda c: (round(c["steel_mass_kg"], 6), c["girt_lines"], c["fastener_count"])) if feasible else None
    base = design_wall(base_inp)
    baseline = {"n_spans": base_inp["design"]["n_spans"], "girt_spacing_m": base["girt_spacing_m"],
                "section_id": base_inp["section"].get("id"), "section_name": base_inp["section"].get("name"),
                "feasible": base["summary"]["status"] == "PASS", "max_dcr": base["summary"]["max_dcr"],
                "steel_mass_kg": base["quantities"]["secondary_steel_mass_kg"],
                "girt_lines": base["quantities"]["girt_lines"], "fastener_count": base["quantities"]["fastener_count"]}
    # A "saving" is only meaningful against a layout that itself passes. If the prior layout
    # fails, the difference is reported as steel added to reach compliance, never as a saving.
    diff = (baseline["steel_mass_kg"] - best["steel_mass_kg"]) if best else None
    saving = diff if (best and baseline["feasible"]) else None
    added = -diff if (best and not baseline["feasible"]) else None
    return {"objective": "minimum secondary steel mass (girts + opening framing)",
            "search": {"min_spacing_m": min_spacing_m, "n_spans_min": n_lo, "n_spans_max": n_hi, "sections": len(sections), "evaluated": len(candidates),
                       "feasible": len(feasible)},
            "baseline": baseline, "best": best, "candidates": candidates,
            "steel_saving_kg": saving,
            "steel_saving_pct": (saving / baseline["steel_mass_kg"] * 100 if saving is not None and baseline["steel_mass_kg"] > 0 else None),
            "steel_added_for_compliance_kg": added,
            "note": ("The layout before optimisation fails one or more checks, so no saving is claimed; the best layout "
                     "is the lightest one that passes." if added is not None else
                     "No layout passes every check within the search limits (maximum panel span, minimum girt spacing, "
                     "section library)." if not best else "")}
