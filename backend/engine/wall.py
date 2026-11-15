"""Wall-level design: wind -> panel -> girt, plus quantity take-off. Pure function of its inputs."""
from __future__ import annotations
import math
from . import ENGINE_VERSION
from .wind import net_pressures, effective_area, end_zone_width
from .panel import panel_checks
from .girt import girt_checks
from .sections import lipped_section
from .trace import step, fmt

ASSUMPTIONS = [
    "Panels span vertically, continuous over equally spaced horizontal girts; base supported at foundation, top at eave girt.",
    "End-zone (zone e) suction governs the whole wall: girts are continuous through end zones, so one spacing is used.",
    "Wind only (NBCC 2020 static procedure, low-rise coefficients). Thermal bow, seismic, impact, snow drift on walls and dead load are not included.",
    "Girt: simple span between columns, gross section fully effective; web crippling, combined actions and connections not checked.",
    "Product strengths are taken from the product record; results inherit that record's evidence status.",
]


def girt_elevations(height_m: float, n_spans: int) -> list[float]:
    if n_spans < 1:
        raise ValueError("n_spans must be at least 1")
    s = height_m / n_spans
    return [round(s * k, 6) for k in range(1, n_spans + 1)]


def takeoff(*, wall: dict, n_spans: int, product: dict, section: dict, fasteners_per_support: int,
            density: float) -> dict:
    """Quantities from geometry. Girts are cut at openings they cross; openings get jamb/header/sill framing."""
    L, H = wall["length_m"], wall["height_m"]
    module = product["module_mm"] / 1000.0
    n_panels = math.ceil(round(L / module, 6))
    open_area = sum(o["width_m"] * o["height_m"] for o in wall.get("openings", []))
    net_area = L * H - open_area
    if net_area <= 0:
        raise ValueError("openings exceed wall area")
    girt_len = 0.0
    for z in girt_elevations(H, n_spans):
        cut = sum(o["width_m"] for o in wall.get("openings", []) if o["sill_m"] < z < o["sill_m"] + o["height_m"])
        girt_len += L - cut
    frame_len = sum(2 * o["height_m"] + o["width_m"] + (o["width_m"] if o["sill_m"] > 0 else 0.0)
                    for o in wall.get("openings", []))
    mass_m = lipped_section(section["shape"], section["depth_mm"], section["flange_mm"], section["lip_mm"],
                            section["t_mm"], density)["mass_kg_per_m"]
    return {"panel_count": n_panels, "gross_area_m2": L * H, "opening_area_m2": open_area, "net_panel_area_m2": net_area,
            "panel_mass_kg": net_area * product.get("mass_kg_m2", 0.0),
            "girt_lines": n_spans, "girt_length_m": girt_len, "opening_framing_length_m": frame_len,
            "steel_mass_kg_per_m": mass_m, "secondary_steel_mass_kg": (girt_len + frame_len) * mass_m,
            "fastener_count": n_panels * (n_spans + 1) * fasteners_per_support}


def design_wall(inp: dict) -> dict:
    """inp = {site, wall, design:{n_spans, fasteners_per_support}, product, section, code}."""
    site, wall, des, product, section, code = (inp[k] for k in ("site", "wall", "design", "product", "section", "code"))
    H, L = wall["height_m"], wall["length_m"]
    if H <= 0 or L <= 0:
        raise ValueError("wall height and length must be positive")
    bay = wall["max_bay_m"]
    if bay <= 0:
        raise ValueError("column bay spacing must be positive")
    n = int(des["n_spans"])
    if n < 1:
        raise ValueError("n_spans must be at least 1")
    s = H / n
    module = product["module_mm"] / 1000.0
    common = dict(q50_kpa=site["q50_kpa"], importance=site["importance"], terrain=site["terrain"],
                  h_m=site["ref_height_m"], ct=site.get("ct", 1.0), internal_category=site["internal_category"], code=code)
    wp = net_pressures(area_m2=effective_area(s, module), tag="wind.panel", **common)
    wg = net_pressures(area_m2=effective_area(bay, s), tag="wind.girt", **common)
    z = end_zone_width(site["least_plan_dim_m"], site["ref_height_m"])
    steps = [step("geom.spacing", "Girt spacing (panel span)", "s = H / n_spans", f"{fmt(H)} / {n}", s, "m", "Wall geometry (model import)"),
             step("wind.zone", "End-zone width z", "z = max(min(0.1 D, 0.4 H), 0.04 D, 1 m)",
                  f"D = {fmt(site['least_plan_dim_m'],2)} m, H = {fmt(site['ref_height_m'],2)} m", z, "m", "NBCC 2020 Fig. 4.1.7.6.-B")]
    steps += wp["steps"] + wg["steps"]
    checks = []
    lim = code["limits.panel_deflection"]
    panel_res = {}
    for direction, case in (("pressure", "pressure"), ("suction", "suction_e")):
        r = panel_checks(product=product, spans_m=[s] * n, p_uls_kpa=wp["cases"][case]["p_uls"],
                         p_sls_kpa=wp["cases"][case]["p_sls"], direction=direction, defl_limit=lim,
                         fasteners_per_panel_per_support=int(des["fasteners_per_support"]), tag=f"panel.{direction}")
        panel_res[direction] = r
        steps += r["steps"]; checks += r["checks"]
        coeff = r["reaction_coeff"]
        w_u = wg["cases"][case]["p_uls"] * s * coeff
        w_s = wg["cases"][case]["p_sls"] * s * coeff
        steps.append(step(f"girt.{direction}.w", f"Girt factored line load ({direction})", "wf = pf,girt * s * k_R",
                          f"{fmt(wg['cases'][case]['p_uls'])} kPa * {fmt(s)} m * {fmt(coeff)} (k_R = panel reaction coefficient R/(p s))",
                          w_u, "kN/m", "Statics: panel continuity reaction on most heavily loaded girt"))
        g = girt_checks(section=section, span_m=bay, w_uls_kN_m=w_u, w_sls_kN_m=w_s, direction=direction,
                        code=code, tag=f"girt.{direction}")
        steps += g["steps"]; checks += g["checks"]
    qty = takeoff(wall=wall, n_spans=n, product=product, section=section,
                  fasteners_per_support=int(des["fasteners_per_support"]), density=code["steel.density_kg_m3"])
    gov = max(checks, key=lambda c: c["dcr"])
    return {"engine_version": ENGINE_VERSION, "girt_spacing_m": s, "girt_elevations_m": girt_elevations(H, n),
            "end_zone_width_m": z, "pressures": {"panel": wp["cases"], "girt": wg["cases"]},
            "steps": steps, "checks": checks, "quantities": qty,
            "summary": {"status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
                        "max_dcr": gov["dcr"], "governing_check": gov["id"], "governing_title": gov["title"]},
            "warnings": wp["warnings"], "assumptions": ASSUMPTIONS}
