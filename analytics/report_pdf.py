from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

def generate_report_pdf(title, subtitle, headers, rows, summary_text=None, landscape_mode=True):
    """
    Generates a branded Kenya Airways PDF report.
    Returns bytes of the generated PDF document.
    """
    buffer = BytesIO()
    page_size = landscape(A4) if landscape_mode else A4
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    KQ_RED = colors.HexColor("#C8102E")
    KQ_DARK = colors.HexColor("#0B2240")
    KQ_GRAY = colors.HexColor("#6B7280")
    KQ_LIGHT = colors.HexColor("#F8F9FA")
    BORDER_COLOR = colors.HexColor("#E5E7EB")

    # Header Styles
    header_title = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=KQ_DARK,
        leading=18,
    )

    meta_text = ParagraphStyle(
        'RepMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=KQ_GRAY,
        leading=11,
    )

    cell_style = ParagraphStyle(
        'RepCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1F2937"),
    )

    cell_right = ParagraphStyle(
        'RepCellR',
        parent=cell_style,
        alignment=TA_RIGHT,
    )

    cell_bold_right = ParagraphStyle(
        'RepCellBR',
        parent=cell_style,
        fontName='Helvetica-Bold',
        alignment=TA_RIGHT,
    )

    th_style = ParagraphStyle(
        'RepTH',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=colors.white,
    )

    th_right = ParagraphStyle(
        'RepTHR',
        parent=th_style,
        alignment=TA_RIGHT,
    )

    # 1. Page Header with KQ Brand
    from django.utils import timezone
    gen_time = timezone.now().strftime("%B %d, %Y %H:%M")
    
    left_meta = [
        Paragraph("<b>KENYA AIRWAYS PLC</b>", ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=KQ_RED)),
        Paragraph("Sales &amp; Order Intelligence System — Executive Reporting", meta_text),
        Paragraph(f"<b>Report:</b> {title}", header_title),
        Paragraph(f"{subtitle}", meta_text),
    ]

    right_meta = [
        Paragraph("<b>CONFIDENTIAL &amp; PROPRIETARY</b>", ParagraphStyle('RConf', parent=meta_text, fontName='Helvetica-Bold', alignment=TA_RIGHT, textColor=KQ_RED)),
        Paragraph(f"<b>Generated:</b> {gen_time}", ParagraphStyle('RGen', parent=meta_text, alignment=TA_RIGHT)),
        Paragraph("Water Bottling &amp; Catering Sales Unit", ParagraphStyle('RDep', parent=meta_text, alignment=TA_RIGHT)),
    ]

    header_table = Table([[left_meta, right_meta]], colWidths=[5.0*inch, 5.0*inch] if landscape_mode else [3.5*inch, 3.8*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=KQ_DARK, spaceAfter=12))

    # 2. Build Table
    th_cells = []
    for h in headers:
        if any(w in h.lower() for w in ['total', 'amount', 'paid', 'balance', 'price', 'spend', 'qty', 'score', 'days']):
            th_cells.append(Paragraph(f"<b>{h}</b>", th_right))
        else:
            th_cells.append(Paragraph(f"<b>{h}</b>", th_style))

    table_data = [th_cells]

    for row in rows:
        row_cells = []
        for i, val in enumerate(row):
            h_text = headers[i].lower() if i < len(headers) else ""
            val_str = str(val) if val is not None else "—"
            if any(w in h_text for w in ['total', 'amount', 'paid', 'balance', 'price', 'spend']):
                row_cells.append(Paragraph(val_str, cell_right))
            elif any(w in h_text for w in ['qty', 'days', 'score', 'frequency']):
                row_cells.append(Paragraph(val_str, cell_right))
            else:
                row_cells.append(Paragraph(val_str, cell_style))
        table_data.append(row_cells)

    # Calculate proportional column widths
    total_avail_width = 10.3 * inch if landscape_mode else 7.3 * inch
    num_cols = len(headers)
    col_width = total_avail_width / max(1, num_cols)
    col_widths = [col_width] * num_cols

    rep_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    rep_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), KQ_DARK),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, KQ_LIGHT]),
    ]))
    story.append(rep_table)

    # 3. Summary Footer
    if summary_text:
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<b>Summary Notes:</b> {summary_text}", meta_text))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
