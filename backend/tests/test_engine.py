"""Engineering function tests. Expected values are independent closed-form / hand calculations."""
import math, copy
import pytest
from engine import wind, beam, panel, sections, girt, wall, optimize
from engine.trace import check, step

# ---------------------------------------------------------------- trace
def test_check_pass_fail_and_dcr():
    assert check("a", "t", 5, 10, "kN", "f", "r")["dcr"] == 0.5
    assert check("a", "t", 10, 10, "kN", "f", "r")["status"] == "PASS"
    assert check("a", "t", 10.01, 10, "kN", "f", "r")["status"] == "FAIL"
    assert check("a", "t", -12, 10, "kN", "f", "r")["dcr"] == pytest.approx(1.2)
    with pytest.raises(ValueError):
        check("a", "t", 1, 0, "kN", "f", "r")

def test_step_retains_formula_units_reference():
    s = step("x", "T", "a=b", "1=1", 1.0, "kN", "ref")
    assert all(s[k] for k in ("formula", "substitution", "unit", "reference"))

# ---------------------------------------------------------------- wind
def test_exposure_factor_open():
    assert wind.exposure_factor(10, "Open") == pytest.approx(1.0)
    assert wind.exposure_factor(20, "Open") == pytest.approx(2 ** 0.2)
    assert wind.exposure_factor(3, "Open") == pytest.approx(0.6 ** 0.2)   # h floored at 6 m
    assert wind.exposure_factor(6, "Open") >= 0.9

def test_exposure_factor_rough():
    assert wind.exposure_factor(12, "Rough") == pytest.approx(0.7)
    assert wind.exposure_factor(24, "Rough") == pytest.approx(0.7 * 2 ** 0.3)
    assert wind.exposure_factor(4, "Rough") == pytest.approx(0.7)

def test_exposure_factor_invalid():
    with pytest.raises(ValueError): wind.exposure_factor(0, "Open")
    with pytest.raises(ValueError): wind.exposure_factor(10, "Suburban")

def test_effective_area_one_third_rule():
    assert wind.effective_area(3.0, 1.0) == pytest.approx(3.0)        # width == L/3
    assert wind.effective_area(6.0, 1.0) == pytest.approx(12.0)       # width -> L/3 = 2
    assert wind.effective_area(2.0, 1.5) == pytest.approx(3.0)
    with pytest.raises(ValueError): wind.effective_area(0, 1)

def test_cpcg_interpolation(code):
    t = code["nbcc.cpcg_walls"]
    assert wind.cpcg_wall(0.5, "negative_e", t) == -2.1
    assert wind.cpcg_wall(100, "negative_e", t) == -1.5
    mid = math.sqrt(50.0)                                              # log-midpoint
    assert wind.cpcg_wall(mid, "negative_e", t) == pytest.approx(-1.8)
    assert wind.cpcg_wall(mid, "positive", t) == pytest.approx(1.525)
    assert wind.cpcg_wall(mid, "negative_w", t) == pytest.approx(-1.65)
    with pytest.raises(ValueError): wind.cpcg_wall(0, "positive", t)

def test_end_zone_width():
    assert wind.end_zone_width(30, 9) == pytest.approx(3.0)           # min(3.0, 3.6)
    assert wind.end_zone_width(100, 6) == pytest.approx(4.0)          # min(10, 2.4)=2.4 -> >= 4% of 100
    assert wind.end_zone_width(8, 3) == pytest.approx(1.0)            # floor of 1 m
    with pytest.raises(ValueError): wind.end_zone_width(-1, 3)

def test_net_pressures_hand_calc(code):
    r = wind.net_pressures(q50_kpa=0.5, importance="Normal", terrain="Open", h_m=10.0, ct=1.0,
                           internal_category="Category 2", area_m2=1.0, code=code, tag="t")
    # suction e: |-2.1 - 2.0*0.3| = 2.7 ; pressure: 1.75 + 2.0*0.45 = 2.65 ; suction w: 2.4
    assert r["cases"]["suction_e"]["p_uls"] == pytest.approx(1.4 * 1.0 * 0.5 * 1.0 * 2.7)
    assert r["cases"]["suction_e"]["p_sls"] == pytest.approx(0.75 * 0.5 * 2.7)
    assert r["cases"]["pressure"]["p_uls"] == pytest.approx(1.4 * 0.5 * 2.65)
    assert r["cases"]["suction_w"]["p_uls"] == pytest.approx(1.4 * 0.5 * 2.4)
    assert not r["warnings"]

def test_net_pressures_importance_and_warnings(code):
    kw = dict(q50_kpa=0.5, terrain="Open", h_m=25.0, ct=1.0, internal_category="Category 1", area_m2=60.0, code=code, tag="t")
    hi = wind.net_pressures(importance="Post-disaster", **kw)
    no = wind.net_pressures(importance="Normal", **kw)
    assert hi["cases"]["pressure"]["p_uls"] / no["cases"]["pressure"]["p_uls"] == pytest.approx(1.25)
    assert hi["cases"]["pressure"]["p_sls"] == pytest.approx(no["cases"]["pressure"]["p_sls"])
    assert hi["warnings"]                                              # h > 20 m flagged
    with pytest.raises(ValueError): wind.net_pressures(importance="Normal", **{**kw, "q50_kpa": 0})
    with pytest.raises(ValueError): wind.net_pressures(importance="Normal", **{**kw, "ct": 0.9})
    with pytest.raises(KeyError): wind.net_pressures(importance="Extreme", **kw)

# ---------------------------------------------------------------- beam
W, L, EI = 2.0, 3.0, 500.0

def test_single_span_closed_form():
    r = beam.continuous_beam([L], W, EI)
    assert r["M_sag_max"] == pytest.approx(W * L**2 / 8)
    assert r["V_max"] == pytest.approx(W * L / 2)
    assert r["reactions"] == pytest.approx([W * L / 2] * 2)
    assert r["defl_max"] == pytest.approx(5 * W * L**4 / (384 * EI), rel=1e-6)
    assert r["M_hog_max"] == 0

def test_single_span_with_shear_deflection():
    GA = 350.0
    r = beam.continuous_beam([L], W, EI, GA)
    assert r["defl_max"] == pytest.approx(5 * W * L**4 / (384 * EI) + W * L**2 / (8 * GA), rel=1e-6)
    assert r["M_sag_max"] == pytest.approx(W * L**2 / 8)               # statically determinate: unaffected

def test_two_span_closed_form():
    r = beam.continuous_beam([L, L], W, EI)
    assert r["M_hog_max"] == pytest.approx(W * L**2 / 8)
    assert r["reactions"] == pytest.approx([0.375 * W * L, 1.25 * W * L, 0.375 * W * L])
    assert r["M_sag_max"] == pytest.approx(9 * W * L**2 / 128)
    assert r["V_max"] == pytest.approx(0.625 * W * L)
    assert r["defl_max"] == pytest.approx(W * L**4 / (185 * EI), rel=2e-3)

def test_three_and_four_span_coefficients():
    r3 = beam.continuous_beam([L] * 3, W, EI)
    assert r3["M_hog_max"] == pytest.approx(0.100 * W * L**2)
    assert r3["reactions"] == pytest.approx([0.4 * W * L, 1.1 * W * L, 1.1 * W * L, 0.4 * W * L])
    assert r3["M_sag_max"] == pytest.approx(0.080 * W * L**2)
    r4 = beam.continuous_beam([L] * 4, W, EI)
    assert r4["M_hog_max"] == pytest.approx(3 / 28 * W * L**2)
    assert r4["R_max"] == pytest.approx(8 / 7 * W * L)

def test_two_span_sandwich_shear_relief():
    GA = 350.0
    k = 3 * EI / (L**2 * GA)
    r = beam.continuous_beam([L, L], W, EI, GA)
    assert r["M_hog_max"] == pytest.approx(W * L**2 / 8 / (1 + k))    # EN 14509-type closed form
    assert r["M_hog_max"] < W * L**2 / 8

def test_equilibrium_unequal_spans():
    spans = [2.0, 3.5, 2.7]
    r = beam.continuous_beam(spans, W, EI, 300.0)
    assert sum(r["reactions"]) == pytest.approx(W * sum(spans))
    assert r["support_moments"][0] == 0 and r["support_moments"][-1] == 0

def test_beam_linearity_and_validation():
    a = beam.continuous_beam([L, L], 1.0, EI, 300.0); b = beam.continuous_beam([L, L], 3.0, EI, 300.0)
    assert b["defl_max"] == pytest.approx(3 * a["defl_max"])
    for bad in (dict(spans=[], w=1, EI=1), dict(spans=[-1], w=1, EI=1), dict(spans=[1], w=1, EI=0),
                dict(spans=[1], w=-1, EI=1), dict(spans=[1], w=1, EI=1, GA=0)):
        with pytest.raises(ValueError): beam.continuous_beam(**bad)

# ---------------------------------------------------------------- panel
def test_sandwich_stiffness_hand_calc():
    s = panel.sandwich_stiffness(100, 0.5, 0.5, 200000, 3.5)
    assert s["e_mm"] == pytest.approx(99.5)
    assert s["EI_kNm2_per_m"] == pytest.approx(200000 * 250 * 99.5**2 / 1e9)       # 495.01
    assert s["GA_kN_per_m"] == pytest.approx(3.5 * 1000 * 99.5**2 / 99 / 1e3)      # 350.0
    with pytest.raises(ValueError): panel.sandwich_stiffness(1, 0.5, 0.5, 200000, 3.5)
    with pytest.raises(ValueError): panel.sandwich_stiffness(100, 0, 0.5, 200000, 3.5)

def test_panel_checks_single_span(product):
    r = panel.panel_checks(product=product, spans_m=[3.0], p_uls_kpa=1.5, p_sls_kpa=0.8, direction="suction",
                           defl_limit=180, fasteners_per_panel_per_support=2, tag="p")
    c = {x["id"]: x for x in r["checks"]}
    assert c["p.bending"]["demand"] == pytest.approx(1.5 * 9 / 8)
    assert c["p.shear"]["demand"] == pytest.approx(2.25)
    assert c["p.fastener"]["demand"] == pytest.approx(2.25 * 1.0 / 2)
    d = (5 * 0.8 * 81 / (384 * r["EI"]) + 0.8 * 9 / (8 * r["GA"])) * 1000
    assert c["p.deflection"]["demand"] == pytest.approx(d, rel=1e-6)
    assert c["p.deflection"]["capacity"] == pytest.approx(3000 / 180)
    assert r["reaction_coeff"] == pytest.approx(0.5)

def test_panel_pressure_has_no_fastener_check_and_span_limit(product):
    r = panel.panel_checks(product=product, spans_m=[4.0, 4.0], p_uls_kpa=1.0, p_sls_kpa=0.5, direction="pressure",
                           defl_limit=180, fasteners_per_panel_per_support=2, tag="p")
    ids = [c["id"] for c in r["checks"]]
    assert "p.fastener" not in ids
    assert next(c for c in r["checks"] if c["id"] == "p.span")["status"] == "FAIL"   # 4.0 > 3.5 max

def test_panel_refuses_missing_capacity(product):
    p = dict(product); p["Mr_kNm_per_m"] = None
    with pytest.raises(ValueError, match="missing required engineering data"):
        panel.panel_checks(product=p, spans_m=[2.0], p_uls_kpa=1, p_sls_kpa=1, direction="pressure",
                           defl_limit=180, fasteners_per_panel_per_support=2, tag="p")
    with pytest.raises(ValueError):
        panel.panel_checks(product=product, spans_m=[2.0], p_uls_kpa=1, p_sls_kpa=1, direction="suction",
                           defl_limit=180, fasteners_per_panel_per_support=0, tag="p")
    with pytest.raises(ValueError):
        panel.panel_checks(product=product, spans_m=[2.0], p_uls_kpa=1, p_sls_kpa=1, direction="up",
                           defl_limit=180, fasteners_per_panel_per_support=1, tag="p")

# ---------------------------------------------------------------- sections
def test_lipped_section_hand_calc():
    # D=200, B=75, C=20, t=2 -> h=198, b=73, c=19
    p = sections.lipped_section("Z", 200, 75, 20, 2)
    A = 2 * (198 + 146 + 38)
    Ix = 2 * 198**3 / 12 + 2 * (73 * 2 * 99**2 + 73 * 8 / 12) + 2 * (2 * 19**3 / 12 + 19 * 2 * (99 - 9.5)**2)
    assert p["A_mm2"] == pytest.approx(A)
    assert p["Ix_mm4"] == pytest.approx(Ix)
    assert p["Sx_mm3"] == pytest.approx(Ix / 100)
    assert p["mass_kg_per_m"] == pytest.approx(A * 1e-6 * 7850)
    assert p["h_over_t"] == pytest.approx(98)
    assert sections.lipped_section("C", 200, 75, 20, 2)["Ix_mm4"] == pytest.approx(Ix)

def test_lipped_section_validation():
    for a in (("L", 200, 75, 20, 2), ("Z", 0, 75, 20, 2), ("Z", 200, 75, -1, 2), ("Z", 200, 75, 20, 40), ("Z", 60, 75, 40, 2)):
        with pytest.raises(ValueError): sections.lipped_section(*a)

# ---------------------------------------------------------------- girt
def test_shear_stress_three_regimes():
    E, Fy = 203000.0, 345.0
    lim = math.sqrt(E * 5.34 / Fy)                                     # 56.05
    assert girt.shear_stress_Fv(40, Fy, E) == pytest.approx(0.6 * Fy)
    assert girt.shear_stress_Fv(70, Fy, E) == pytest.approx(0.6 * math.sqrt(E * 5.34 * Fy) / 70)
    assert girt.shear_stress_Fv(120, Fy, E) == pytest.approx(math.pi**2 * E * 5.34 / (12 * 0.91 * 120**2))
    assert girt.shear_stress_Fv(lim, Fy, E) == pytest.approx(0.6 * Fy)
    with pytest.raises(ValueError): girt.shear_stress_Fv(0, Fy, E)

def test_r_factor_table(code):
    t = code["s136.r_through_fastened"]
    assert girt.r_factor("Z", 152, t) == 0.70
    assert girt.r_factor("Z", 203, t) == 0.65
    assert girt.r_factor("Z", 254, t) == 0.50
    assert girt.r_factor("C", 254, t) == 0.40
    with pytest.raises(ValueError): girt.r_factor("Z", 305, t)

def test_girt_checks_hand_calc(code, section):
    pr = sections.lipped_section("Z", 203, 70, 20, 1.9)
    g = girt.girt_checks(section=section, span_m=8.0, w_uls_kN_m=2.0, w_sls_kN_m=1.0, direction="pressure", code=code, tag="g")
    c = {x["id"]: x for x in g["checks"]}
    assert c["g.bending"]["demand"] == pytest.approx(16.0)
    assert c["g.bending"]["capacity"] == pytest.approx(0.9 * pr["Sx_mm3"] * 345 / 1e6)
    assert c["g.shear"]["demand"] == pytest.approx(8.0)
    assert c["g.deflection"]["demand"] == pytest.approx(5 * 1.0 * 8**4 / (384 * 203000 * pr["Ix_mm4"] / 1e9) * 1000)
    assert c["g.deflection"]["capacity"] == pytest.approx(8000 / 180)
    s = girt.girt_checks(section=section, span_m=8.0, w_uls_kN_m=2.0, w_sls_kN_m=1.0, direction="suction", code=code, tag="g")
    assert s["checks"][0]["capacity"] == pytest.approx(0.65 * c["g.bending"]["capacity"])
    with pytest.raises(ValueError):
        girt.girt_checks(section=section, span_m=0, w_uls_kN_m=1, w_sls_kN_m=1, direction="pressure", code=code, tag="g")
    with pytest.raises(ValueError):
        girt.girt_checks(section=section, span_m=5, w_uls_kN_m=1, w_sls_kN_m=1, direction="sideways", code=code, tag="g")

# ---------------------------------------------------------------- wall
def test_girt_elevations():
    assert wall.girt_elevations(9.0, 4) == [2.25, 4.5, 6.75, 9.0]
    with pytest.raises(ValueError): wall.girt_elevations(9.0, 0)

def test_takeoff_hand_calc(wall_inp):
    q = wall.takeoff(wall=wall_inp["wall"], n_spans=4, product=wall_inp["product"], section=wall_inp["section"],
                     fasteners_per_support=2, density=7850)
    assert q["panel_count"] == 48
    assert q["net_panel_area_m2"] == pytest.approx(48 * 9 - 3.6 * 4.2)
    # girts at 2.25 (crosses door 0-4.2), 4.5, 6.75, 9.0 -> 48*4 - 3.6
    assert q["girt_length_m"] == pytest.approx(188.4)
    assert q["opening_framing_length_m"] == pytest.approx(2 * 4.2 + 3.6)            # door: no sill member
    assert q["secondary_steel_mass_kg"] == pytest.approx((188.4 + 12.0) * q["steel_mass_kg_per_m"])
    assert q["fastener_count"] == 48 * 5 * 2
    bad = copy.deepcopy(wall_inp["wall"]); bad["openings"] = [{"offset_m": 0, "width_m": 48, "sill_m": 0, "height_m": 9}]
    with pytest.raises(ValueError):
        wall.takeoff(wall=bad, n_spans=4, product=wall_inp["product"], section=wall_inp["section"], fasteners_per_support=2, density=7850)

def test_design_wall_consistent_with_components(wall_inp, code):
    r = wall.design_wall(wall_inp)
    assert r["girt_spacing_m"] == pytest.approx(2.25)
    assert r["end_zone_width_m"] == pytest.approx(3.0)
    # panel suction pressure recomputed independently: A = 2.25 * max(1.0, 0.75) = 2.25 m2
    ce = 0.9 ** 0.2
    cp = -2.1 + (math.log10(2.25) / math.log10(50)) * 0.6
    p = 1.4 * 0.45 * ce * abs(cp - 0.6)
    assert r["pressures"]["panel"]["suction_e"]["p_uls"] == pytest.approx(p)
    b = beam.continuous_beam([2.25] * 4, p, r and panel.sandwich_stiffness(100, .5, .5, 200000, 3.5)["EI_kNm2_per_m"],
                             panel.sandwich_stiffness(100, .5, .5, 200000, 3.5)["GA_kN_per_m"])
    c = {x["id"]: x for x in r["checks"]}
    assert c["panel.suction.bending"]["demand"] == pytest.approx(max(b["M_sag_max"], b["M_hog_max"]))
    assert c["panel.suction.fastener"]["demand"] == pytest.approx(b["R_max"] * 1.0 / 2)
    assert len(r["checks"]) == 4 + 5 + 3 + 3
    assert r["summary"]["max_dcr"] == max(x["dcr"] for x in r["checks"])
    assert all(s["formula"] and s["unit"] and s["reference"] for s in r["steps"])

def test_design_wall_deterministic_and_validates(wall_inp):
    assert wall.design_wall(wall_inp) == wall.design_wall(copy.deepcopy(wall_inp))
    for path, val in ((("wall", "height_m"), 0), (("wall", "max_bay_m"), 0), (("design", "n_spans"), 0)):
        bad = copy.deepcopy(wall_inp); bad[path[0]][path[1]] = val
        with pytest.raises(ValueError): wall.design_wall(bad)

def test_higher_wind_increases_dcr(wall_inp):
    hi = copy.deepcopy(wall_inp); hi["site"]["q50_kpa"] = 0.9
    assert wall.design_wall(hi)["summary"]["max_dcr"] > wall.design_wall(wall_inp)["summary"]["max_dcr"]

# ---------------------------------------------------------------- optimise
SECS = [{"id": i, "name": n, "shape": "Z", "depth_mm": d, "flange_mm": 70.0, "lip_mm": 20.0, "t_mm": t, "Fy_MPa": 345.0}
        for i, (n, d, t) in enumerate([("Z152x1.5", 152.0, 1.52), ("Z203x1.9", 203.0, 1.9), ("Z254x2.7", 254.0, 2.67)], 1)]

def test_optimiser_best_is_feasible_and_minimal(wall_inp):
    r = optimize.optimise_wall(wall_inp, SECS)
    assert r["search"]["evaluated"] == len(r["candidates"]) == (r["search"]["n_spans_max"] - r["search"]["n_spans_min"] + 1) * 3
    assert r["search"]["n_spans_min"] == 3                              # ceil(9 / 3.5)
    best = r["best"]; assert best and best["feasible"]
    feas = [c for c in r["candidates"] if c["feasible"]]
    assert best["steel_mass_kg"] == pytest.approx(min(c["steel_mass_kg"] for c in feas))
    # re-run the engine on the winner: must pass
    sec = next(s for s in SECS if s["id"] == best["section_id"])
    chk = wall.design_wall({**wall_inp, "design": {**wall_inp["design"], "n_spans": best["n_spans"]}, "section": sec})
    assert chk["summary"]["status"] == "PASS"
    assert chk["quantities"]["secondary_steel_mass_kg"] == pytest.approx(best["steel_mass_kg"])
    diff = r["baseline"]["steel_mass_kg"] - best["steel_mass_kg"]
    if r["baseline"]["feasible"]:
        assert r["steel_saving_kg"] == pytest.approx(diff) and r["steel_added_for_compliance_kg"] is None
    else:   # a failing baseline must never be reported as a saving
        assert r["steel_saving_kg"] is None and r["steel_added_for_compliance_kg"] == pytest.approx(-diff)

def test_optimiser_saving_vs_passing_baseline(wall_inp):
    heavy = copy.deepcopy(wall_inp); heavy["design"]["n_spans"] = 10; heavy["section"] = SECS[2]
    assert wall.design_wall(heavy)["summary"]["status"] == "PASS"
    r = optimize.optimise_wall(heavy, SECS)
    assert r["baseline"]["feasible"] and r["steel_saving_kg"] >= 0 and r["steel_added_for_compliance_kg"] is None
    assert r["steel_saving_pct"] == pytest.approx(r["steel_saving_kg"] / r["baseline"]["steel_mass_kg"] * 100)

def test_optimiser_respects_min_spacing(wall_inp):
    r = optimize.optimise_wall(wall_inp, SECS, min_spacing_m=1.5)
    assert r["search"]["n_spans_max"] == 6 and all(c["girt_spacing_m"] >= 1.5 - 1e-9 for c in r["candidates"])
    tight = optimize.optimise_wall(wall_inp, SECS, min_spacing_m=4.0)       # 9/4 -> n<=2 but panel needs n>=3
    assert tight["candidates"] == [] and tight["best"] is None and tight["note"]
    with pytest.raises(ValueError): optimize.optimise_wall(wall_inp, SECS, min_spacing_m=0.1)

def test_optimiser_reports_infeasible(wall_inp):
    hard = copy.deepcopy(wall_inp); hard["site"]["q50_kpa"] = 6.0
    r = optimize.optimise_wall(hard, SECS)
    assert r["best"] is None and r["steel_saving_kg"] is None
    assert all(c["failed_checks"] for c in r["candidates"])
    with pytest.raises(ValueError): optimize.optimise_wall(wall_inp, [])
