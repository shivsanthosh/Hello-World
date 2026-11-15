"""Cold-formed steel girt checks (simple span between columns), CSA S136 / AISI S100 (LSD).

Scope and assumptions (reported with every run, engineer to confirm):
  * gross section taken as fully effective (no local/distortional buckling reduction);
  * pressure case: compression (outer) flange restrained by the through-fastened panel;
  * suction case: inner flange unbraced, strength reduced by factor R (through-fastened provision);
  * web crippling, combined bending+shear, connections and axial loads are NOT checked here.
"""
from __future__ import annotations
import math
from .sections import lipped_section
from .trace import step, check, fmt


def shear_stress_Fv(h_over_t: float, Fy: float, E: float, kv: float = 5.34, mu: float = 0.3) -> float:
    """Nominal web shear stress, unreinforced web (AISI S100-12 C3.2.1 form)."""
    if h_over_t <= 0 or Fy <= 0 or E <= 0:
        raise ValueError("h/t, Fy and E must be positive")
    lim1 = math.sqrt(E * kv / Fy)
    if h_over_t <= lim1:
        return 0.60 * Fy
    if h_over_t <= 1.51 * lim1:
        return 0.60 * math.sqrt(E * kv * Fy) / h_over_t
    return math.pi ** 2 * E * kv / (12 * (1 - mu ** 2) * h_over_t ** 2)


def r_factor(shape: str, depth_mm: float, table: dict) -> float:
    for row in table["simple"]:
        if depth_mm <= row["d_max_mm"]:
            return row[shape]
    raise ValueError(f"girt depth {depth_mm} mm is outside the range of the through-fastened R-factor table")


def girt_checks(*, section: dict, span_m: float, w_uls_kN_m: float, w_sls_kN_m: float, direction: str,
                code: dict, tag: str) -> dict:
    """section: {shape, depth_mm, flange_mm, lip_mm, t_mm, Fy_MPa}."""
    if span_m <= 0:
        raise ValueError("girt span must be positive")
    if direction not in ("pressure", "suction"):
        raise ValueError("direction must be 'pressure' or 'suction'")
    E = code["steel.E_MPa"]; Fy = section["Fy_MPa"]
    pr = lipped_section(section["shape"], section["depth_mm"], section["flange_mm"], section["lip_mm"],
                        section["t_mm"], code["steel.density_kg_m3"])
    phi_b, phi_v = code["s136.phi_b"], code["s136.phi_v"]
    R = r_factor(section["shape"], section["depth_mm"], code["s136.r_through_fastened"]) if direction == "suction" else 1.0
    Mf = w_uls_kN_m * span_m ** 2 / 8.0
    Vf = w_uls_kN_m * span_m / 2.0
    Mr = phi_b * R * pr["Sx_mm3"] * Fy / 1e6
    Fv = shear_stress_Fv(pr["h_over_t"], Fy, E)
    Vr = phi_v * pr["web_flat_mm"] * section["t_mm"] * Fv / 1e3
    EI = E * pr["Ix_mm4"] / 1e9                                   # kN*m2
    d = 5 * w_sls_kN_m * span_m ** 4 / (384 * EI) * 1000          # mm
    lim = code["limits.girt_deflection"]
    steps = [
        step(f"{tag}.Sx", "Girt gross section modulus", "Sx = Ix/(D/2); Ix by thin-wall centreline method",
             f"{section['shape']} {section['depth_mm']}x{section['flange_mm']}x{section['lip_mm']}x{section['t_mm']} mm, Ix = {pr['Ix_mm4']:.0f} mm4",
             pr["Sx_mm3"], "mm3", "Section geometry (gross properties)"),
        step(f"{tag}.Mf", "Factored girt moment", "Mf = wf L^2 / 8", f"{fmt(w_uls_kN_m)} * {fmt(span_m)}^2 / 8", Mf, "kN*m", "Statics, simple span"),
        step(f"{tag}.Mr", "Factored moment resistance", "Mr = phi_b * R * Sx * Fy",
             f"{phi_b} * {R} * {pr['Sx_mm3']:.0f} mm3 * {Fy} MPa", Mr, "kN*m",
             "CSA S136-16 F2.1 (yielding); I6.2.1 (R, through-fastened, suction only)"),
        step(f"{tag}.Vf", "Factored girt shear", "Vf = wf L / 2", f"{fmt(w_uls_kN_m)} * {fmt(span_m)} / 2", Vf, "kN", "Statics, simple span"),
        step(f"{tag}.Vr", "Factored shear resistance", "Vr = phi_v * h * t * Fv",
             f"{phi_v} * {fmt(pr['web_flat_mm'],1)} * {section['t_mm']} * {fmt(Fv,1)} MPa (h/t = {fmt(pr['h_over_t'],1)})", Vr, "kN",
             "CSA S136 / AISI S100 web shear, unreinforced web (kv = 5.34)"),
        step(f"{tag}.defl", "Service deflection", "d = 5 ws L^4 / (384 E Ix)",
             f"5 * {fmt(w_sls_kN_m)} * {fmt(span_m)}^4 / (384 * {E:.0f} MPa * {pr['Ix_mm4']:.0f} mm4)", d, "mm", "Statics, simple span"),
    ]
    checks = [
        check(f"{tag}.bending", f"Girt bending ({direction})", Mf, Mr, "kN*m", "Mf <= phi_b R Sx Fy", "CSA S136-16 F2.1 / I6.2.1"),
        check(f"{tag}.shear", f"Girt shear ({direction})", Vf, Vr, "kN", "Vf <= phi_v Aw Fv", "CSA S136 web shear"),
        check(f"{tag}.deflection", f"Girt deflection (L/{lim:g}, {direction})", d, span_m / lim * 1000, "mm",
              f"d <= L/{lim:g}", "Project serviceability criterion"),
    ]
    return {"direction": direction, "props": pr, "R": R, "steps": steps, "checks": checks}
