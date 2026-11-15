"""Panel Studio API. Engineering results come only from the deterministic engine; integrations are mocks."""
from __future__ import annotations
import os, base64, secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, Body
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from engine import ENGINE_VERSION
from engine.optimize import optimise_wall, DEFAULT_MIN_SPACING_M
from engine.sections import lipped_section
from engine.panel import sandwich_stiffness
from . import models as m, services as sv
from .db import Base, engine as db_engine, get_db, SessionLocal, DATA_DIR
from .seed import seed
from .reports import build_report

MOCK_NOTE = "SIMULATED SYSTEM - mock records stored locally in Panel Studio; no connection to a live enterprise tenant."


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(db_engine)
    with SessionLocal() as db:
        seed(db)
    yield

app = FastAPI(title="Panel Studio", version=ENGINE_VERSION, lifespan=lifespan)


@app.middleware("http")
async def shared_password_gate(request, call_next):
    """Optional shared-password gate for hosted demos (HTTP Basic; any username).

    Active only when PANEL_STUDIO_PASSWORD is set. This keeps a demo URL private; it is NOT
    user authentication - production still requires enterprise SSO. /healthz stays open for the host.
    """
    pw = os.environ.get("PANEL_STUDIO_PASSWORD")
    if pw and request.url.path != "/healthz":
        ok = False
        h = request.headers.get("authorization", "")
        if h.lower().startswith("basic "):
            try:
                ok = secrets.compare_digest(base64.b64decode(h[6:]).decode().partition(":")[2], pw)
            except Exception:
                ok = False
        if not ok:
            return Response("Password required", status_code=401, headers={"WWW-Authenticate": 'Basic realm="Panel Studio demo"'})
    return await call_next(request)


@app.get("/healthz")
def healthz():
    return {"ok": True}
D = Depends(get_db)


def current_user(x_user: str = Header(default=""), db: Session = D) -> m.User:
    u = db.query(m.User).filter_by(username=x_user).first()
    if not u:
        raise HTTPException(401, "unknown or missing user (X-User header)")
    return u

U = Depends(current_user)


def need(user: m.User, *roles: str):
    if user.role not in roles:
        raise HTTPException(403, f"role '{user.role}' may not perform this action (requires: {', '.join(roles)})")


def get_project(db, pid) -> m.Project:
    p = db.get(m.Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


def get_wall(db, wid) -> m.Wall:
    w = db.get(m.Wall, wid)
    if not w:
        raise HTTPException(404, "wall not found")
    return w


def run_view(r: m.CalcRun, full=True):
    d = m.to_dict(r)
    if not full:
        d.pop("inputs"); d["summary"] = d.pop("results")["summary"]
    return d


def wall_view(db, p, w: m.Wall):
    d = m.to_dict(w)
    run = db.query(m.CalcRun).filter_by(wall_id=w.id).order_by(m.CalcRun.revision.desc()).first()
    d["latest_run"] = None
    if run:
        cur = run.input_hash == sv.input_hash(sv.build_inputs(db, p, w))
        d["latest_run"] = {"id": run.id, "revision": run.revision, "status": run.status, "max_dcr": run.max_dcr, "current": cur,
                           "girt_elevations_m": run.results["girt_elevations_m"], "end_zone_width_m": run.results["end_zone_width_m"]}
    return d


def project_view(db, p: m.Project):
    d = m.to_dict(p)
    d["status"] = sv.project_status(db, p)
    d["wall_count"] = db.query(m.Wall).filter_by(project_id=p.id).count()
    return d


# ------------------------------------------------------------------ users / meta
@app.get("/api/meta")
def meta():
    return {"engine_version": ENGINE_VERSION, "auth_note": "Demo identity switch only - production requires enterprise SSO.",
            "importance": ["Low", "Normal", "High", "Post-disaster"], "terrain": ["Open", "Rough"],
            "internal_category": ["Category 1", "Category 2", "Category 3"]}


@app.get("/api/users")
def users(db: Session = D):
    return [m.to_dict(u) for u in db.query(m.User).order_by(m.User.id)]


# ------------------------------------------------------------------ projects
PROJECT_FIELDS = {"name": str, "client": str, "location": str, "q50_kpa": float, "importance": str, "terrain": str, "ref_height_m": float,
                  "ct": float, "internal_category": str, "least_plan_dim_m": float, "climate_source": str,
                  "baseline_prep_hours": float, "actual_prep_hours": float}


def apply_project_fields(p: m.Project, body: dict):
    mt = meta()
    for k, typ in PROJECT_FIELDS.items():
        if k in body:
            v = body[k]
            if v is None or v == "":
                if k in ("baseline_prep_hours", "actual_prep_hours", "client", "location", "climate_source"):
                    setattr(p, k, None if typ is float else ""); continue
                raise HTTPException(422, f"{k} is required")
            try:
                v = typ(v)
            except (TypeError, ValueError):
                raise HTTPException(422, f"{k} must be a {typ.__name__}")
            if k in ("importance", "terrain", "internal_category") and v not in mt[k]:
                raise HTTPException(422, f"{k} must be one of {mt[k]}")
            if k in ("q50_kpa", "ref_height_m", "least_plan_dim_m") and v <= 0:
                raise HTTPException(422, f"{k} must be positive")
            if k == "ct" and v < 1.0:
                raise HTTPException(422, "ct cannot be less than 1.0")
            if k in ("baseline_prep_hours", "actual_prep_hours") and v < 0:
                raise HTTPException(422, f"{k} cannot be negative")
            setattr(p, k, v)


def create_project(db, user, body, sf_id=None) -> m.Project:
    need(user, "coordinator", "engineer")
    for k in ("name", "q50_kpa", "ref_height_m", "least_plan_dim_m"):
        if body.get(k) in (None, ""):
            raise HTTPException(422, f"{k} is required")
    n = db.query(m.Project).count() + 1
    p = m.Project(number=f"PS-{m.now().year}-{n:04d}", name="", q50_kpa=0, ref_height_m=0, least_plan_dim_m=0,
                  created_by=user.username, sf_opportunity_id=sf_id)
    apply_project_fields(p, body)
    db.add(p); db.flush()
    sv.snapshot(db, user, "project", p, "created")
    sv.audit(db, user, "project.create", p.id, f"project:{p.id}", {"number": p.number, "name": p.name, "sf_opportunity_id": sf_id})
    return p


@app.get("/api/projects")
def list_projects(db: Session = D):
    return [project_view(db, p) for p in db.query(m.Project).order_by(m.Project.id.desc())]


@app.post("/api/projects")
def post_project(body: dict = Body(...), db: Session = D, user: m.User = U):
    p = create_project(db, user, body); db.commit()
    return project_view(db, p)


@app.get("/api/projects/{pid}")
def get_project_api(pid: int, db: Session = D):
    p = get_project(db, pid)
    d = project_view(db, p)
    d["walls"] = [wall_view(db, p, w) for w in db.query(m.Wall).filter_by(project_id=pid).order_by(m.Wall.id)]
    imp = db.query(m.ModelImport).filter_by(project_id=pid).order_by(m.ModelImport.id.desc()).first()
    d["model_import"] = m.to_dict(imp) if imp else None
    d["revisions"] = [m.to_dict(r) for r in db.query(m.Revision).filter_by(entity_type="project", entity_id=pid).order_by(m.Revision.id.desc())]
    return d


@app.patch("/api/projects/{pid}")
def patch_project(pid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid)
    before = m.to_dict(p)
    apply_project_fields(p, body)
    after = m.to_dict(p)
    changed = {k: [before[k], after[k]] for k in after if before[k] != after[k]}
    if changed:
        p.revision += 1
        sv.snapshot(db, user, "project", p, "edited: " + ", ".join(changed))
        sv.audit(db, user, "project.update", pid, f"project:{pid}", {"changed": changed, "revision": p.revision})
    db.commit()
    return project_view(db, p)


@app.post("/api/projects/{pid}/import-model")
def import_model(pid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    imp = sv.import_model(db, user, get_project(db, pid), body); db.commit()
    return m.to_dict(imp)


@app.get("/api/sample-model")
def sample_model():
    return FileResponse(os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data", "sample_revit_export.json"),
                        media_type="application/json")


# ------------------------------------------------------------------ walls / calculations
@app.patch("/api/walls/{wid}")
def patch_wall(wid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    w = get_wall(db, wid)
    changed = {}
    for k in ("product_id", "section_id", "n_spans", "fasteners_per_support"):
        if k in body and body[k] != getattr(w, k):
            v = int(body[k])
            if k in ("n_spans", "fasteners_per_support") and not 1 <= v <= 16:
                raise HTTPException(422, f"{k} must be between 1 and 16")
            if k == "product_id" and not db.get(m.Product, v):
                raise HTTPException(422, "unknown product")
            if k == "section_id" and not db.get(m.Section, v):
                raise HTTPException(422, "unknown section")
            changed[k] = [getattr(w, k), v]; setattr(w, k, v)
    if changed:
        sv.audit(db, user, "wall.design_change", w.project_id, f"wall:{w.id}", {"wall": w.name, "changed": changed})
    db.commit()
    return wall_view(db, get_project(db, w.project_id), w)


@app.post("/api/walls/{wid}/calculate")
def calculate(wid: int, db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    w = get_wall(db, wid)
    run, created = sv.run_calc(db, user, get_project(db, w.project_id), w); db.commit()
    return {**run_view(run), "created": created}


@app.post("/api/projects/{pid}/calculate")
def calculate_all(pid: int, db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid); out = []
    for w in db.query(m.Wall).filter_by(project_id=pid).order_by(m.Wall.id):
        run, created = sv.run_calc(db, user, p, w)
        out.append({**run_view(run, False), "created": created})
    db.commit()
    return out


@app.get("/api/walls/{wid}/runs")
def wall_runs(wid: int, db: Session = D):
    return [run_view(r, False) for r in db.query(m.CalcRun).filter_by(wall_id=wid).order_by(m.CalcRun.revision.desc())]


@app.get("/api/runs/{rid}")
def get_run(rid: int, db: Session = D):
    r = db.get(m.CalcRun, rid)
    if not r:
        raise HTTPException(404, "run not found")
    return run_view(r)


# ------------------------------------------------------------------ optimisation
@app.post("/api/walls/{wid}/optimize")
def optimize(wid: int, body: dict = Body(default={}), db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    w = get_wall(db, wid); p = get_project(db, w.project_id)
    inputs = sv.build_inputs(db, p, w)
    secs = [{k: getattr(s, k) for k in ("id", "name", "shape", "depth_mm", "flange_mm", "lip_mm", "t_mm", "Fy_MPa")}
            for s in db.query(m.Section).order_by(m.Section.id)]
    try:
        res = optimise_wall(inputs, secs, float(body.get("min_spacing_m") or DEFAULT_MIN_SPACING_M))
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(422, f"optimisation refused: {e}")
    o = m.OptimizationRun(project_id=p.id, wall_id=w.id, wall_name=w.name, input_hash=sv.input_hash(inputs), result=res, created_by=user.username)
    db.add(o); db.flush()
    sv.audit(db, user, "optimize.run", p.id, f"wall:{w.id}", {"optimization_id": o.id, "evaluated": res["search"]["evaluated"],
             "feasible": res["search"]["feasible"], "best": res["best"] and {k: res["best"][k] for k in ("n_spans", "section_name", "steel_mass_kg")},
             "min_spacing_m": res["search"]["min_spacing_m"], "steel_saving_kg": res["steel_saving_kg"],
             "steel_added_for_compliance_kg": res["steel_added_for_compliance_kg"]})
    db.commit()
    return m.to_dict(o)


@app.get("/api/walls/{wid}/optimizations")
def wall_opts(wid: int, db: Session = D):
    return [m.to_dict(o) for o in db.query(m.OptimizationRun).filter_by(wall_id=wid).order_by(m.OptimizationRun.id.desc()).limit(5)]


@app.post("/api/optimizations/{oid}/apply")
def apply_opt(oid: int, db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    o = db.get(m.OptimizationRun, oid)
    if not o:
        raise HTTPException(404, "optimisation not found")
    w = get_wall(db, o.wall_id); p = get_project(db, o.project_id)
    if sv.input_hash(sv.build_inputs(db, p, w)) != o.input_hash:
        raise HTTPException(409, "wall inputs changed since this optimisation was run; re-run the optimisation")
    best = o.result["best"]
    if not best:
        raise HTTPException(422, "optimisation found no feasible layout; nothing to apply")
    w.n_spans, w.section_id = best["n_spans"], best["section_id"]
    o.applied, o.applied_by, o.applied_at = True, user.username, m.now()
    sv.audit(db, user, "optimize.apply", p.id, f"wall:{w.id}", {"optimization_id": o.id, "n_spans": best["n_spans"], "section": best["section_name"]})
    run, _ = sv.run_calc(db, user, p, w); db.commit()
    return {"optimization": m.to_dict(o), "run": run_view(run, False)}


# ------------------------------------------------------------------ library & evidence
LIB = {"products": (m.Product, "product", ("description", "thickness_mm", "module_mm", "face_ext_mm", "face_int_mm", "E_face_MPa", "G_core_MPa",
                                           "Mr_kNm_per_m", "Vr_kN_per_m", "fastener_Tr_kN", "max_span_m", "mass_kg_m2", "source")),
       "sections": (m.Section, "section", ("shape", "depth_mm", "flange_mm", "lip_mm", "t_mm", "Fy_MPa", "source")),
       "code-values": (m.CodeValue, "code", ("value", "source"))}


def lib_view(kind, o):
    d = m.to_dict(o)
    if kind == "products":
        try:
            d["derived"] = sandwich_stiffness(o.thickness_mm, o.face_ext_mm, o.face_int_mm, o.E_face_MPa, o.G_core_MPa)
        except ValueError as e:
            d["derived"] = {"error": str(e)}
    if kind == "sections":
        try:
            d["derived"] = lipped_section(o.shape, o.depth_mm, o.flange_mm, o.lip_mm, o.t_mm)
        except ValueError as e:
            d["derived"] = {"error": str(e)}
    if kind == "code-values":
        d["value"] = o.value["v"]
    return d


@app.get("/api/library/{kind}")
def lib_list(kind: str, db: Session = D):
    if kind not in LIB:
        raise HTTPException(404, "unknown library")
    return [lib_view(kind, o) for o in db.query(LIB[kind][0]).order_by(LIB[kind][0].id)]


@app.patch("/api/library/{kind}/{oid}")
def lib_patch(kind: str, oid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "engineer")
    Model, etype, fields = LIB[kind]
    o = db.get(Model, oid)
    if not o:
        raise HTTPException(404, "record not found")
    changed = {}
    for k in fields:
        if k in body:
            new = {"v": body[k]} if (kind == "code-values" and k == "value") else body[k]
            if new != getattr(o, k):
                changed[k] = [getattr(o, k), new]; setattr(o, k, new)
    if changed:
        try:   # reject edits that make the record unusable
            if kind == "products": sandwich_stiffness(o.thickness_mm, o.face_ext_mm, o.face_int_mm, o.E_face_MPa, o.G_core_MPa)
            if kind == "sections": lipped_section(o.shape, o.depth_mm, o.flange_mm, o.lip_mm, o.t_mm)
        except (ValueError, TypeError) as e:
            db.rollback(); raise HTTPException(422, str(e))
        o.revision += 1
        o.evidence_status, o.evidence_ref, o.verified_by, o.verified_at = m.UNVERIFIED, "", None, None
        sv.snapshot(db, user, etype, o, "edited: " + ", ".join(changed))
        sv.audit(db, user, "library.update", None, f"{etype}:{o.id}", {"changed": changed, "revision": o.revision, "evidence_reset": True})
    db.commit()
    return lib_view(kind, o)


@app.post("/api/library/{kind}/{oid}/verify")
def lib_verify(kind: str, oid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "engineer")
    Model, etype, _ = LIB[kind]
    o = db.get(Model, oid)
    if not o:
        raise HTTPException(404, "record not found")
    ref = (body.get("evidence_ref") or "").strip()
    if len(ref) < 10:
        raise HTTPException(422, "an evidence reference (test report, approval or code clause checked, min. 10 characters) is required")
    o.revision += 1
    o.evidence_status, o.evidence_ref, o.verified_by, o.verified_at = m.VERIFIED, ref, user.username, m.now()
    sv.snapshot(db, user, etype, o, "verified")
    sv.audit(db, user, "library.verify", None, f"{etype}:{o.id}", {"name": getattr(o, "name", getattr(o, "key", "")), "evidence_ref": ref, "revision": o.revision})
    db.commit()
    return lib_view(kind, o)


@app.get("/api/library/{kind}/{oid}/revisions")
def lib_revs(kind: str, oid: int, db: Session = D):
    return [m.to_dict(r) for r in db.query(m.Revision).filter_by(entity_type=LIB[kind][1], entity_id=oid).order_by(m.Revision.id.desc())]


# ------------------------------------------------------------------ validation (reference calculations)
def case_view(c):
    return {**m.to_dict(c), "result": sv.run_reference_case(c)}


@app.get("/api/validation/cases")
def val_cases(db: Session = D):
    return [case_view(c) for c in db.query(m.ReferenceCase).order_by(m.ReferenceCase.id)]


@app.post("/api/validation/cases")
def val_add(body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "engineer")
    for k in ("title", "kind", "inputs", "expected", "source"):
        if not body.get(k):
            raise HTTPException(422, f"{k} is required")
    if body["kind"] not in ("beam", "sandwich", "section", "wind_ce"):
        raise HTTPException(422, "kind must be beam, sandwich, section or wind_ce")
    c = m.ReferenceCase(title=body["title"], kind=body["kind"], inputs=body["inputs"], expected=body["expected"],
                        rel_tol=float(body.get("rel_tol", 0.005)), source=body["source"], origin="ENGINEER", created_by=user.username)
    db.add(c); db.flush()
    sv.audit(db, user, "validation.case_add", None, f"case:{c.id}", {"title": c.title})
    db.commit()
    return case_view(c)


@app.post("/api/validation/cases/{cid}/approve")
def val_approve(cid: int, db: Session = D, user: m.User = U):
    need(user, "engineer")
    c = db.get(m.ReferenceCase, cid)
    if not c:
        raise HTTPException(404, "case not found")
    if c.created_by == user.username:
        raise HTTPException(403, "a reference case must be approved by an engineer other than its author")
    res = sv.run_reference_case(c)
    if not res["passed"]:
        raise HTTPException(409, "case is failing against the current engine; it cannot be approved")
    c.approved_by, c.approved_at, c.last_result = user.username, m.now(), res
    sv.audit(db, user, "validation.case_approve", None, f"case:{c.id}", {"title": c.title, "engine_version": ENGINE_VERSION})
    db.commit()
    return case_view(c)


# ------------------------------------------------------------------ review / approval
def package(db, p):
    cr = sv.current_runs(db, p)
    if not cr:
        raise HTTPException(422, "project has no walls; import a model first")
    stale = [c["wall"].name for c in cr if not c["current"]]
    if stale:
        raise HTTPException(409, f"calculations missing or out of date for: {', '.join(stale)}. Re-run calculations.")
    return [c["run"] for c in cr]


@app.get("/api/projects/{pid}/reviews")
def reviews(pid: int, db: Session = D):
    p = get_project(db, pid)
    cr = sv.current_runs(db, p)
    runs = [c["run"] for c in cr if c["run"]]
    return {"reviews": [sv.review_view(db, p, r) for r in db.query(m.Review).filter_by(project_id=pid).order_by(m.Review.id.desc())],
            "reliance_blockers": sv.reliance_blockers(db, runs),
            "package_ready": bool(cr) and all(c["current"] for c in cr),
            "all_pass": bool(runs) and all(r.status == "PASS" for r in runs)}


@app.post("/api/projects/{pid}/reviews")
def submit_review(pid: int, body: dict = Body(default={}), db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid); runs = package(db, p)
    failing = [r.wall_name for r in runs if r.status != "PASS"]
    if failing:
        raise HTTPException(422, f"cannot submit: checks failing on {', '.join(failing)}")
    ph = sv.package_hash(runs)
    open_ = db.query(m.Review).filter_by(project_id=pid, package_hash=ph, status="SUBMITTED").first()
    if open_:
        raise HTTPException(409, "this calculation package is already awaiting review")
    n = db.query(m.Review).filter_by(project_id=pid).count() + 1
    rv = m.Review(project_id=pid, revision=n, status="SUBMITTED", run_ids=[r.id for r in runs], package_hash=ph,
                  submitted_by=user.username, submit_note=body.get("note", ""))
    db.add(rv); db.flush()
    sv.audit(db, user, "review.submit", pid, f"review:{rv.id}", {"revision": n, "package_hash": ph, "run_ids": rv.run_ids})
    db.commit()
    return sv.review_view(db, p, rv)


@app.post("/api/reviews/{rid}/decision")
def decide(rid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "engineer")          # no autonomous sign-off: a named engineer must decide
    rv = db.get(m.Review, rid)
    if not rv:
        raise HTTPException(404, "review not found")
    p = get_project(db, rv.project_id)
    if sv.review_view(db, p, rv)["effective_status"] != "SUBMITTED":
        raise HTTPException(409, "review is not open (already decided, or superseded by changed inputs)")
    if rv.submitted_by == user.username:
        raise HTTPException(403, "independent review required: the submitter cannot approve their own package")
    decision, comment = body.get("decision"), (body.get("comment") or "").strip()
    runs = [db.get(m.CalcRun, i) for i in rv.run_ids]
    blockers = sv.reliance_blockers(db, runs)
    if decision == "approve_reliance":
        if blockers:
            raise HTTPException(422, {"message": "cannot approve for engineering reliance", "blockers": blockers})
        rv.status = "APPROVED_RELIANCE"
    elif decision == "approve_demo":
        rv.status = "APPROVED_DEMO"
    elif decision == "return":
        if len(comment) < 5:
            raise HTTPException(422, "a comment explaining the return is required")
        rv.status = "RETURNED"
    else:
        raise HTTPException(422, "decision must be approve_reliance, approve_demo or return")
    rv.decided_by, rv.decided_at, rv.decision_comment, rv.blockers_at_decision = user.username, m.now(), comment, blockers
    sv.audit(db, user, "review.decision", p.id, f"review:{rv.id}", {"decision": rv.status, "comment": comment, "open_blockers": len(blockers),
             "package_hash": rv.package_hash})
    db.commit()
    return sv.review_view(db, p, rv)


# ------------------------------------------------------------------ reports
@app.post("/api/projects/{pid}/reports")
def make_report(pid: int, db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid); runs = package(db, p)
    ph = sv.package_hash(runs)
    rv = db.query(m.Review).filter_by(project_id=pid, package_hash=ph).order_by(m.Review.id.desc()).first()
    rvv = sv.review_view(db, p, rv) if rv else None
    label = {"APPROVED_RELIANCE": "APPROVED FOR ENGINEERING RELIANCE", "APPROVED_DEMO": "APPROVED - DEMONSTRATION ONLY",
             "SUBMITTED": "DRAFT - UNDER REVIEW", "RETURNED": "DRAFT - RETURNED BY REVIEWER"}.get(rvv["effective_status"] if rvv else "", "DRAFT - NOT REVIEWED")
    n = db.query(m.Report).filter_by(project_id=pid).count() + 1
    at = m.now()
    pdf = build_report(project=m.to_dict(p), runs=[run_view(r) for r in runs], status_label=label, review=rvv,
                       blockers=sv.reliance_blockers(db, runs), revision=n, package_hash=ph, generated_by=user.username,
                       generated_at=at.isoformat()[:19] + "Z")
    fn = f"{p.number}_calc_report_rev{n}.pdf"
    with open(os.path.join(DATA_DIR, "reports", fn), "wb") as f:
        f.write(pdf)
    rep = m.Report(project_id=pid, revision=n, status_label=label, review_id=rv.id if rv else None, package_hash=ph, filename=fn,
                   sha256=sv.sha(pdf), size_bytes=len(pdf), created_by=user.username, created_at=at)
    db.add(rep); db.flush()
    sv.audit(db, user, "report.generate", pid, f"report:{rep.id}", {"filename": fn, "sha256": rep.sha256, "status_label": label})
    db.commit()
    return m.to_dict(rep)


@app.get("/api/projects/{pid}/reports")
def list_reports(pid: int, db: Session = D):
    return [m.to_dict(r) for r in db.query(m.Report).filter_by(project_id=pid).order_by(m.Report.id.desc())]


@app.get("/api/reports/{rid}/download")
def download(rid: int, db: Session = D):
    r = db.get(m.Report, rid)
    if not r:
        raise HTTPException(404, "report not found")
    return FileResponse(os.path.join(DATA_DIR, "reports", r.filename), media_type="application/pdf", filename=r.filename)


# ------------------------------------------------------------------ MOCK integrations (Salesforce / SAP / Forma Docs)
@app.get("/api/integrations/salesforce/opportunities")
def sf_opps(db: Session = D):
    linked = {p.sf_opportunity_id: p.id for p in db.query(m.Project) if p.sf_opportunity_id}
    return {"mock": True, "note": MOCK_NOTE,
            "records": [{**m.to_dict(o), "project_id": linked.get(o.sf_id)} for o in db.query(m.MockSfOpportunity).order_by(m.MockSfOpportunity.id)]}


@app.post("/api/integrations/salesforce/opportunities/{sf_id}/create-project")
def sf_create(sf_id: str, db: Session = D, user: m.User = U):
    o = db.query(m.MockSfOpportunity).filter_by(sf_id=sf_id).first()
    if not o:
        raise HTTPException(404, "opportunity not found")
    if db.query(m.Project).filter_by(sf_opportunity_id=sf_id).first():
        raise HTTPException(409, "a project already exists for this opportunity")
    p = create_project(db, user, {"name": o.name, "client": o.account, **o.site,
                                  "climate_source": f"Mock Salesforce opportunity {sf_id} site fields - confirm against NBCC Appendix C climatic data"}, sf_id)
    db.commit()
    return project_view(db, p)


@app.post("/api/projects/{pid}/integrations/salesforce/sync-status")
def sf_sync(pid: int, db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid)
    o = db.query(m.MockSfOpportunity).filter_by(sf_id=p.sf_opportunity_id).first() if p.sf_opportunity_id else None
    if not o:
        raise HTTPException(422, "project is not linked to a Salesforce opportunity")
    st = sv.project_status(db, p)
    o.engineering_status = st
    o.status_log = o.status_log + [{"at": m.now().isoformat(), "status": st, "by": user.username}]
    sv.audit(db, user, "mock.salesforce.status_sync", pid, f"sf:{o.sf_id}", {"status": st, "mock": True})
    db.commit()
    return {"mock": True, "note": MOCK_NOTE, "record": m.to_dict(o)}


@app.get("/api/integrations/sap/materials")
def sap_materials(db: Session = D):
    return {"mock": True, "note": MOCK_NOTE, "records": [m.to_dict(x) for x in db.query(m.MockSapMaterial).order_by(m.MockSapMaterial.id)]}


@app.post("/api/projects/{pid}/integrations/sap/handoff")
def sap_handoff(pid: int, db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid); runs = package(db, p); ph = sv.package_hash(runs)
    rv = db.query(m.Review).filter_by(project_id=pid, package_hash=ph).filter(m.Review.status.in_(("APPROVED_DEMO", "APPROVED_RELIANCE"))).first()
    if not rv:
        raise HTTPException(422, "an engineer-approved review of the current calculation package is required before staging a handoff")
    mat = {x.ref_name: x for x in db.query(m.MockSapMaterial)}
    agg: dict[str, dict] = {}
    def add(ref, qty, wall):
        x = mat.get(ref)
        if not x:
            raise HTTPException(422, f"no SAP material mapping for '{ref}'")
        a = agg.setdefault(x.material_no, {"material_no": x.material_no, "description": x.description, "uom": x.uom, "quantity": 0.0, "walls": []})
        a["quantity"] += qty; a["walls"].append(wall)
    for r in runs:
        q = r.results["quantities"]
        add(r.inputs["product"]["name"], q["net_panel_area_m2"], r.wall_name)
        add(r.inputs["section"]["name"], q["girt_length_m"] + q["opening_framing_length_m"], r.wall_name)
        add("fastener", q["fastener_count"], r.wall_name)
    for a in agg.values():
        a["quantity"] = round(a["quantity"], 2)
    payload = {"project_number": p.number, "sf_opportunity_id": p.sf_opportunity_id, "review_id": rv.id, "approval_level": rv.status,
               "approved_by": rv.decided_by, "package_hash": ph, "engineering_reliance": rv.status == "APPROVED_RELIANCE",
               "production_authorization": "NOT GRANTED BY PANEL STUDIO - production authorization remains in SAP",
               "items": sorted(agg.values(), key=lambda a: a["material_no"])}
    h = m.MockSapHandoff(project_id=pid, review_id=rv.id, status="STAGED_NOT_TRANSMITTED", payload=payload, created_by=user.username)
    db.add(h); db.flush()
    sv.audit(db, user, "mock.sap.handoff_staged", pid, f"handoff:{h.id}", {"items": len(payload["items"]), "approval_level": rv.status, "mock": True})
    db.commit()
    return {"mock": True, "note": MOCK_NOTE, "record": m.to_dict(h)}


@app.post("/api/projects/{pid}/integrations/forma/publish")
def forma_publish(pid: int, body: dict = Body(...), db: Session = D, user: m.User = U):
    need(user, "coordinator", "engineer")
    p = get_project(db, pid)
    rep = db.get(m.Report, body.get("report_id") or 0)
    if not rep or rep.project_id != pid:
        raise HTTPException(404, "report not found for this project")
    folder = f"/{p.number}/Engineering/Calculations"
    name = f"{p.number}_calc_report.pdf"
    if db.query(m.MockFormaDoc).filter_by(project_id=pid, report_id=rep.id).first():
        raise HTTPException(409, "this report revision is already published")
    v = db.query(m.MockFormaDoc).filter_by(project_id=pid, filename=name).count() + 1
    d = m.MockFormaDoc(project_id=pid, folder=folder, filename=name, version=v, report_id=rep.id, sha256=rep.sha256, uploaded_by=user.username)
    db.add(d); db.flush()
    sv.audit(db, user, "mock.forma.publish", pid, f"doc:{d.id}", {"folder": folder, "filename": name, "version": v, "sha256": rep.sha256, "mock": True})
    db.commit()
    return {"mock": True, "note": MOCK_NOTE, "record": m.to_dict(d)}


@app.get("/api/projects/{pid}/integrations")
def integrations(pid: int, db: Session = D):
    p = get_project(db, pid)
    o = db.query(m.MockSfOpportunity).filter_by(sf_id=p.sf_opportunity_id).first() if p.sf_opportunity_id else None
    return {"mock": True, "note": MOCK_NOTE, "salesforce": m.to_dict(o) if o else None,
            "sap_handoffs": [m.to_dict(h) for h in db.query(m.MockSapHandoff).filter_by(project_id=pid).order_by(m.MockSapHandoff.id.desc())],
            "forma_docs": [m.to_dict(d) for d in db.query(m.MockFormaDoc).filter_by(project_id=pid).order_by(m.MockFormaDoc.id.desc())]}


# ------------------------------------------------------------------ audit / dashboard
@app.get("/api/audit")
def audit_list(project_id: int | None = None, limit: int = 300, db: Session = D):
    q = db.query(m.AuditEvent)
    if project_id:
        q = q.filter_by(project_id=project_id)
    return {"chain": sv.verify_audit_chain(db), "events": [m.to_dict(e) for e in q.order_by(m.AuditEvent.id.desc()).limit(limit)]}


@app.get("/api/dashboard")
def dashboard(db: Session = D):
    projects = db.query(m.Project).all()
    by_status: dict[str, int] = {}
    walls = stale = passing = 0; dcrs = []
    for p in projects:
        st = sv.project_status(db, p); by_status[st] = by_status.get(st, 0) + 1
        for c in sv.current_runs(db, p):
            walls += 1
            if c["run"] and c["current"]:
                dcrs.append({"project": p.number, "wall": c["wall"].name, "max_dcr": c["run"].max_dcr, "status": c["run"].status,
                             "governing": c["run"].results["summary"]["governing_title"]})
                passing += c["run"].status == "PASS"
            else:
                stale += 1
    applied = db.query(m.OptimizationRun).filter_by(applied=True).all()
    vs_pass = [o for o in applied if o.result["steel_saving_kg"] is not None]      # baseline itself passed
    corrected = [o for o in applied if o.result.get("steel_added_for_compliance_kg") is not None]
    base = sum(o.result["baseline"]["steel_mass_kg"] for o in vs_pass)
    saved = sum(o.result["steel_saving_kg"] for o in vs_pass)
    timed = [p for p in projects if p.baseline_prep_hours and p.actual_prep_hours is not None]
    bh, ah = sum(p.baseline_prep_hours for p in timed), sum(p.actual_prep_hours for p in timed)
    ev = []
    for label, Model in (("Panel products", m.Product), ("Girt sections", m.Section), ("Code tables", m.CodeValue)):
        rows = db.query(Model).all()
        ev.append({"label": label, "verified": sum(r.evidence_status == m.VERIFIED for r in rows), "total": len(rows)})
    cases = db.query(m.ReferenceCase).all()
    ev.append({"label": "Reference calculations approved", "verified": sum(bool(c.approved_by) for c in cases), "total": len(cases)})
    reviews_ = db.query(m.Review).all()
    return {"projects": len(projects), "by_status": by_status, "walls": walls, "walls_current": walls - stale, "walls_passing": passing,
            "calc_runs": db.query(m.CalcRun).count(), "optimizations": db.query(m.OptimizationRun).count(), "dcrs": dcrs,
            "steel": {"applied_optimizations": len(applied), "compared_to_passing_baseline": len(vs_pass), "failing_layouts_corrected": len(corrected),
                      "baseline_kg": base, "saved_kg": saved, "saved_pct": (saved / base * 100 if base else None)},
            "prep_time": {"projects_measured": len(timed), "baseline_hours": bh, "actual_hours": ah,
                          "reduction_pct": ((bh - ah) / bh * 100 if bh else None), "target_pct": 25.0,
                          "basis": "Hours entered by the project team per project; target is the pilot benchmark, not a forecast."},
            "evidence": ev,
            "reviews": {"submitted": sum(r.status == "SUBMITTED" for r in reviews_), "approved_demo": sum(r.status == "APPROVED_DEMO" for r in reviews_),
                        "approved_reliance": sum(r.status == "APPROVED_RELIANCE" for r in reviews_), "returned": sum(r.status == "RETURNED" for r in reviews_)},
            "reports": db.query(m.Report).count(), "audit": sv.verify_audit_chain(db),
            "safeguards": ["No autonomous engineering sign-off: approvals require a named engineer other than the submitter.",
                           "No SAP production write-back: handoffs are staged in a mock outbox and never transmitted.",
                           "Unverified capacities are flagged on every run and block approval for engineering reliance.",
                           "No live enterprise credentials: Salesforce, SAP and Forma Docs are local simulations."]}


_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
