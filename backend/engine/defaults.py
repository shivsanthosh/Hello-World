"""Default code data tables.

IMPORTANT: these are transcriptions prepared for the pilot and are stored in the
database with evidence status UNVERIFIED until the accountable engineer checks
each one against the printed standard and records the verification. The engine
never reads this module at run time; it receives the (possibly verified/edited)
database copy, so the values used are always the ones recorded in the run.
"""

CODE_DATA = {
    "nbcc.importance_factor_wind": {
        "value": {"Low": {"ULS": 0.8, "SLS": 0.75}, "Normal": {"ULS": 1.0, "SLS": 0.75},
                  "High": {"ULS": 1.15, "SLS": 0.75}, "Post-disaster": {"ULS": 1.25, "SLS": 0.75}},
        "unit": "-", "source": "NBCC 2020 Div. B Table 4.1.7.3."},
    "nbcc.wind_load_factor_uls": {
        "value": 1.4, "unit": "-", "source": "NBCC 2020 Div. B Table 4.1.3.2.-A (principal load 1.4W)"},
    "nbcc.cpcg_walls": {
        # Log-linear in tributary area between area_lo and area_hi (m2).
        "value": {"area_lo": 1.0, "area_hi": 50.0,
                  "positive": {"lo": 1.75, "hi": 1.3},
                  "negative_w": {"lo": -1.8, "hi": -1.5},
                  "negative_e": {"lo": -2.1, "hi": -1.5}},
        "unit": "-", "source": "NBCC 2020 Div. B Figure 4.1.7.6.-B (walls, cladding and secondary members)"},
    "nbcc.internal_pressure": {
        "value": {"Category 1": {"cpi_min": -0.15, "cpi_max": 0.0},
                  "Category 2": {"cpi_min": -0.45, "cpi_max": 0.3},
                  "Category 3": {"cpi_min": -0.7, "cpi_max": 0.7},
                  "cgi": 2.0},
        "unit": "-", "source": "NBCC 2020 Div. B Sentence 4.1.7.7.(1) and Table 4.1.7.7."},
    "s136.phi_b": {"value": 0.90, "unit": "-", "source": "CSA S136-16 (AISI S100-16) F1, LSD resistance factor, flexure"},
    "s136.phi_v": {"value": 0.80, "unit": "-", "source": "CSA S136-16 (AISI S100-16) G2, LSD resistance factor, shear"},
    "s136.r_through_fastened": {
        # Reduction factor R for flexural members with tension flange through-fastened
        # to sheathing/panel and compression flange laterally unbraced (suction case).
        "value": {"simple": [{"d_max_mm": 165.0, "C": 0.70, "Z": 0.70},
                             {"d_max_mm": 216.0, "C": 0.65, "Z": 0.65},
                             {"d_max_mm": 292.0, "C": 0.40, "Z": 0.50}]},
        "unit": "-", "source": "CSA S136-16 (AISI S100-16) I6.2.1, Table I6.2.1-1 (simple span)"},
    "steel.E_MPa": {"value": 203000.0, "unit": "MPa", "source": "CSA S136-16 A3 (modulus of elasticity of steel)"},
    "steel.density_kg_m3": {"value": 7850.0, "unit": "kg/m3", "source": "Physical constant, structural steel"},
    "limits.panel_deflection": {"value": 180.0, "unit": "L/x", "source": "Project serviceability criterion (default L/180); confirm per project specification"},
    "limits.girt_deflection": {"value": 180.0, "unit": "L/x", "source": "Project serviceability criterion (default L/180); confirm per project specification"},
}


def code_values() -> dict:
    """Plain {key: value} view used by the engine and tests."""
    return {k: v["value"] for k, v in CODE_DATA.items()}
