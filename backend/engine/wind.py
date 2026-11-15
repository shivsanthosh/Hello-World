"""Wind pressures on wall cladding and secondary members, NBCC 2020 4.1.7 (static procedure, low-rise)."""
from __future__ import annotations
import math
from .trace import step, fmt

TERRAINS = ("Open", "Rough")


def exposure_factor(h_m: float, terrain: str) -> float:
    """Ce per NBCC 2020 4.1.7.3.(5). Reference height not less than 6 m."""
    if h_m <= 0:
        raise ValueError("reference height must be positive")
    h = max(h_m, 6.0)
    if terrain == "Open":
        return max((h / 10.0) ** 0.2, 0.9)
    if terrain == "Rough":
        return max(0.7 * (h / 12.0) ** 0.3, 0.7)
    raise ValueError(f"unknown terrain '{terrain}' (expected one of {TERRAINS})")


def effective_area(span_m: float, width_m: float) -> float:
    """Tributary area for CpCg; width need not be taken less than span/3."""
    if span_m <= 0 or width_m <= 0:
        raise ValueError("span and width must be positive")
    return span_m * max(width_m, span_m / 3.0)


def cpcg_wall(area_m2: float, key: str, table: dict) -> float:
    """Log-linear interpolation of CpCg in tributary area. key: positive | negative_w | negative_e."""
    if area_m2 <= 0:
        raise ValueError("area must be positive")
    lo, hi = table["area_lo"], table["area_hi"]
    v = table[key]
    if area_m2 <= lo:
        return v["lo"]
    if area_m2 >= hi:
        return v["hi"]
    f = (math.log10(area_m2) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    return v["lo"] + f * (v["hi"] - v["lo"])


def end_zone_width(least_plan_dim_m: float, h_m: float) -> float:
    """End-zone width z: lesser of 10% least horizontal dimension and 40% of H,
    but not less than 4% of least horizontal dimension or 1 m (NBCC Fig. 4.1.7.6.-B notes)."""
    if least_plan_dim_m <= 0 or h_m <= 0:
        raise ValueError("dimensions must be positive")
    z = min(0.10 * least_plan_dim_m, 0.40 * h_m)
    return max(z, 0.04 * least_plan_dim_m, 1.0)


def net_pressures(*, q50_kpa: float, importance: str, terrain: str, h_m: float, ct: float,
                  internal_category: str, area_m2: float, code: dict, tag: str) -> dict:
    """Net specified/factored pressures across the wall for one tributary area.

    Suction (outward):  p = Iw q Ce Ct (CpCg_neg - Cgi*Cpi_max)   [negative]
    Pressure (inward):  p = Iw q Ce Ct (CpCg_pos - Cgi*Cpi_min)   [positive]
    Returned magnitudes are positive numbers in kPa for cases 'pressure', 'suction_w', 'suction_e'.
    """
    if q50_kpa <= 0:
        raise ValueError("q (1-in-50 reference velocity pressure) must be positive")
    if ct < 1.0:
        raise ValueError("topographic factor Ct cannot be less than 1.0")
    iw = code["nbcc.importance_factor_wind"][importance]
    ip = code["nbcc.internal_pressure"]
    cat = ip[internal_category]
    cgi = ip["cgi"]
    lf = code["nbcc.wind_load_factor_uls"]
    tbl = code["nbcc.cpcg_walls"]
    ce = exposure_factor(h_m, terrain)
    steps = [step(f"{tag}.ce", "Exposure factor Ce",
                  "Ce = max((h/10)^0.2, 0.9)" if terrain == "Open" else "Ce = max(0.7(h/12)^0.3, 0.7)",
                  f"h = max({fmt(h_m,2)}, 6.0) m, terrain = {terrain}", ce, "-", "NBCC 2020 4.1.7.3.(5)")]
    warnings = []
    if h_m > 20.0:
        warnings.append("Reference height exceeds 20 m: NBCC Figure 4.1.7.6.-B low-rise coefficients "
                        "are outside their stated range; engineer must select the applicable procedure.")
    coef = {"pressure": ("positive", cat["cpi_min"]), "suction_w": ("negative_w", cat["cpi_max"]),
            "suction_e": ("negative_e", cat["cpi_max"])}
    out = {"ce": ce, "iw_uls": iw["ULS"], "iw_sls": iw["SLS"], "area_m2": area_m2, "cases": {},
           "steps": steps, "warnings": warnings}
    for case, (key, cpi) in coef.items():
        cpcg = cpcg_wall(area_m2, key, tbl)
        net = cpcg - cgi * cpi
        p_spec_uls = iw["ULS"] * q50_kpa * ce * ct * abs(net)
        p_sls = iw["SLS"] * q50_kpa * ce * ct * abs(net)
        p_f = lf * p_spec_uls
        steps.append(step(f"{tag}.{case}.cpcg", f"CpCg ({case}, A = {fmt(area_m2,2)} m2)",
                          "log-linear interpolation in A between 1 and 50 m2",
                          f"table '{key}': {tbl[key]['lo']} at <=1 m2, {tbl[key]['hi']} at >=50 m2",
                          cpcg, "-", "NBCC 2020 Fig. 4.1.7.6.-B"))
        steps.append(step(f"{tag}.{case}.pf", f"Factored net pressure ({case})",
                          "pf = 1.4 * Iw * q * Ce * Ct * |CpCg - Cgi*Cpi|",
                          f"{lf} * {iw['ULS']} * {fmt(q50_kpa)} * {fmt(ce)} * {fmt(ct,2)} * |{fmt(cpcg)} - {cgi}*({cpi})|",
                          p_f, "kPa", "NBCC 2020 4.1.7.3.(1),(3); Table 4.1.3.2.-A"))
        steps.append(step(f"{tag}.{case}.ps", f"Service net pressure ({case})",
                          "ps = Iw,SLS * q * Ce * Ct * |CpCg - Cgi*Cpi|",
                          f"{iw['SLS']} * {fmt(q50_kpa)} * {fmt(ce)} * {fmt(ct,2)} * {fmt(abs(net))}",
                          p_sls, "kPa", "NBCC 2020 4.1.7.3.; Table 4.1.7.3."))
        out["cases"][case] = {"cpcg": cpcg, "cpi": cpi, "net_coeff": net, "p_uls": p_f, "p_sls": p_sls}
    return out
