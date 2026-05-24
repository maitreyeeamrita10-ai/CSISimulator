import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)


def safe_text(value):
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf_report(filepath, case, user, evidence, suspects, verdict, notes=None):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "title",
        parent=styles["Title"],
        textColor=colors.HexColor("#0f172a"),
        fontSize=22,
        leading=26,
        alignment=1,
        spaceAfter=10
    )

    h2 = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1e40af"),
        fontSize=14,
        leading=18,
        spaceBefore=10,
        spaceAfter=8
    )

    normal = ParagraphStyle(
        "normal",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.black
    )

    table_text = ParagraphStyle(
        "table_text",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
        textColor=colors.black
    )

    table_head = ParagraphStyle(
        "table_head",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    story = []

    story.append(Paragraph("CSI Simulator Investigation Report", title))
    story.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            normal
        )
    )
    story.append(Spacer(1, 14))

    # CASE SUMMARY
    story.append(Paragraph("Case Summary", h2))

    summary = [
        [
            Paragraph("<b>Case</b>", table_text),
            Paragraph(safe_text(case.get("title", "")), table_text)
        ],
        [
            Paragraph("<b>Crime Type</b>", table_text),
            Paragraph(safe_text(case.get("crime_type", "")), table_text)
        ],
        [
            Paragraph("<b>Location</b>", table_text),
            Paragraph(safe_text(case.get("location", "")), table_text)
        ],
        [
            Paragraph("<b>Difficulty</b>", table_text),
            Paragraph(safe_text(case.get("difficulty", "")), table_text)
        ],
        [
            Paragraph("<b>Investigator</b>", table_text),
            Paragraph(safe_text(user.get("name", "")), table_text)
        ],
        [
            Paragraph("<b>Description</b>", table_text),
            Paragraph(safe_text(case.get("description", "")), table_text)
        ],
    ]

    table = Table(summary, colWidths=[110, 340])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dbeafe")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(table)
    story.append(Spacer(1, 14))

    # EVIDENCE COLLECTED
    story.append(Paragraph("Evidence Collected", h2))

    rows = [
        [
            Paragraph("<b>Evidence</b>", table_head),
            Paragraph("<b>Type</b>", table_head),
            Paragraph("<b>Lab Result</b>", table_head),
        ]
    ]

    for ev in evidence:
        evidence_name = (
            ev.get("label")
            or ev.get("evidence_name")
            or ev.get("description")
            or ""
        )

        evidence_type = ev.get("type") or ev.get("evidence_type") or ""
        lab_result = ev.get("lab_result") or "Pending lab examination"

        rows.append([
            Paragraph(safe_text(evidence_name), table_text),
            Paragraph(safe_text(evidence_type), table_text),
            Paragraph(safe_text(lab_result), table_text),
        ])

    if len(rows) == 1:
        rows.append([
            Paragraph("No evidence collected", table_text),
            Paragraph("-", table_text),
            Paragraph("-", table_text),
        ])

    evidence_table = Table(rows, colWidths=[210, 90, 150], repeatRows=1)
    evidence_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(evidence_table)
    story.append(Spacer(1, 14))

    # SUSPECT ANALYSIS
    story.append(Paragraph("Suspect Analysis", h2))

    for s in suspects:
        story.append(
            Paragraph(
                f"<b>{safe_text(s.get('name', ''))}</b> "
                f"({safe_text(s.get('occupation', ''))})",
                normal
            )
        )
        story.append(
            Paragraph(
                f"<b>Alibi:</b> {safe_text(s.get('alibi', ''))}",
                normal
            )
        )
        story.append(
            Paragraph(
                f"<b>Motive:</b> {safe_text(s.get('motive', ''))}",
                normal
            )
        )
        story.append(Spacer(1, 6))

    # FINAL VERDICT
    story.append(Paragraph("Final Verdict", h2))

    if verdict:
        story.append(
            Paragraph(
                f"<b>Accused:</b> {safe_text(verdict.get('accused_name', 'Not selected'))}",
                normal
            )
        )
        story.append(
            Paragraph(
                f"<b>Reasoning:</b> {safe_text(verdict.get('reasoning', ''))}",
                normal
            )
        )
        story.append(
            Paragraph(
                f"<b>Score:</b> {safe_text(verdict.get('score', 0))} / 100",
                normal
            )
        )
        story.append(
            Paragraph(
                f"<b>Verdict Accuracy:</b> "
                f"{'Correct' if verdict.get('is_correct') else 'Incorrect'}",
                normal
            )
        )
    else:
        story.append(Paragraph("No verdict submitted yet.", normal))

    # NOTES
    if notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Investigation Notes", h2))
        story.append(Paragraph(safe_text(notes), normal))

    doc.build(story)
    return filepath