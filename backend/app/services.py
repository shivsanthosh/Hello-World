"""Domain services: audit chain, revisions, model import, calculation packaging, evidence gating."""
from __future__ import annotations
import hashlib, json, math
from fastapi import HTTPException
from sqlalchemy.orm import Session
from engine import ENGINE_VERSION, wind, beam, panel, sections
from engine.wall import design_wall
from . import models as m


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def sha(o) -> str:
    return hashlib.sha256((o if isinstance(o, bytes) else canon(o).encode())).hexdigest()


# ------------------------------------------------------------------ audit
def audit(db: Session, user: m.User, action: str, project_id: int | None = None, entity: str = "", detail: dict | None = None):
    last = db.query(m.AuditEvent).order_by(m.AuditEvent.id.desc()).first()
    prev = last.hash if last else "GENESIS"
    at = m.now()
    body = {"at": at.isoformat(), "user": user.username, "role": user.role, "action": action,
            "project_id": project_id, "entity": entity, "detail": detail or {}}
    ev = m.AuditEvent(at=at, user=user.username, role=user.role, action=action, project_id=project_id, entity=entity,
                      detail=detail or {}, prev_hash=prev, hash=sha(prev + canon(body)))
    db.add(ev); db.flush()
    return ev


def verify_audit_chain(db: Session) -> dict:
    prev = "GENESIS"; n = 0
    for ev in db.query(m.AuditEvent).order_by(m.AuditEvent.id):
        at = ev.at.replace(tzinfo=__import__("datetime").timezone.utc) if ev.at.tzinfo is None else ev.at
        body = {"at": at.isoformat(), "user": ev.user, "role": ev.role, "action": ev.action,
                "project_id": ev.project_id, "entity": ev.entity, "detail": ev.detail}
        if ev.prev_hash != prev or ev.hash != sha(prev + canon(body)):
            return {"valid": False, "events": n, "broken_at_id": ev.id}
        prev = ev.hash; n += 1
    return {"valid": True, "events": n, "head": prev}


def snapshot(db: Session, user: m.User, etype: str, obj, reason: str):
    db.add(m.Revision(entity_type=etype, entity_id=obj.id, revision=obj.revision, snapshot=m.to_dict(obj),
                      reason=reason, user=user.username))


# ------------------------------------------------------------------ model import (Revit-derived JSON)
def import_model(db: Session, user: m.User, project: m.Project, data: dict) -> m.ModelImport:
    src = data.get("source") or {}
    if "Revit" not in str(src.get("application", "")):
        raise HTTPException(422, "source.application must identify an Autodesk Revit export")
    scale = {"mm": 0.001, "m": 1.0}.get(src.get("units", "mm"))
    if scale is None:
        raise HTTPException(422, "source.units must be 'mm' or 'm'")
    walls_in = data.get("walls") or []
    if not walls_in:
        raise HTTPException(422, "export contains no walls")
    cols = [{"id": str(c.get("revit_element_id", "")), "x": c["x"] * scale, "y": c["y"] * scale} for c in data.get("columns", [])]
    existing = {w.revit_element_id: w for w in db.query(m.Wall).filter_by(project_id=project.id)}
    seen, warnings, added, updated = set(), [], 0, 0
    default_product = db.query(m.Product).order_by(m.Product.id).first()
    default_section = db.query(m.Section).order_by(m.Section.id).first()
    for w in walls_in:
        eid = str(w["revit_element_id"])
        if eid in seen:
            raise HTTPException(422, f"duplicate wall element id {eid}")
        seen.add(eid)
        sx, sy, ex, ey = (w["start"][0] * scale, w["start"][1] * scale, w["end"][0] * scale, w["end"][1] * scale)
        L = math.hypot(ex - sx, ey - sy); H = w["height"] * scale
        if L <= 0 or H <= 0:
            raise HTTPException(422, f"wall {eid}: zero length or height")
        ux, uy = (ex - sx) / L, (ey - sy) / L
        offs = set()
        for c in cols:
            t = (c["x"] - sx) * ux + (c["y"] - sy) * uy
            dist = abs((c["x"] - sx) * -uy + (c["y"] - sy) * ux)
            if dist <= 0.6 and -0.05 <= t <= L + 0.05:
                offs.add(round(min(max(t, 0.0), L), 3))
        offs = sorted(offs)
        if len(offs) >= 2:
            pts = sorted(set([0.0] + offs + [round(L, 3)]))
            bay = max(b - a for a, b in zip(pts, pts[1:]))
        else:
            bay = L; warnings.append(f"Wall '{w.get('name', eid)}': fewer than 2 structural columns found on the wall line; bay taken as full wall length.")
        ops = []
        for o in w.get("openings", []):
            op = {"revit_element_id": str(o.get("revit_element_id", "")), "kind": o.get("kind", "opening"),
                  "offset_m": o["offset"] * scale, "width_m": o["width"] * scale, "sill_m": o.get("sill", 0) * scale, "height_m": o["height"] * scale}
            if op["offset_m"] < 0 or op["offset_m"] + op["width_m"] > L + 1e-6 or op["sill_m"] + op["height_m"] > H + 1e-6:
                raise HTTPException(422, f"wall {eid}: opening {op['revit_element_id']} lies outside the wall")
            ops.append(op)
        geom = dict(name=w.get("name", eid), type_name=w.get("type_name", ""), start_x=sx, start_y=sy, end_x=ex, end_y=ey,
                    base_elev_m=w.get("base_elevation", 0) * scale, length_m=round(L, 4), height_m=round(H, 4),
                    bay_offsets_m=offs, max_bay_m=round(bay, 4), openings=ops)
        if eid in existing:
            for k, v in geom.items():
                setattr(existing[eid], k, v)
            updated += 1
        else:
            db.add(m.Wall(project_id=project.id, revit_element_id=eid, product_id=default_product.id, section_id=default_section.id,
                          n_spans=max(1, math.ceil(H / (default_product.max_span_m or H))), **geom))
            added += 1
    removed = [w for eid, w in existing.items() if eid not in seen]
    for w in removed:
        db.delete(w)
    summary = {"walls_added": added, "walls_updated": updated, "walls_removed": len(removed), "columns": len(cols), "warnings": warnings}
    imp = m.ModelImport(project_id=project.id, source=src, columns=cols, sha256=sha(data), summary=summary, imported_by=user.username)
    db.add(imp); db.flush()
    audit(db, user, "model.import", project.id, f"import:{imp.id}", {"sha256": imp.sha256, **summary, "source": src})
    return imp


# ------------------------------------------------------------------ calculation inputs / evidence
def code_rows(db: Session):
    return db.query(m.CodeValue).order_by(m.CodeValue.key).all()


def build_inputs(db: Session, project: m.Project, wall: m.Wall) -> dict:
    product = db.get(m.Product, wall.product_id) if wall.product_id else None
    section = db.get(m.Section, wall.section_id) if wall.section_id else None
    if not product or not section:
        raise HTTPException(422, f"wall '{wall.name}' has no panel product or girt section assigned")
    rows = code_rows(db)
    pcols = ("id", "name", "thickness_mm", "module_mm", "face_ext_mm", "face_int_mm", "E_face_MPa", "G_core_MPa", "Mr_kNm_per_m",
             "Vr_kN_per_m", "fastener_Tr_kN", "max_span_m", "mass_kg_m2")
    scols = ("id", "name", "shape", "depth_mm", "flange_mm", "lip_mm", "t_mm", "Fy_MPa")
    ev = lambda kind, name, o: {"kind": kind, "name": name, "status": o.evidence_status, "revision": o.revision,
                                "source": o.source, "evidence_ref": o.evidence_ref, "verified_by": o.verified_by}
    return {
        "site": {k: getattr(project, k) for k in ("q50_kpa", "importance", "terrain", "ref_height_m", "ct", "internal_category", "least_plan_dim_m")},
        "wall": {"length_m": wall.length_m, "height_m": wall.height_m, "max_bay_m": wall.max_bay_m,
                 "openings": [{k: o[k] for k in ("offset_m", "width_m", "sill_m", "height_m")} for o in wall.openings]},
        "design": {"n_spans": wall.n_spans, "fasteners_per_support": wall.fasteners_per_support},
        "product": {k: getattr(product, k) for k in pcols},
        "section": {k: getattr(section, k) for k in scols},
        "code": {r.key: r.value["v"] for r in rows},
        "evidence": [ev("product", product.name, product), ev("section", section.name, section)] + [ev("code", r.key, r) for r in rows],
    }


def input_hash(inputs: dict) -> str:
    return sha({"engine": ENGINE_VERSION, "inputs": inputs})


def run_calc(db: Session, user: m.User, project: m.Project, wall: m.Wall) -> tuple[m.CalcRun, bool]:
    """Returns (run, created). Identical inputs + engine version reuse the existing immutable run."""
    inputs = build_inputs(db, project, wall)
    h = input_hash(inputs)
    last = db.query(m.CalcRun).filter_by(wall_id=wall.id).order_by(m.CalcRun.revision.desc()).first()
    if last and last.input_hash == h:
        return last, False
    try:
        res = design_wall(inputs)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"calculation refused for wall '{wall.name}': {e}")
    run = m.CalcRun(project_id=project.id, wall_id=wall.id, wall_name=wall.name, revision=(last.revision + 1 if last else 1),
                    input_hash=h, inputs=inputs, results=res, status=res["summary"]["status"], max_dcr=res["summary"]["max_dcr"],
                    engine_version=ENGINE_VERSION, created_by=user.username)
    db.add(run); db.flush()
    audit(db, user, "calc.run", project.id, f"wall:{wall.id}", {"run_id": run.id, "revision": run.revision, "input_hash": h,
          "status": run.status, "max_dcr": round(run.max_dcr, 4), "engine_version": ENGINE_VERSION})
    return run, True


def current_runs(db: Session, project: m.Project) -> list[dict]:
    """Per wall: latest run and whether it still matches the wall's present inputs."""
    out = []
    for w in db.query(m.Wall).filter_by(project_id=project.id).order_by(m.Wall.id):
        run = db.query(m.CalcRun).filter_by(wall_id=w.id).order_by(m.CalcRun.revision.desc()).first()
        try:
            h = input_hash(build_inputs(db, project, w))
        except HTTPException:
            h = None
        out.append({"wall": w, "run": run, "current": bool(run and h and run.input_hash == h)})
    return out


def package_hash(runs: list[m.CalcRun]) -> str:
    return sha(sorted(r.input_hash for r in runs))


# ------------------------------------------------------------------ validation / reliance gating
def run_reference_case(c: m.ReferenceCase) -> dict:
    try:
        if c.kind == "beam":
            res = beam.continuous_beam(**c.inputs)
        elif c.kind == "sandwich":
            res = panel.sandwich_stiffness(**c.inputs)
        elif c.kind == "section":
            res = sections.lipped_section(**c.inputs)
        elif c.kind == "wind_ce":
            res = {"ce": wind.exposure_factor(**c.inputs)}
        else:
            return {"passed": False, "error": f"unknown case kind '{c.kind}'", "rows": []}
        rows = []
        for k, exp in c.expected.items():
            got = res[k]
            err = abs(got - exp) / abs(exp) if exp else abs(got)
            rows.append({"quantity": k, "expected": exp, "engine": got, "rel_error": err, "passed": err <= c.rel_tol})
        return {"passed": all(r["passed"] for r in rows), "rows": rows, "engine_version": ENGINE_VERSION}
    except Exception as e:  # a reference case must never crash the page; report it as a failure
        return {"passed": False, "error": str(e), "rows": []}


def reliance_blockers(db: Session, runs: list[m.CalcRun]) -> list[str]:
    """Everything that must be resolved before results may be approved for engineering reliance."""
    b, seen = [], set()
    for r in runs:
        for e in r.inputs["evidence"]:
            key = (e["kind"], e["name"])
            if e["status"] != m.VERIFIED and key not in seen:
                seen.add(key); b.append(f"Unverified {e['kind']} data: {e['name']}")
    cases = db.query(m.ReferenceCase).all()
    unapproved = [c for c in cases if not c.approved_by]
    if unapproved:
        b.append(f"{len(unapproved)} of {len(cases)} reference calculations not yet approved by an independent engineer")
    failing = [c for c in cases if not run_reference_case(c)["passed"]]
    if failing:
        b.append(f"{len(failing)} reference calculation(s) failing against engine {ENGINE_VERSION}")
    return b


def project_status(db: Session, p: m.Project) -> str:
    cr = current_runs(db, p)
    if not cr:
        return "Setup"
    if db.query(m.MockSapHandoff).filter_by(project_id=p.id).count():
        rv = db.query(m.Review).filter_by(project_id=p.id).order_by(m.Review.id.desc()).first()
        if rv and review_view(db, p, rv)["effective_status"].startswith("APPROVED"):
            return "Handoff staged"
    rv = db.query(m.Review).filter_by(project_id=p.id).order_by(m.Review.id.desc()).first()
    if rv:
        es = review_view(db, p, rv)["effective_status"]
        if es != "SUPERSEDED":
            return {"SUBMITTED": "In review", "APPROVED_DEMO": "Approved (demonstration)", "APPROVED_RELIANCE": "Approved for reliance",
                    "RETURNED": "Returned"}[es]
    return "Design"


def review_view(db: Session, p: m.Project, rv: m.Review) -> dict:
    cr = current_runs(db, p)
    live = package_hash([c["run"] for c in cr]) if cr and all(c["current"] for c in cr) else None
    d = m.to_dict(rv)
    d["effective_status"] = rv.status if live == rv.package_hash else "SUPERSEDED"
    return d
