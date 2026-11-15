"""PDF calculation report: every number with its formula, substitution, units and reference."""
from __future__ import annotations
import io
from xml.sax.saxutils import escape as esc
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ss = getSampleStyleSheet()
SM = ParagraphStyle("sm", parent=ss["Normal"], fontSize=7, leading=8.5)
N = ParagraphStyle("n", parent=ss["Normal"], fontSize=9, leading=11)
H1, H2 = ss["Heading1"], ss["Heading2"]
GRID = [("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "TOP")]


def P(t, st=SM):
    return Paragraph(esc(str(t)), st)


def tbl(rows, widths, extra=()):
    t = Table([[c if not isinstance(c, str) else P(c) for c in r] for r in rows], colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle(GRID + list(extra)))
    return t


def build_report(*, project: dict, runs: list[dict], status_label: str, review: dict | None, blockers: list[str],
                 revision: int, package_hash: str, generated_by: str, generated_at: str) -> bytes:
    buf = io.BytesIO()

    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.grey)
        canvas.drawString(12 * mm, 8 * mm, f"Panel Studio | {project['number']} | Report rev {revision} | package {package_hash[:16]} | {status_label}")
        canvas.drawRightString(285 * mm, 8 * mm, f"Page {doc.page}")
        if "RELIANCE" not in status_label:
            canvas.setFont("Helvetica-Bold", 46); canvas.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.10))
            canvas.translate(148 * mm, 100 * mm); canvas.rotate(25)
            canvas.drawCentredString(0, 0, "NOT FOR ENGINEERING RELIANCE")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                            title=f"Panel Studio calculation report {project['number']}")
    s = [Paragraph("IMP Wall Engineering Calculation Report", H1),
         P(f"{project['number']} - {project['name']} | Client: {project['client']} | Location: {project['location']}", N),
         P(f"Status: {status_label} | Report revision {revision} | Generated {generated_at} by {generated_by}", N), Spacer(1, 4 * mm)]
    if blockers:
        s += [P("Reliance blockers (must be cleared before this package can be approved for engineering reliance):", N)]
        s += [P(f"- {b}", SM) for b in blockers] + [Spacer(1, 3 * mm)]
    s += [Paragraph("Site and wind parameters", H2),
          tbl([["Parameter", "Value", "Source"],
               ["q (1/50) reference velocity pressure", f"{project['q50_kpa']} kPa", project.get("climate_source") or "Entered by user - source not recorded"],
               ["Importance category", project["importance"], "NBCC 2020 Table 4.1.2.1."],
               ["Terrain", project["terrain"], "NBCC 2020 4.1.7.3.(5)"],
               ["Reference height", f"{project['ref_height_m']} m", "Model / user"],
               ["Topographic factor Ct", str(project["ct"]), "NBCC 2020 4.1.7.4."],
               ["Internal pressure", project["internal_category"], "NBCC 2020 4.1.7.7."],
               ["Least plan dimension", f"{project['least_plan_dim_m']} m", "Model / user"]], [70, 40, 160])]
    if review:
        s += [Paragraph("Review record", H2),
              tbl([["Review rev", "Status", "Submitted by", "Submitted", "Decided by", "Decided", "Comment"],
                   [str(review["revision"]), review["effective_status"], review["submitted_by"], review["submitted_at"][:19],
                    review.get("decided_by") or "-", (review.get("decided_at") or "-")[:19], review.get("decision_comment") or "-"]],
                  [18, 36, 28, 34, 28, 34, 92])]
    s += [Paragraph("Summary", H2),
          tbl([["Wall", "Run rev", "Product", "Girt", "Spacing (m)", "Status", "Max DCR", "Governing check", "Steel (kg)", "Input hash"]] +
              [[r["wall_name"], str(r["revision"]), r["inputs"]["product"]["name"], r["inputs"]["section"]["name"],
                f"{r['results']['girt_spacing_m']:.3f}", r["status"], f"{r['max_dcr']:.3f}", r["results"]["summary"]["governing_title"],
                f"{r['results']['quantities']['secondary_steel_mass_kg']:.0f}", r["input_hash"][:12]] for r in runs],
              [28, 14, 26, 30, 20, 16, 18, 62, 20, 36])]
    for r in runs:
        res = r["results"]
        s += [PageBreak(), Paragraph(f"Wall: {r['wall_name']} (run revision {r['revision']}, engine {r['engine_version']})", H2),
              P(f"Input hash {r['input_hash']} | run by {r['created_by']} at {r['created_at'][:19]}", SM), Spacer(1, 2 * mm),
              tbl([["Data item", "Type", "Rev", "Evidence status", "Source / evidence reference"]] +
                  [[e["name"], e["kind"], str(e["revision"]), e["status"], (e["evidence_ref"] or e["source"])] for e in r["inputs"]["evidence"]],
                  [55, 16, 10, 26, 163]), Spacer(1, 3 * mm), P("Checks", N),
              tbl([["Check", "Demand", "Capacity", "Unit", "DCR", "Status", "Criterion", "Reference"]] +
                  [[c["title"], f"{c['demand']:.3f}", f"{c['capacity']:.3f}", c["unit"], f"{c['dcr']:.3f}", c["status"], c["formula"], c["reference"]]
                   for c in res["checks"]], [62, 18, 18, 16, 14, 14, 44, 84],
                  [("TEXTCOLOR", (5, i + 1), (5, i + 1), colors.red if c["status"] == "FAIL" else colors.darkgreen) for i, c in enumerate(res["checks"])]),
              Spacer(1, 3 * mm), P("Calculation trace", N),
              tbl([["ID", "Quantity", "Formula", "Substitution", "Value", "Unit", "Reference"]] +
                  [[st["id"], st["title"], st["formula"], st["substitution"], f"{st['value']:.4g}", st["unit"], st["reference"]] for st in res["steps"]],
                  [30, 44, 50, 70, 16, 14, 46]), Spacer(1, 3 * mm), P("Quantities", N),
              tbl([["Item", "Value"]] + [[k, f"{v:.2f}" if isinstance(v, float) else str(v)] for k, v in res["quantities"].items()], [80, 40]),
              Spacer(1, 3 * mm), P("Assumptions and exclusions", N)] + [P(f"- {a}", SM) for a in res["assumptions"] + res["warnings"]]
    doc.build(s, onFirstPage=deco, onLaterPages=deco)
    return buf.getvalue()
