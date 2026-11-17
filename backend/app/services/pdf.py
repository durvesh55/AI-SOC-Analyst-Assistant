"""Investigation report PDF (ReportLab / Platypus)."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .mitre import DISCLAIMER

SEV_COLORS = {"Critical": "#b91c1c", "High": "#c2410c", "Medium": "#a16207", "Low": "#15803d"}


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "-"


def _p(text, style) -> Paragraph:
    """Paragraph with user text escaped so it can never inject markup into the PDF."""
    return Paragraph(escape(str(text if text not in (None, "") else "-")).replace("\n", "<br/>"), style)


def build_case_report(case: dict, alerts: list[dict], assignee: str, generated_by: str, generated_at) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"Investigation Report {case['case_id']}", author="AI SOC Analyst Assistant")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, textColor=colors.HexColor("#0f172a"), spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, textColor=colors.HexColor("#1e3a8a"),
                        spaceBefore=12, spaceAfter=4)
    grid = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])

    sev_color = SEV_COLORS.get(case["severity"], "#334155")
    story = [
        Paragraph("Security Investigation Report", h1),
        Paragraph(f"Case <b>{escape(case['case_id'])}</b> &nbsp;|&nbsp; Severity: "
                  f"<font color='{sev_color}'><b>{escape(case['severity'])}</b></font> &nbsp;|&nbsp; "
                  f"Status: <b>{escape(case['status'])}</b>", body),
        Spacer(1, 6),
    ]

    summary = [
        ["Title", _p(case["title"], body)],
        ["Assigned analyst", _p(assignee, body)],
        ["Created", _p(_fmt(case.get("created_at")), body)],
        ["Closed", _p(_fmt(case.get("closed_at")), body)],
        ["Linked alerts", _p(", ".join(a["alert_id"] for a in alerts), body)],
    ]
    t = Table(summary, colWidths=[40 * mm, 130 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Paragraph("Case Summary", h2), t]

    story.append(Paragraph("Alert Information", h2))
    rows = [["Alert", "Title / Details", "Severity", "Category", "Status"]]
    for a in alerts:
        detail = a["title"]
        extra = [f"src {a['source_ip']}" if a.get("source_ip") else "", f"dst {a['destination_ip']}" if a.get("destination_ip") else "",
                 f"host {a['hostname']}" if a.get("hostname") else "", f"user {a['affected_user']}" if a.get("affected_user") else ""]
        extra = ", ".join(e for e in extra if e)
        rows.append([_p(a["alert_id"], small), _p(detail + (f"\n{extra}" if extra else ""), small),
                     _p(a["severity"], small), _p(a["category"], small), _p(a["status"], small)])
    t = Table(rows, colWidths=[24 * mm, 70 * mm, 18 * mm, 30 * mm, 28 * mm], repeatRows=1)
    t.setStyle(grid)
    story.append(t)

    story.append(Paragraph("MITRE ATT&amp;CK Mapping (Suggestions)", h2))
    story.append(Paragraph(escape(DISCLAIMER) + " Mappings are NOT confirmed attacker behaviour.", small))
    story.append(Spacer(1, 3))
    if case.get("mitre_suggestions"):
        rows = [["Technique", "Name", "Tactic", "Why suggested"]]
        for m in case["mitre_suggestions"]:
            rows.append([_p(m["technique_id"], small), _p(m["technique_name"], small),
                         _p(m["tactic"], small), _p(m["reason"], small)])
        t = Table(rows, colWidths=[20 * mm, 40 * mm, 30 * mm, 80 * mm], repeatRows=1)
        t.setStyle(grid)
        story.append(t)
    else:
        story.append(_p("No technique suggestions for this case.", body))

    story.append(Paragraph("Investigation Notes", h2))
    if case.get("notes"):
        for n in case["notes"]:
            story.append(Paragraph(f"<b>{escape(n['author_username'])}</b> - {_fmt(n['created_at'])}", small))
            story.append(_p(n["text"], body))
            story.append(Spacer(1, 4))
    else:
        story.append(_p("No notes recorded.", body))

    story.append(Paragraph("Investigation Timeline", h2))
    rows = [["Time (UTC)", "By", "Event", "Detail"]]
    for e in case.get("timeline", []):
        rows.append([_p(_fmt(e["at"]), small), _p(e["by_username"], small), _p(e["action"], small), _p(e["detail"], small)])
    t = Table(rows, colWidths=[34 * mm, 26 * mm, 32 * mm, 78 * mm], repeatRows=1)
    t.setStyle(grid)
    story.append(t)

    story.append(Paragraph("Findings", h2))
    story.append(_p(case.get("findings"), body))
    story.append(Paragraph("Conclusion", h2))
    story.append(_p(case.get("conclusion"), body))
    if case.get("outcome"):
        story.append(Paragraph(f"Outcome: <b>{escape(case['outcome'])}</b>", body))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(18 * mm, 10 * mm, f"{case['case_id']} - generated {_fmt(generated_at)} by {generated_by} - "
                                           "Educational SOC assistant: not a production SIEM")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
