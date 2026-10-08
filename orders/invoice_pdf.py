from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

def generate_invoice_pdf(order):
    """
    Generates a branded Kenya Airways PDF Tax Invoice for the given Order.
    Returns bytes of the generated PDF document.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # KQ Brand Colors
    KQ_RED = colors.HexColor("#C8102E")
    KQ_DARK = colors.HexColor("#0B2240")
    KQ_GRAY = colors.HexColor("#6B7280")
    KQ_LIGHT = colors.HexColor("#F8F9FA")
    BORDER_COLOR = colors.HexColor("#E5E7EB")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=KQ_RED,
        leading=24,
    )

    company_sub = ParagraphStyle(
        'CompanySub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=KQ_GRAY,
        leading=12,
    )

    meta_right = ParagraphStyle(
        'MetaRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        alignment=TA_RIGHT,
        textColor=KQ_DARK,
        leading=13,
    )

    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=KQ_GRAY,
        leading=10,
    )

    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1F2937"),
    )

    cell_right = ParagraphStyle(
        'CellRight',
        parent=cell_style,
        alignment=TA_RIGHT,
    )

    cell_bold_right = ParagraphStyle(
        'CellBoldRight',
        parent=cell_style,
        fontName='Helvetica-Bold',
        alignment=TA_RIGHT,
    )

    # 1. Header Section
    invoice = getattr(order, 'invoice', None)
    inv_num = f"#INV-{invoice.invoice_id}" if invoice else f"DRAFT-KQ-{order.order_id}"
    issue_date = invoice.issue_date.strftime("%B %d, %Y") if invoice else order.order_date.strftime("%B %d, %Y")

    header_left = [
        Paragraph("<b>KENYA AIRWAYS PLC</b>", ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, textColor=KQ_DARK)),
        Paragraph("Water Bottling &amp; Catering Sales Unit", company_sub),
        Paragraph("Jomo Kenyatta International Airport, Nairobi, Kenya", company_sub),
        Paragraph("PIN: P051109462W | Tel: +254 20 6422000", company_sub),
    ]

    status_str = invoice.get_payment_status_display().upper() if invoice else "DRAFT"
    status_color = "#198754" if (invoice and invoice.payment_status == 'paid') else ("#D97706" if (invoice and invoice.payment_status == 'partially_paid') else "#DC2626")

    header_right = [
        Paragraph(f"<b>TAX INVOICE</b>", ParagraphStyle('InvTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, alignment=TA_RIGHT, textColor=KQ_RED)),
        Paragraph(f"<b>Invoice No:</b> {inv_num}", meta_right),
        Paragraph(f"<b>Issue Date:</b> {issue_date}", meta_right),
        Paragraph(f"<b>Booking Ref:</b> KQ-{order.order_id}", meta_right),
        Paragraph(f"<font color='{status_color}'><b>STATUS: {status_str}</b></font>", meta_right),
    ]

    header_table = Table([[header_left, header_right]], colWidths=[3.5*inch, 3.8*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1.5, color=KQ_DARK, spaceAfter=15))

    # 2. Customer & Bill-To Section
    cust = order.customer
    bill_to_content = [
        Paragraph("<b>BILLED TO:</b>", meta_label),
        Paragraph(f"<b>{cust.name}</b>", ParagraphStyle('CustName', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=KQ_DARK)),
        Paragraph(f"Account Type: {cust.account_type}", company_sub),
        Paragraph(f"Contact: {cust.contact_info}", company_sub),
    ]

    order_info_content = [
        Paragraph("<b>PAYMENT TERMS &amp; DISPATCH:</b>", meta_label),
        Paragraph("Terms: Net 30 Days from invoice date", company_sub),
        Paragraph(f"Order Status: {order.get_status_display()}", company_sub),
        Paragraph("Currency: Kenyan Shillings (KES)", company_sub),
    ]

    billing_table = Table([[bill_to_content, order_info_content]], colWidths=[3.65*inch, 3.65*inch])
    billing_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), KQ_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(billing_table)
    story.append(Spacer(1, 15))

    # 3. Line Items Table
    headers = [
        Paragraph("<b>#</b>", ParagraphStyle('TH', parent=cell_style, fontName='Helvetica-Bold', textColor=colors.white)),
        Paragraph("<b>Item Description</b>", ParagraphStyle('TH', parent=cell_style, fontName='Helvetica-Bold', textColor=colors.white)),
        Paragraph("<b>Qty</b>", ParagraphStyle('THC', parent=cell_style, fontName='Helvetica-Bold', textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("<b>Unit Price (KES)</b>", ParagraphStyle('THR', parent=cell_right, fontName='Helvetica-Bold', textColor=colors.white)),
        Paragraph("<b>Line Total (KES)</b>", ParagraphStyle('THR', parent=cell_right, fontName='Helvetica-Bold', textColor=colors.white)),
    ]
    items_data = [headers]

    subtotal = Decimal("0.00")
    for i, item in enumerate(order.items.select_related('product').all(), 1):
        subtotal += Decimal(str(item.line_total))
        items_data.append([
            Paragraph(str(i), cell_style),
            Paragraph(item.product.name, cell_style),
            Paragraph(str(item.quantity), ParagraphStyle('C', parent=cell_style, alignment=TA_CENTER)),
            Paragraph(f"{item.unit_price:,.2f}", cell_right),
            Paragraph(f"{item.line_total:,.2f}", cell_bold_right),
        ])

    vat = round(subtotal * Decimal("0.16"), 2)
    grand_total = subtotal + vat

    items_table = Table(
        items_data,
        colWidths=[0.4*inch, 3.5*inch, 0.8*inch, 1.3*inch, 1.3*inch]
    )
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), KQ_DARK),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, KQ_LIGHT]),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 12))

    # 4. Totals & Financial Summary
    paid_amt = invoice.amount_paid if invoice else Decimal("0.00")
    balance_due = invoice.balance if invoice else grand_total

    totals_data = [
        [Paragraph("Subtotal (Excl. VAT):", cell_right), Paragraph(f"KSh {subtotal:,.2f}", cell_bold_right)],
        [Paragraph("Value Added Tax (16% VAT):", cell_right), Paragraph(f"KSh {vat:,.2f}", cell_bold_right)],
        [Paragraph("<b>Grand Total:</b>", cell_right), Paragraph(f"<b>KSh {grand_total:,.2f}</b>", ParagraphStyle('TotG', parent=cell_bold_right, textColor=KQ_RED, fontSize=10))],
    ]

    if invoice:
        totals_data.append([Paragraph("Total Amount Paid:", cell_right), Paragraph(f"<font color='#198754'><b>KSh {paid_amt:,.2f}</b></font>", cell_bold_right)])
        bal_color = "#DC2626" if balance_due > 0 else "#198754"
        totals_data.append([Paragraph("<b>Outstanding Balance Due:</b>", cell_right), Paragraph(f"<font color='{bal_color}'><b>KSh {balance_due:,.2f}</b></font>", ParagraphStyle('BalG', parent=cell_bold_right, fontSize=10))])

    totals_table = Table(totals_data, colWidths=[5.3*inch, 2.0*inch])
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,1), (-1,1), 0.5, BORDER_COLOR),
        ('LINEBELOW', (0,2), (-1,2), 1.0, KQ_DARK),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 20))

    # 5. Settlement / Remittance Instructions Box
    payment_terms = [
        Paragraph("<b>PAYMENT REMITTANCE CHANNELS:</b>", meta_label),
        Paragraph("• <b>M-Pesa Paybill:</b> Business No: <b>522522</b> | Account: <b>INV-" + (str(invoice.invoice_id) if invoice else str(order.order_id)) + "</b>", company_sub),
        Paragraph("• <b>Bank Transfer (EFT/RTGS):</b> KCB Bank Kenya | A/C No: 1102938491 | Swift: KCBLKENX", company_sub),
        Paragraph("• <b>KQ Internal Departments:</b> Provide Inter-departmental Journal Voucher to Finance Cost Centre 412.", company_sub),
        Paragraph("<i>Please quote the invoice number on all remittances. Electronic invoice valid without signature.</i>", ParagraphStyle('Foot', parent=company_sub, textColor=colors.HexColor("#9CA3AF"))),
    ]
    remit_table = Table([[payment_terms]], colWidths=[7.3*inch])
    remit_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(remit_table)

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
