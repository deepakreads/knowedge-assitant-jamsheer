from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.models import Sop


def generate_sop_pdf(sop: Sop) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
    )
    h2_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#334155"))
    bold_body = ParagraphStyle("BoldBody", parent=styles["Normal"], fontSize=9, leading=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#0f172a"))

    story = []

    # Title & Metadata
    story.append(Paragraph(f"Standard Operating Procedure: {sop.title}", title_style))
    story.append(Spacer(1, 10))

    meta_data = [
        [Paragraph(f"<b>Status:</b> {sop.status}", body_style), Paragraph(f"<b>Est. Duration:</b> {sop.estimated_duration}", body_style)],
        [Paragraph(f"<b>Source Video:</b> {sop.source_video}", body_style), Paragraph(f"<b>SOP ID:</b> {sop.id[:8]}...", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Purpose & Scope
    story.append(Paragraph("1. Document Overview", h2_style))
    story.append(Paragraph(f"<b>Purpose:</b> {sop.purpose}", body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Scope:</b> {sop.scope}", body_style))
    story.append(Spacer(1, 10))

    # Tools & Materials
    story.append(Paragraph("2. Required Tools & Materials", h2_style))
    tools_str = ", ".join(sop.required_tools) if sop.required_tools else "Not specified in source video."
    mats_str = ", ".join(sop.required_materials) if sop.required_materials else "Not specified in source video."
    story.append(Paragraph(f"<b>Required Tools:</b> {tools_str}", body_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Required Materials:</b> {mats_str}", body_style))
    story.append(Spacer(1, 10))

    # Procedure Steps
    story.append(Paragraph("3. Detailed Operational Procedure Steps", h2_style))
    story.append(Spacer(1, 4))

    step_table_data = [
        [
            Paragraph("<b>Step</b>", bold_body),
            Paragraph("<b>Instruction & Operational Details</b>", bold_body),
            Paragraph("<b>Tools & Components</b>", bold_body),
        ]
    ]

    for step in sop.steps:
        tools_list = ", ".join(step.tools) if step.tools else "-"
        mats_list = ", ".join(step.materials) if step.materials else "-"
        tools_mats = f"<b>Tools:</b> {tools_list}<br/><b>Materials:</b> {mats_list}"

        desc_text = f"<b>{step.title}</b> (t={step.start_time:.1f}s - {step.end_time:.1f}s)<br/>{step.description}"
        if step.quality_check:
            desc_text += f"<br/><font color='#2563eb'><b>QC Verification:</b> {step.quality_check}</font>"
        if step.safety_notes:
            desc_text += f"<br/><font color='#dc2626'><b>Safety Note:</b> {', '.join(step.safety_notes)}</font>"

        step_table_data.append(
            [
                Paragraph(f"<b>#{step.step_number:02d}</b>", bold_body),
                Paragraph(desc_text, body_style),
                Paragraph(tools_mats, body_style),
            ]
        )

    step_table = Table(step_table_data, colWidths=[35, 335, 170])
    step_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(step_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()