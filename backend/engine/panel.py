"""Insulated metal panel (IMP) checks: sandwich stiffness from first principles, strength from product records.

Stiffness is calculated (thin-face sandwich theory). Strength values (bending,
shear, fastener) are test-derived and must come from the product record with
their evidence status; the engine never invents a capacity.
"""
from __future__ import annotations
from .beam import continuous_beam
from .trace import step, check, fmt

REQUIRED_PRODUCT_FIELDS = ("thickness_mm", "face_ext_mm", "face_int_mm", "E_face_MPa", "G_core_MPa",
                           "Mr_kNm_per_m", "Vr_kN_per_m", "fastener_Tr_kN", "max_span_m", "module_mm")


def sandwich_stiffness(thickness_mm: float, face_ext_mm: float, face_int_mm: float,
                       E_face_MPa: float, G_core_MPa: float) -> dict:
    """Per metre width. Thin flat faces, core carries shear, faces carry bending.

    e  = D - (t1 + t2)/2                      distance between face centroids
    EI = E * A1*A2/(A1+A2) * e^2              (face own-inertia neglected)
    GA = G_core * b * e^2 / d_core            (d_core = D - t1 - t2)
    """
    for name, v in (("thickness", thickness_mm), ("exterior face", face_ext_mm), ("interior face", face_int_mm),
                    ("E_face", E_face_MPa), ("G_core", G_core_MPa)):
        if v <= 0:
            raise ValueError(f"{name} must be positive")
    d_core = thickness_mm - face_ext_mm - face_int_mm
    if d_core <= 0:
        raise ValueError("face thicknesses exceed panel thickness")
    e = thickness_mm - (face_ext_mm + face_int_mm) / 2.0
    a1, a2 = face_ext_mm * 1000.0, face_int_mm * 1000.0            # mm2 per m width
    EI_Nmm2 = E_face_MPa * a1 * a2 / (a1 + a2) * e ** 2
    GA_N = G_core_MPa * 1000.0 * e ** 2 / d_core
    return {"e_mm": e, "d_core_mm": d_core, "EI_kNm2_per_m": EI_Nmm2 / 1e9, "GA_kN_per_m": GA_N / 1e3}


def panel_checks(*, product: dict, spans_m: list[float], p_uls_kpa: float, p_sls_kpa: float,
                 direction: str, defl_limit: float, fasteners_per_panel_per_support: int, tag: str) -> dict:
    """Checks a 1 m wide strip of panel, continuous over the given spans, for one load direction.

    direction: 'pressure' (panel bears on supports) or 'suction' (fasteners in tension).
    """
    missing = [f for f in REQUIRED_PRODUCT_FIELDS if product.get(f) in (None, "")]
    if missing:
        raise ValueError(f"product record is missing required engineering data: {', '.join(missing)}")
    if direction not in ("pressure", "suction"):
        raise ValueError("direction must be 'pressure' or 'suction'")
    if defl_limit <= 0:
        raise ValueError("deflection limit denominator must be positive")
    st = sandwich_stiffness(product["thickness_mm"], product["face_ext_mm"], product["face_int_mm"],
                            product["E_face_MPa"], product["G_core_MPa"])
    EI, GA = st["EI_kNm2_per_m"], st["GA_kN_per_m"]
    uls = continuous_beam(spans_m, p_uls_kpa, EI, GA)
    sls = continuous_beam(spans_m, p_sls_kpa, EI, GA)
    Lmax = max(spans_m)
    gs = sls["governing_span"]
    n = len(spans_m)
    ref_beam = "Three-moment equation with shear flexibility (sandwich beam theory; cf. EN 14509 Annex E)"
    steps = [
        step(f"{tag}.EI", "Panel bending stiffness per m", "EI = E * A1*A2/(A1+A2) * e^2",
             f"E = {product['E_face_MPa']} MPa, t1 = {product['face_ext_mm']} mm, t2 = {product['face_int_mm']} mm, e = {fmt(st['e_mm'],2)} mm",
             EI, "kN*m2/m", "Sandwich beam theory (thin faces)"),
        step(f"{tag}.GA", "Panel shear stiffness per m", "GA = G_core * b * e^2 / d_core",
             f"G = {product['G_core_MPa']} MPa, e = {fmt(st['e_mm'],2)} mm, d_core = {fmt(st['d_core_mm'],2)} mm",
             GA, "kN/m", "Sandwich beam theory (thin faces)"),
        step(f"{tag}.Mf", "Max factored moment (span or support)", "continuous beam, UDL = pf * 1 m",
             f"{n} span(s) of {fmt(Lmax)} m max, pf = {fmt(p_uls_kpa)} kPa; sagging {fmt(uls['M_sag_max'])}, hogging {fmt(uls['M_hog_max'])}",
             max(uls["M_sag_max"], uls["M_hog_max"]), "kN*m/m", ref_beam),
        step(f"{tag}.Vf", "Max factored shear", "continuous beam, UDL = pf * 1 m", f"pf = {fmt(p_uls_kpa)} kPa",
             uls["V_max"], "kN/m", ref_beam),
        step(f"{tag}.Rf", "Max factored support reaction", "sum of end shears at support", f"pf = {fmt(p_uls_kpa)} kPa",
             uls["R_max"], "kN/m", ref_beam),
        step(f"{tag}.defl", "Max service deflection", "d = d_bending + d_shear",
             f"ps = {fmt(p_sls_kpa)} kPa; bending {fmt(gs['defl_bending']*1000,2)} mm + shear {fmt(gs['defl_shear']*1000,2)} mm in span L = {fmt(gs['L'])} m",
             sls["defl_max"] * 1000, "mm", ref_beam),
    ]
    src = "Product record (test-derived factored resistance)"
    checks = [
        check(f"{tag}.span", "Panel span vs product maximum", Lmax, product["max_span_m"], "m",
              "L <= L_max", "Product record (maximum tested span)"),
        check(f"{tag}.bending", "Panel bending", max(uls["M_sag_max"], uls["M_hog_max"]), product["Mr_kNm_per_m"],
              "kN*m/m", "Mf <= Mr", src),
        check(f"{tag}.shear", "Panel shear", uls["V_max"], product["Vr_kN_per_m"], "kN/m", "Vf <= Vr", src),
        check(f"{tag}.deflection", f"Panel deflection (L/{defl_limit:g})", gs["defl_max"] * 1000,
              gs["L"] / defl_limit * 1000, "mm", f"d <= L/{defl_limit:g}", "Project serviceability criterion"),
    ]
    if direction == "suction":
        if fasteners_per_panel_per_support < 1:
            raise ValueError("at least one fastener per panel per support is required")
        module_m = product["module_mm"] / 1000.0
        tf = uls["R_max"] * module_m / fasteners_per_panel_per_support
        steps.append(step(f"{tag}.Tf", "Factored tension per fastener", "Tf = Rf * module / n_fasteners",
                          f"{fmt(uls['R_max'])} kN/m * {fmt(module_m)} m / {fasteners_per_panel_per_support}",
                          tf, "kN", "Statics (tributary width of one panel module)"))
        checks.append(check(f"{tag}.fastener", "Fastener tension (pull-out / pull-over)", tf,
                            product["fastener_Tr_kN"], "kN", "Tf <= Tr", src))
    return {"direction": direction, "EI": EI, "GA": GA, "steps": steps, "checks": checks,
            "R_max_uls": uls["R_max"], "R_max_sls": sls["R_max"],
            "reaction_coeff": (uls["R_max"] / (p_uls_kpa * Lmax)) if p_uls_kpa > 0 else 0.0,
            "support_moments": uls["support_moments"], "reactions_uls": uls["reactions"]}
