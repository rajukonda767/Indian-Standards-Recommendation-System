"""
app/routers/audit_pdf.py
========================
POST /api/audit/export-pdf

Generates a professional GeM/CPPP-format Technical Specification PDF using ReportLab.
Accepts a payload with:
  - ref_no, title, organization, date
  - rows: list of {sl_no, material_code, short_description, technical_specification, unit, quantity}
  - Each row has an "action" field: "accepted" | "rejected"
    - accepted  → technical_specification = the AI-recommended corrected clause
    - rejected  → technical_specification = the original specification from the tender (passed by frontend)

Returns the PDF as an inline download (application/pdf).
"""
import io
import html
from datetime import datetime
from typing import Optional, List, Any
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# ReportLab imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.utils import simpleSplit

router = APIRouter(prefix="/audit", tags=["Audit PDF Export"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class PdfRow(BaseModel):
    sl_no: int
    material_code: str = ""
    short_description: str = ""
    technical_specification: str = ""
    unit: str = ""
    quantity: str = ""
    action: str = "accepted"            # "accepted" | "rejected"
    original_specification: str = ""    # raw original spec for rejected rows


class ExportPdfRequest(BaseModel):
    ref_no: str = Field("100001922", description="Reference number (e.g. GeM/CPPP tender ref)")
    title: str = Field("Procurement Technical Specification", description="Document title")
    organization: Optional[str] = Field(None, description="Procuring entity name")
    date: Optional[str] = Field(None, description="Report date (YYYY-MM-DD)")
    rows: List[PdfRow] = Field(..., description="Table rows (both accepted and rejected)")


# ── PDF Generator ──────────────────────────────────────────────────────────────

def build_audit_pdf(req: ExportPdfRequest) -> bytes:
    """Builds and returns the PDF bytes using ReportLab."""
    buf = io.BytesIO()

    page_w, page_h = landscape(A4)

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    # ── Custom paragraph styles ───────────────────────────────────────────────
    style_ref = ParagraphStyle(
        "RefNo",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#1a1a1a"),
    )
    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontSize=12,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0a0a0a"),
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0a0a0a"),
        spaceAfter=2,
    )
    style_cell_center = ParagraphStyle(
        "CellCenter",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        alignment=TA_CENTER,
        leading=10,
    )
    style_cell_left = ParagraphStyle(
        "CellLeft",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        alignment=TA_LEFT,
        leading=10,
    )
    style_cell_rejected = ParagraphStyle(
        "CellRejected",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica-Oblique",
        alignment=TA_LEFT,
        leading=10,
        textColor=colors.HexColor("#5a5a5a"),
    )

    # ── Story elements ────────────────────────────────────────────────────────
    story = []

    # Header line: ref_no left, date right
    date_str = req.date or datetime.today().strftime("%d-%m-%Y")
    org_str = req.organization or ""

    ref_val = html.escape(str(req.ref_no or ""))
    ref_text = f"<b>Ref no {ref_val}</b>"
    if org_str:
        ref_text += f"&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;{html.escape(org_str)}"

    story.append(Paragraph(ref_text, style_ref))
    story.append(Paragraph(f"Date: {date_str}", style_ref))
    story.append(Spacer(1, 6 * mm))

    # Title
    story.append(Paragraph(html.escape(str(req.title or "")), style_title))

    # Subtitle with underline
    story.append(Paragraph("<u>TECHNICAL SPECIFICATION</u>", style_subtitle))
    story.append(Spacer(1, 5 * mm))

    # ── Table data ────────────────────────────────────────────────────────────
    # Column widths (landscape A4 usable ≈ 269mm)
    col_widths = [
        14 * mm,   # Sl.no
        32 * mm,   # Material Code
        50 * mm,   # Short Description
        120 * mm,  # Technical Specification
        18 * mm,   # Unit
        22 * mm,   # Quantity
    ]

    # Header row
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        leading=11,
    )
    headers = [
        Paragraph("Sl.no", header_style),
        Paragraph("Material Code", header_style),
        Paragraph("Short Description", header_style),
        Paragraph("Technical Specification", header_style),
        Paragraph("Unit", header_style),
        Paragraph("Quantity", header_style),
    ]
    table_data = [headers]

    def safe_p(text: Any, style: ParagraphStyle) -> Paragraph:
        val = str(text or "").strip()
        escaped = html.escape(val).replace("\n", "<br/>")
        return Paragraph(escaped, style)

    for row in req.rows:
        is_rejected = row.action == "rejected"
        spec_style = style_cell_rejected if is_rejected else style_cell_left

        # Specification text:
        # - For compliant & accepted: technical_specification has the clean active specification clause
        # - For rejected: user may have edited technical_specification or we fall back to original_specification
        spec_text = row.technical_specification or row.original_specification or ""

        # Sl.no formatted as multiples of 10 (like GeM: 10, 20, 30…)
        sl_display = str(row.sl_no * 10)

        row_data = [
            safe_p(sl_display, style_cell_center),
            safe_p(row.material_code, style_cell_center),
            safe_p(row.short_description, style_cell_center),
            safe_p(spec_text, spec_style),
            safe_p(row.unit, style_cell_center),
            safe_p(row.quantity, style_cell_center),
        ]
        table_data.append(row_data)

    # Build table
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

    tbl_style = TableStyle([
        # Header styling
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Grid lines — black, thin
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])

    # Shade rejected rows lightly in grey
    for i, row in enumerate(req.rows, start=1):
        if row.action == "rejected":
            tbl_style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5"))
            tbl_style.add("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#5a5a5a"))

    tbl.setStyle(tbl_style)
    story.append(tbl)

    # ── Footer function ───────────────────────────────────────────────────────
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        footer_text = (
            f"BIS Procurement Audit Report  •  StandardSphere  •  "
            f"Generated: {date_str}  •  Page {doc.page} of {doc.page}"
        )
        canvas.drawCentredString(page_w / 2, 10 * mm, footer_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return buf.getvalue()


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/export-pdf")
async def export_audit_pdf(req: ExportPdfRequest):
    """
    POST /api/audit/export-pdf
    Generates a professional GeM/CPPP-format Technical Specification PDF.
    - Accepted rows → AI-recommended corrected specification
    - Rejected rows → Original specification from the tender document
    Returns a downloadable PDF file.
    """
    try:
        pdf_bytes = build_audit_pdf(req)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    safe_ref = "".join(c if c.isalnum() else "_" for c in req.ref_no)
    date_tag = datetime.today().strftime("%Y-%m-%d")
    filename = f"Audit_Report_{safe_ref}_{date_tag}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
