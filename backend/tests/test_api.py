"""API / workflow tests against an isolated temporary database."""
import os, sys, json, tempfile, pathlib
_tmp = tempfile.mkdtemp()
os.environ["PANEL_STUDIO_DATA"] = _tmp
os.environ["PANEL_STUDIO_DB"] = f"sqlite:///{_tmp}/test.db"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app import models as m

SAMPLE = json.load(open(pathlib.Path(__file__).resolve().parents[1] / "sample_data" / "sample_revit_export.json"))
CO, E1, E2, MG = ({"X-User": u} for u in ("tcoord", "eng.lead", "eng.review", "manager"))


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def pid(c):
    r = c.post("/api/integrations/salesforce/opportunities/006MOCK000001/create-project", headers=CO)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_auth_and_roles(c):
    assert c.post("/api/projects", json={}).status_code == 401
    assert c.post("/api/projects", json={"name": "x", "q50_kpa": 0.4, "ref_height_m": 8, "least_plan_dim_m": 20}, headers=MG).status_code == 403
    assert c.post("/api/projects", json={"name": "x", "q50_kpa": -1, "ref_height_m": 8, "least_plan_dim_m": 20}, headers=CO).status_code == 422
    assert c.post("/api/projects", json={"name": "x"}, headers=CO).status_code == 422


def test_project_from_mock_salesforce(c, pid):
    p = c.get(f"/api/projects/{pid}").json()
    assert p["sf_opportunity_id"] == "006MOCK000001" and p["q50_kpa"] == 0.45 and p["status"] == "Setup"
    assert c.post("/api/integrations/salesforce/opportunities/006MOCK000001/create-project", headers=CO).status_code == 409


def test_model_import_derives_geometry(c, pid):
    bad = {**SAMPLE, "source": {"application": "SketchUp", "units": "mm"}}
    assert c.post(f"/api/projects/{pid}/import-model", json=bad, headers=CO).status_code == 422
    r = c.post(f"/api/projects/{pid}/import-model", json=SAMPLE, headers=CO)
    assert r.status_code == 200 and r.json()["summary"]["walls_added"] == 4
    walls = c.get(f"/api/projects/{pid}").json()["walls"]
    south = walls[0]
    assert south["length_m"] == 48.0 and south["height_m"] == 9.0 and south["max_bay_m"] == 8.0
    assert len(south["bay_offsets_m"]) == 7 and len(south["openings"]) == 4
    assert walls[1]["length_m"] == 30.0 and walls[1]["max_bay_m"] == 7.5
    # re-import is idempotent on element ids and keeps design
    r2 = c.post(f"/api/projects/{pid}/import-model", json=SAMPLE, headers=CO).json()
    assert r2["summary"]["walls_added"] == 0 and r2["summary"]["walls_updated"] == 4


def test_calculation_is_traceable_and_revisioned(c, pid):
    w = c.get(f"/api/projects/{pid}").json()["walls"][0]
    run = c.post(f"/api/walls/{w['id']}/calculate", headers=CO).json()
    assert run["created"] and run["revision"] == 1 and len(run["input_hash"]) == 64
    assert all(s["formula"] and s["unit"] and s["reference"] for s in run["results"]["steps"])
    assert all(e["status"] == "UNVERIFIED" for e in run["inputs"]["evidence"])
    again = c.post(f"/api/walls/{w['id']}/calculate", headers=CO).json()
    assert not again["created"] and again["id"] == run["id"]                 # same inputs -> same immutable run
    c.patch(f"/api/walls/{w['id']}", json={"n_spans": 5}, headers=CO)
    assert c.get(f"/api/projects/{pid}").json()["walls"][0]["latest_run"]["current"] is False
    r2 = c.post(f"/api/walls/{w['id']}/calculate", headers=CO).json()
    assert r2["created"] and r2["revision"] == 2 and r2["input_hash"] != run["input_hash"]
    assert len(c.get(f"/api/walls/{w['id']}/runs").json()) == 2
    assert c.post(f"/api/walls/{w['id']}/calculate", headers=MG).status_code == 403


def test_optimise_and_apply(c, pid):
    for w in c.get(f"/api/projects/{pid}").json()["walls"]:
        o = c.post(f"/api/walls/{w['id']}/optimize", headers=CO).json()
        assert o["result"]["best"] and o["result"]["search"]["evaluated"] > 10 and o["result"]["search"]["min_spacing_m"] == 0.9
        a = c.post(f"/api/optimizations/{o['id']}/apply", headers=CO).json()
        assert a["run"]["status"] == "PASS"
        assert a["run"]["summary"]["max_dcr"] == pytest.approx(o["result"]["best"]["max_dcr"])
    w0 = c.get(f"/api/projects/{pid}").json()["walls"][0]
    assert c.post(f"/api/walls/{w0['id']}/optimize", json={"min_spacing_m": 0.05}, headers=CO).status_code == 422
    o = c.post(f"/api/walls/{w0['id']}/optimize", json={"min_spacing_m": 1.0}, headers=CO).json()
    assert all(x["girt_spacing_m"] >= 1.0 - 1e-9 for x in o["result"]["candidates"])
    c.patch(f"/api/walls/{w0['id']}", json={"fasteners_per_support": 3}, headers=CO)
    assert c.post(f"/api/optimizations/{o['id']}/apply", headers=CO).status_code == 409   # stale optimisation refused
    c.patch(f"/api/walls/{w0['id']}", json={"fasteners_per_support": 2}, headers=CO)


def test_review_rules(c, pid):
    w0 = c.get(f"/api/projects/{pid}").json()["walls"][0]
    c.patch(f"/api/walls/{w0['id']}", json={"fasteners_per_support": 3}, headers=CO)
    assert c.post(f"/api/projects/{pid}/reviews", json={}, headers=CO).status_code == 409        # stale calc
    c.patch(f"/api/walls/{w0['id']}", json={"fasteners_per_support": 2}, headers=CO)
    c.post(f"/api/projects/{pid}/calculate", headers=CO)
    assert c.post(f"/api/projects/{pid}/integrations/sap/handoff", headers=CO).status_code == 422  # no approval yet
    rv = c.post(f"/api/projects/{pid}/reviews", json={"note": "for review"}, headers=E1).json()
    assert rv["effective_status"] == "SUBMITTED"
    assert c.post(f"/api/projects/{pid}/reviews", json={}, headers=E1).status_code == 409        # duplicate
    d = lambda h, **b: c.post(f"/api/reviews/{rv['id']}/decision", json=b, headers=h)
    assert d(CO, decision="approve_demo").status_code == 403                                     # not an engineer
    assert d(E1, decision="approve_demo").status_code == 403                                     # self-approval
    assert d(E2, decision="return", comment="").status_code == 422
    r = d(E2, decision="approve_reliance")
    assert r.status_code == 422 and r.json()["detail"]["blockers"]                               # unverified data blocks reliance
    ok = d(E2, decision="approve_demo", comment="Demo data only.")
    assert ok.status_code == 200 and ok.json()["effective_status"] == "APPROVED_DEMO"
    assert d(E2, decision="approve_demo").status_code == 409                                     # already decided
    assert c.get(f"/api/projects/{pid}").json()["status"] == "Approved (demonstration)"


def test_report_and_mock_handoffs(c, pid):
    rep = c.post(f"/api/projects/{pid}/reports", headers=CO).json()
    assert rep["status_label"] == "APPROVED - DEMONSTRATION ONLY"
    pdf = c.get(f"/api/reports/{rep['id']}/download")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and len(pdf.content) == rep["size_bytes"]
    f = c.post(f"/api/projects/{pid}/integrations/forma/publish", json={"report_id": rep["id"]}, headers=CO).json()
    assert f["mock"] and f["record"]["version"] == 1 and f["record"]["sha256"] == rep["sha256"]
    assert c.post(f"/api/projects/{pid}/integrations/forma/publish", json={"report_id": rep["id"]}, headers=CO).status_code == 409
    h = c.post(f"/api/projects/{pid}/integrations/sap/handoff", headers=CO).json()
    assert h["mock"] and h["record"]["status"] == "STAGED_NOT_TRANSMITTED"
    pl = h["record"]["payload"]
    assert pl["engineering_reliance"] is False and "NOT GRANTED" in pl["production_authorization"]
    runs = [c.get(f"/api/runs/{w['latest_run']['id']}").json() for w in c.get(f"/api/projects/{pid}").json()["walls"]]
    area = sum(r["results"]["quantities"]["net_panel_area_m2"] for r in runs)
    panel_item = next(i for i in pl["items"] if i["uom"] == "M2")
    assert panel_item["quantity"] == pytest.approx(area, abs=0.01)                               # BOM derived from runs
    s = c.post(f"/api/projects/{pid}/integrations/salesforce/sync-status", headers=CO).json()
    assert s["record"]["engineering_status"] == "Handoff staged"
    paths = [r.path for r in app.routes]
    assert not any("transmit" in p or "production" in p for p in paths)                          # no write-back endpoint exists


def test_changed_inputs_supersede_approval(c, pid):
    c.patch(f"/api/projects/{pid}", json={"q50_kpa": 0.5}, headers=CO)
    p = c.get(f"/api/projects/{pid}").json()
    assert p["revision"] == 2 and len(p["revisions"]) == 2 and p["status"] == "Design"
    assert c.get(f"/api/projects/{pid}/reviews").json()["reviews"][0]["effective_status"] == "SUPERSEDED"
    c.patch(f"/api/projects/{pid}", json={"q50_kpa": 0.45}, headers=CO)
    assert c.get(f"/api/projects/{pid}/reviews").json()["reviews"][0]["effective_status"] == "APPROVED_DEMO"


def test_library_evidence_and_revisions(c):
    prod = c.get("/api/library/products").json()[0]
    assert prod["evidence_status"] == "UNVERIFIED" and prod["derived"]["EI_kNm2_per_m"] > 0
    assert c.post(f"/api/library/products/{prod['id']}/verify", json={"evidence_ref": "Test report TR-0001 rev B"}, headers=CO).status_code == 403
    assert c.post(f"/api/library/products/{prod['id']}/verify", json={"evidence_ref": "x"}, headers=E1).status_code == 422
    v = c.post(f"/api/library/products/{prod['id']}/verify", json={"evidence_ref": "Test report TR-0001 rev B"}, headers=E1).json()
    assert v["evidence_status"] == "VERIFIED" and v["verified_by"] == "eng.lead"
    e = c.patch(f"/api/library/products/{prod['id']}", json={"Mr_kNm_per_m": 3.1}, headers=E1).json()
    assert e["evidence_status"] == "UNVERIFIED" and e["revision"] == 3                           # edit resets verification
    assert c.patch(f"/api/library/products/{prod['id']}", json={"thickness_mm": 0.5}, headers=E1).status_code == 422
    assert len(c.get(f"/api/library/products/{prod['id']}/revisions").json()) == 2
    c.patch(f"/api/library/products/{prod['id']}", json={"Mr_kNm_per_m": 3.0}, headers=E1)


def test_validation_cases(c):
    cases = c.get("/api/validation/cases").json()
    assert len(cases) >= 7 and all(x["result"]["passed"] for x in cases)
    assert c.post(f"/api/validation/cases/{cases[0]['id']}/approve", headers=CO).status_code == 403
    assert c.post(f"/api/validation/cases/{cases[0]['id']}/approve", headers=E1).json()["approved_by"] == "eng.lead"
    bad = c.post("/api/validation/cases", headers=E1, json={"title": "wrong expectation", "kind": "beam", "inputs": {"spans": [2], "w": 1, "EI": 100},
                                                            "expected": {"M_sag_max": 0.6}, "source": "deliberately wrong"}).json()
    assert bad["result"]["passed"] is False
    assert c.post(f"/api/validation/cases/{bad['id']}/approve", headers=E2).status_code == 409   # failing case cannot be approved
    with SessionLocal() as db:
        db.delete(db.get(m.ReferenceCase, bad["id"])); db.commit()


def test_reliance_approval_possible_once_everything_verified(c, pid):
    for kind in ("products", "sections", "code-values"):
        for o in c.get(f"/api/library/{kind}").json():
            c.post(f"/api/library/{kind}/{o['id']}/verify", json={"evidence_ref": "TEST FIXTURE evidence reference"}, headers=E1)
    for x in c.get("/api/validation/cases").json():
        c.post(f"/api/validation/cases/{x['id']}/approve", headers=E2)
    c.post(f"/api/projects/{pid}/calculate", headers=CO)
    info = c.get(f"/api/projects/{pid}/reviews").json()
    assert info["reliance_blockers"] == [] and info["package_ready"]
    rv = c.post(f"/api/projects/{pid}/reviews", json={}, headers=CO).json()
    r = c.post(f"/api/reviews/{rv['id']}/decision", json={"decision": "approve_reliance", "comment": "ok"}, headers=E2)
    assert r.status_code == 200 and r.json()["status"] == "APPROVED_RELIANCE"
    rep = c.post(f"/api/projects/{pid}/reports", headers=CO).json()
    assert rep["status_label"] == "APPROVED FOR ENGINEERING RELIANCE" and rep["revision"] == 2


def test_audit_chain_and_tamper_detection(c, pid):
    a = c.get(f"/api/audit?project_id={pid}").json()
    assert a["chain"]["valid"] and a["chain"]["events"] > 20
    actions = {e["action"] for e in a["events"]}
    assert {"project.create", "model.import", "calc.run", "optimize.apply", "review.submit", "review.decision", "report.generate",
            "mock.sap.handoff_staged", "mock.forma.publish"} <= actions
    with SessionLocal() as db:
        ev = db.query(m.AuditEvent).filter_by(action="review.decision").first()
        orig = ev.detail; ev.detail = {**orig, "decision": "APPROVED_RELIANCE-forged"}; db.commit()
        assert c.get("/api/audit").json()["chain"]["valid"] is False
        ev.detail = orig; db.commit()
    assert c.get("/api/audit").json()["chain"]["valid"] is True


def test_dashboard_is_computed(c, pid):
    d = c.get("/api/dashboard").json()
    assert d["projects"] >= 1 and d["walls"] == 4 and d["walls_passing"] == 4
    st = d["steel"]
    assert st["applied_optimizations"] >= 4 and st["compared_to_passing_baseline"] + st["failing_layouts_corrected"] == st["applied_optimizations"]
    assert st["saved_kg"] >= 0                                                               # corrections are never counted as savings
    assert d["prep_time"]["reduction_pct"] is None                                               # nothing entered -> nothing claimed
    c.patch(f"/api/projects/{pid}", json={"baseline_prep_hours": 16, "actual_prep_hours": 10}, headers=CO)
    assert c.get("/api/dashboard").json()["prep_time"]["reduction_pct"] == pytest.approx(37.5)
    assert all(e["verified"] == e["total"] for e in d["evidence"])
