"""Baseline seed: users, library, code tables, reference cases and mock enterprise records.

Nothing here is a calculated result. Product strengths are ILLUSTRATIVE placeholders, stored
as UNVERIFIED so every run that uses them is flagged and cannot be approved for reliance.
"""
from sqlalchemy.orm import Session
from engine.defaults import CODE_DATA
from . import models as m

DEMO_SRC = ("ILLUSTRATIVE DEMO VALUE - not manufacturer data. Replace with the company's tested/approved "
            "values and record the test report or approval reference before any engineering reliance.")


def seed(db: Session):
    if db.query(m.User).count():
        return
    db.add_all([
        m.User(username="tcoord", name="Taylor Coordinator", title="Technical Coordinator", role="coordinator"),
        m.User(username="eng.lead", name="Erin Lead, P.Eng.", title="Accountable Engineering Lead", role="engineer"),
        m.User(username="eng.review", name="Robin Reviewer, P.Eng.", title="Reviewing Engineer", role="engineer"),
        m.User(username="manager", name="Morgan Manager", title="Engineering Manager (read-only)", role="manager"),
    ])
    for name, t, mr, vr, span, mass in (("PS-IMP-075", 75.0, 3.0, 6.0, 3.0, 11.0), ("PS-IMP-100", 100.0, 4.0, 8.0, 3.6, 12.0),
                                        ("PS-IMP-150", 150.0, 6.0, 12.0, 4.5, 14.0)):
        db.add(m.Product(name=name, description=f"{t:.0f} mm PIR-core insulated metal wall panel (demo record)",
                         thickness_mm=t, module_mm=1067.0, face_ext_mm=0.5, face_int_mm=0.5, E_face_MPa=200000.0,
                         G_core_MPa=3.5, Mr_kNm_per_m=mr, Vr_kN_per_m=vr, fastener_Tr_kN=2.0, max_span_m=span,
                         mass_kg_m2=mass, source=DEMO_SRC))
    for d, b, c, ts in ((152.0, 64.0, 19.0, (1.52, 1.90)), (203.0, 70.0, 20.0, (1.52, 1.90, 2.67)), (254.0, 76.0, 22.0, (1.90, 2.67))):
        for t in ts:
            db.add(m.Section(name=f"Z{d:.0f}x{b:.0f}x{t:.2f}", shape="Z", depth_mm=d, flange_mm=b, lip_mm=c, t_mm=t, Fy_MPa=345.0,
                             source="Generic nominal Z-girt geometry; confirm against the girt supplier's section tables and mill grade."))
    for k, v in CODE_DATA.items():
        db.add(m.CodeValue(key=k, value={"v": v["value"]}, unit=v["unit"], source=v["source"]))
    W, L, EI = 2.0, 3.0, 500.0
    cases = [
        ("Simply supported beam, UDL", "beam", {"spans": [L], "w": W, "EI": EI},
         {"M_sag_max": W * L**2 / 8, "V_max": W * L / 2, "defl_max": 5 * W * L**4 / (384 * EI)},
         "Closed form: M = wL^2/8, V = wL/2, d = 5wL^4/384EI"),
        ("Two equal spans, UDL", "beam", {"spans": [L, L], "w": W, "EI": EI},
         {"M_hog_max": W * L**2 / 8, "R_max": 1.25 * W * L, "M_sag_max": 9 * W * L**2 / 128},
         "Closed form: M_support = wL^2/8, R_centre = 1.25wL, M_span = 9wL^2/128"),
        ("Three equal spans, UDL", "beam", {"spans": [L, L, L], "w": W, "EI": EI},
         {"M_hog_max": 0.1 * W * L**2, "R_max": 1.1 * W * L, "M_sag_max": 0.08 * W * L**2},
         "Standard beam coefficients: 0.100, 1.100, 0.080"),
        ("Two-span sandwich panel, shear-flexible core", "beam", {"spans": [L, L], "w": W, "EI": EI, "GA": 350.0},
         {"M_hog_max": W * L**2 / 8 / (1 + 3 * EI / (L**2 * 350.0))},
         "Sandwich theory: M_support = (wL^2/8)/(1+k), k = 3EI/(L^2 GA)"),
        ("Sandwich stiffness, 100 mm panel, 0.5 mm faces", "sandwich",
         {"thickness_mm": 100, "face_ext_mm": 0.5, "face_int_mm": 0.5, "E_face_MPa": 200000, "G_core_MPa": 3.5},
         {"EI_kNm2_per_m": 200000 * 250 * 99.5**2 / 1e9, "GA_kN_per_m": 3.5 * 1000 * 99.5**2 / 99 / 1e3},
         "Hand calculation: EI = E(A1A2/(A1+A2))e^2, GA = G b e^2/dc"),
        ("Lipped Z 200x75x20x2.0 gross properties", "section",
         {"shape": "Z", "depth_mm": 200, "flange_mm": 75, "lip_mm": 20, "t_mm": 2},
         {"A_mm2": 764.0, "Ix_mm4": 2 * 198**3 / 12 + 2 * (73 * 2 * 99**2 + 73 * 8 / 12) + 2 * (2 * 19**3 / 12 + 38 * 89.5**2)},
         "Hand calculation, thin-wall centreline method"),
        ("Exposure factor, open terrain, h = 20 m", "wind_ce", {"h_m": 20, "terrain": "Open"}, {"ce": 2 ** 0.2},
         "NBCC 2020 4.1.7.3.(5): Ce = (h/10)^0.2"),
    ]
    for title, kind, inp, exp, src in cases:
        db.add(m.ReferenceCase(title=title, kind=kind, inputs=inp, expected=exp, source=src))
    site = lambda q, loc, h, d: {"q50_kpa": q, "location": loc, "ref_height_m": h, "least_plan_dim_m": d,
                                 "importance": "Normal", "terrain": "Open", "internal_category": "Category 2"}
    db.add_all([
        m.MockSfOpportunity(sf_id="006MOCK000001", name="Northfield Cold Storage - Phase 1", account="Northfield Logistics (mock)",
                            stage="Technical Review", amount_cad=1850000, site=site(0.45, "Ottawa, ON", 9.0, 30.0)),
        m.MockSfOpportunity(sf_id="006MOCK000002", name="Prairie Food Processing Expansion", account="Prairie Foods (mock)",
                            stage="Proposal", amount_cad=920000, site=site(0.49, "Regina, SK", 7.5, 24.0)),
        m.MockSfOpportunity(sf_id="006MOCK000003", name="Harbour Distribution Centre", account="Harbour DC (mock)",
                            stage="Qualification", amount_cad=3100000, site=site(0.58, "Halifax, NS", 12.0, 60.0)),
    ])
    db.flush()
    for i, p in enumerate(db.query(m.Product).all(), 1):
        db.add(m.MockSapMaterial(material_no=f"MOCK-FG-{1000+i}", description=p.description, kind="product", ref_name=p.name, uom="M2"))
    for i, s in enumerate(db.query(m.Section).all(), 1):
        db.add(m.MockSapMaterial(material_no=f"MOCK-RM-{2000+i}", description=f"Cold-formed girt {s.name}", kind="section", ref_name=s.name, uom="M"))
    db.add(m.MockSapMaterial(material_no="MOCK-HW-3001", description="Panel fastener, self-drilling (demo)", kind="fastener", ref_name="fastener", uom="EA"))
    db.commit()
