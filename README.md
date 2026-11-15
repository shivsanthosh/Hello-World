# Panel Studio — IMP Engineering Studio (pilot build)

A browser-based engineering studio for insulated metal panel (IMP) walls: import Revit-derived
geometry, run traceable deterministic checks, optimise girt spacing and secondary steel, route the
package through engineer review, issue a calculation report, and stage handoffs to (simulated)
Salesforce, SAP and Autodesk Forma Docs.

> **Status of this build.** It was built from the pitch-package `README.md` and the seven-step build
> brief. The file `PANEL_STUDIO_SPEC_DRIVEN_BUILD_PROMPT.md` was **not available** when this was
> written, so anything specific to that document has not been checked against it. See
> [Known gaps](#known-gaps-and-what-must-be-verified).

## Quick start

Requirements: Python 3.11+, Node 20+.

```bash
./run.sh                 # installs, builds the UI, serves http://127.0.0.1:8000
```

Or for development with hot reload:

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt
(cd backend && uvicorn app.main:app --reload --port 8000)   # API
(cd frontend && npm install && npm run dev)                  # UI on http://127.0.0.1:5173
```

The database is SQLite at `backend/data/panel_studio.db` (created and seeded on first start; delete
the `backend/data` folder to reset). Override with `PANEL_STUDIO_DATA` / `PANEL_STUDIO_DB`.

## Tests

```bash
(cd backend && python -m pytest -q)        # 48 tests: 35 engine, 13 API/workflow
node e2e/demo.e2e.cjs                       # 16 browser steps; needs the app running on an EMPTY database
```

Latest results: [`docs/backend_test_results.txt`](docs/backend_test_results.txt) (48 passed),
[`docs/e2e_results.txt`](docs/e2e_results.txt) (16 passed). The browser test also regenerates
[`docs/screenshots/`](docs/screenshots) and [`docs/sample_calc_report.pdf`](docs/sample_calc_report.pdf).

## Architecture

| Layer | Technology | Location |
|---|---|---|
| Interface | React 19 + TypeScript + Vite | `frontend/src` |
| 3D / elevation viewer | Three.js | `frontend/src/Viewer.tsx` |
| Engineering engine | Pure Python (NumPy), no I/O | `backend/engine` |
| API and workflow | FastAPI | `backend/app/main.py`, `services.py` |
| Persistence | SQLAlchemy + SQLite | `backend/app/models.py` |
| Reports | ReportLab PDF | `backend/app/reports.py` |

The engine is a set of pure functions. The API assembles an input snapshot (site, wall geometry,
design, product record, girt section, code tables, and the evidence status of each), hashes it, runs
the engine, and stores the immutable result. Identical inputs return the existing run; any change
creates a new revision.

## What the engine calculates

| Function | Method | Reference |
|---|---|---|
| Wind pressure on cladding and girts | `p = Iw·q·Ce·Ct·(CpCg − Cgi·Cpi)`, area-dependent CpCg, end/interior zones, 1.4 W | NBCC 2020 4.1.7 (static, low-rise) |
| Panel stiffness | `EI = E·A1·A2/(A1+A2)·e²`, `GA = G·b·e²/dc` | Sandwich beam theory |
| Panel moments, shears, reactions, deflection | Three-moment equation with core shear flexibility; bending + shear deflection | Sandwich theory (cf. EN 14509 Annex E) |
| Panel strength, fastener tension | Demand vs. the product record's test-derived resistance | Product record |
| Girt section properties | Thin-wall centreline method from D, B, lip, t | Geometry |
| Girt bending, shear, deflection | `Mr = φ·R·Sx·Fy` (R for through-fastened suction), web shear, `5wL⁴/384EI` | CSA S136 / AISI S100 |
| Quantity take-off | Panels, girts cut at openings, opening framing, fasteners | Geometry |
| Optimisation | Exhaustive enumeration of spacing × section; lightest layout passing every check | — |

Every step stores formula, substituted values, result, unit and reference, and appears in the UI
and the PDF.

## Safeguards enforced in code (and tested)

- **No autonomous sign-off.** Only a user with the engineer role, other than the submitter, can decide a review.
- **Unverified data blocks reliance.** Seeded product strengths are illustrative; code tables are
  transcriptions. All start `UNVERIFIED`. "Approved for engineering reliance" is refused until every
  input record is verified with an evidence reference *and* every reference calculation is approved
  by a second engineer. Until then only "Approved — demonstration only" is possible and reports are
  watermarked.
- **Editing a record resets its verification** and creates a new revision.
- **No SAP write-back.** Handoffs are staged in a local outbox with status `STAGED_NOT_TRANSMITTED`;
  no transmit endpoint exists.
- **Mock integrations are labelled as mock** on every screen and API response.
- **Changed inputs supersede approvals** automatically (hash comparison).
- **Audit log is hash-chained**; tampering is detected and shown.

## Five-minute management demonstration

Start from an empty database (`./run.sh` on a fresh checkout). The identity switcher is bottom-left.

| Time | Acting as | Do | Point to make |
|---|---|---|---|
| 0:00 | Technical Coordinator | **Projects** → *Northfield Cold Storage* → **Create project** | Project starts from the Salesforce opportunity (simulated); wind parameters come across. |
| 0:30 | Coordinator | **Overview** → **Import sample Revit export** | 4 walls, openings and column bays derived from the model, not typed in. |
| 1:00 | Coordinator | **Model** tab: orbit; click a wall; **Elevation** | Same geometry the engine uses. |
| 1:30 | Coordinator | **Engineering** → **Run all calculations** | Default layout **fails** — the tool reports it. Scroll to the trace: every number has formula, units and source. Note the "not for engineering reliance" banner. |
| 2:15 | Coordinator | **Optimisation** → **Run optimisation** → **Apply best layout** (repeat per wall) | Every spacing × girt size is checked by the same engine; table shows all candidates. Savings are only claimed against a layout that already passed. |
| 3:00 | Coordinator | **Review & reports** → **Submit for engineering review** | Approve buttons are disabled for this role. |
| 3:20 | Reviewing Engineer | Same tab → **Approve for engineering reliance** | **Refused**, with the list of unverified data. Then **Approve — demonstration only**. |
| 3:50 | Engineer | **Generate report** → open the PDF | Watermarked; full trace, evidence table, review record, input hashes. |
| 4:15 | Engineer | **Integrations**: publish to Forma Docs, stage SAP handoff, sync Salesforce | All three are simulations. SAP handoff is staged, never transmitted. |
| 4:40 | — | **Audit** tab, then **Executive dashboard** | Hash-chained record of every action; KPIs computed from stored records; G0 readiness shows what must be verified. |

## Known gaps and what must be verified

- **Build specification not seen.** Requirements unique to `PANEL_STUDIO_SPEC_DRIVEN_BUILD_PROMPT.md` are unverified.
- **Product strengths are placeholders**, not manufacturer data.
- **Code coefficients were transcribed without the printed standards to hand** (NBCC CpCg and Cpi
  values, S136 R factors and shear provisions, clause numbers). They are stored as editable,
  unverified tables precisely so the accountable engineer can check and correct them.
- **Engine tests prove the mathematics, not code compliance.** Expected values are closed-form
  solutions computed independently of the engine; they are not engineer-approved reference
  calculations.
- **Scope is wind on vertical-spanning wall panels with simple-span girts.** Not included: thermal
  bow, seismic, roof panels, horizontal panels, continuous/lapped girts, sag rods, effective-width
  reductions, web crippling, connections, building-height > 20 m procedure.
- **Revit import is a JSON file exchange**, not a live Revit/Forma API connection; the sample model is synthetic.
- **Identity is a demo switcher**, not authentication. Production needs enterprise SSO.
