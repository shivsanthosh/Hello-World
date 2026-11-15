from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

UNVERIFIED, VERIFIED = "UNVERIFIED", "VERIFIED"


def now():
    return datetime.now(timezone.utc)


def to_dict(o):
    d = {}
    for c in o.__table__.columns:
        v = getattr(o, c.name)
        d[c.name] = v.isoformat() if isinstance(v, datetime) else v
    return d


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)   # coordinator | engineer | manager


class EvidenceMixin:
    evidence_status: Mapped[str] = mapped_column(String, default=UNVERIFIED)
    evidence_ref: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Product(Base, EvidenceMixin):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String, default="")
    thickness_mm: Mapped[float] = mapped_column(Float)
    module_mm: Mapped[float] = mapped_column(Float)
    face_ext_mm: Mapped[float] = mapped_column(Float)
    face_int_mm: Mapped[float] = mapped_column(Float)
    E_face_MPa: Mapped[float] = mapped_column(Float)
    G_core_MPa: Mapped[float] = mapped_column(Float)
    Mr_kNm_per_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    Vr_kN_per_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fastener_Tr_kN: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_span_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    mass_kg_m2: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(Text, default="")


class Section(Base, EvidenceMixin):
    __tablename__ = "sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    shape: Mapped[str] = mapped_column(String)
    depth_mm: Mapped[float] = mapped_column(Float)
    flange_mm: Mapped[float] = mapped_column(Float)
    lip_mm: Mapped[float] = mapped_column(Float)
    t_mm: Mapped[float] = mapped_column(Float)
    Fy_MPa: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text, default="")


class CodeValue(Base, EvidenceMixin):
    __tablename__ = "code_values"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    value: Mapped[dict] = mapped_column(JSON)
    unit: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(Text)


class Revision(Base):
    """Generic revision history: immutable snapshot of an entity each time it changes."""
    __tablename__ = "revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String, default="")
    user: Mapped[str] = mapped_column(String)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    client: Mapped[str] = mapped_column(String, default="")
    location: Mapped[str] = mapped_column(String, default="")
    q50_kpa: Mapped[float] = mapped_column(Float)
    importance: Mapped[str] = mapped_column(String, default="Normal")
    terrain: Mapped[str] = mapped_column(String, default="Open")
    ref_height_m: Mapped[float] = mapped_column(Float)
    ct: Mapped[float] = mapped_column(Float, default=1.0)
    internal_category: Mapped[str] = mapped_column(String, default="Category 2")
    least_plan_dim_m: Mapped[float] = mapped_column(Float)
    climate_source: Mapped[str] = mapped_column(Text, default="")
    sf_opportunity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    baseline_prep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_prep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ModelImport(Base):
    __tablename__ = "model_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source: Mapped[dict] = mapped_column(JSON)
    columns: Mapped[list] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String)
    summary: Mapped[dict] = mapped_column(JSON)
    imported_by: Mapped[str] = mapped_column(String)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Wall(Base):
    __tablename__ = "walls"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    revit_element_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    type_name: Mapped[str] = mapped_column(String, default="")
    start_x: Mapped[float] = mapped_column(Float)
    start_y: Mapped[float] = mapped_column(Float)
    end_x: Mapped[float] = mapped_column(Float)
    end_y: Mapped[float] = mapped_column(Float)
    base_elev_m: Mapped[float] = mapped_column(Float, default=0)
    length_m: Mapped[float] = mapped_column(Float)
    height_m: Mapped[float] = mapped_column(Float)
    bay_offsets_m: Mapped[list] = mapped_column(JSON)
    max_bay_m: Mapped[float] = mapped_column(Float)
    openings: Mapped[list] = mapped_column(JSON)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), nullable=True)
    n_spans: Mapped[int] = mapped_column(Integer, default=1)
    fasteners_per_support: Mapped[int] = mapped_column(Integer, default=2)


class CalcRun(Base):
    __tablename__ = "calc_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    wall_id: Mapped[int] = mapped_column(Integer, index=True)
    wall_name: Mapped[str] = mapped_column(String)
    revision: Mapped[int] = mapped_column(Integer)
    input_hash: Mapped[str] = mapped_column(String, index=True)
    inputs: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    max_dcr: Mapped[float] = mapped_column(Float)
    engine_version: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    wall_id: Mapped[int] = mapped_column(Integer, index=True)
    wall_name: Mapped[str] = mapped_column(String)
    input_hash: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_by: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)   # SUBMITTED | APPROVED_DEMO | APPROVED_RELIANCE | RETURNED
    run_ids: Mapped[list] = mapped_column(JSON)
    package_hash: Mapped[str] = mapped_column(String)
    blockers_at_decision: Mapped[list] = mapped_column(JSON, default=list)
    submitted_by: Mapped[str] = mapped_column(String)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    submit_note: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_comment: Mapped[str] = mapped_column(Text, default="")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    status_label: Mapped[str] = mapped_column(String)
    review_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_hash: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditEvent(Base):
    """Append-only, hash-chained audit record."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)
    user: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)


class ReferenceCase(Base):
    __tablename__ = "reference_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    inputs: Mapped[dict] = mapped_column(JSON)
    expected: Mapped[dict] = mapped_column(JSON)
    rel_tol: Mapped[float] = mapped_column(Float, default=0.005)
    source: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String, default="TEXTBOOK")
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="system")


# ---- Mock enterprise systems (simulated; no live connection to Salesforce, SAP or Autodesk) ----
class MockSfOpportunity(Base):
    __tablename__ = "mock_sf_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    sf_id: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    account: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String)
    amount_cad: Mapped[float] = mapped_column(Float)
    site: Mapped[dict] = mapped_column(JSON)
    engineering_status: Mapped[str] = mapped_column(String, default="")
    status_log: Mapped[list] = mapped_column(JSON, default=list)


class MockSapMaterial(Base):
    __tablename__ = "mock_sap_materials"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_no: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)     # product | section | fastener
    ref_name: Mapped[str] = mapped_column(String)
    uom: Mapped[str] = mapped_column(String)


class MockSapHandoff(Base):
    __tablename__ = "mock_sap_handoffs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    review_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MockFormaDoc(Base):
    __tablename__ = "mock_forma_docs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    folder: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    report_id: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String)
    uploaded_by: Mapped[str] = mapped_column(String)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)
