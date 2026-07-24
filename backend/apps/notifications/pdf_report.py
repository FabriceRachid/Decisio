"""
PDF report generation for DécisioBI.
Generates PDF reports with KPI summaries, charts, and data tables.
"""

import io
import os
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_kpi_report_pdf(
    user: User,
    kpi_context: List[Dict[str, Any]],
    title: str = "Rapport KPI DécisioBI",
    include_charts: bool = True,
) -> Optional[bytes]:
    """Generate a PDF report with KPI data using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        )
        from reportlab.graphics.shapes import Drawing, Rect
        from reportlab.graphics.charts.barcharts import VerticalBarChart
    except ImportError:
        logger.warning("reportlab not installed; cannot generate PDF reports")
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontSize=20, spaceAfter=12, textColor=colors.HexColor('#1a3a5c')
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=14, spaceAfter=8, textColor=colors.HexColor('#d4a843')
    )
    normal_style = ParagraphStyle(
        'CustomNormal', parent=styles['Normal'],
        fontSize=10, spaceAfter=6
    )

    story = []

    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=40, height=40)
        story.append(logo)
        story.append(Spacer(1, 8))

    # Title
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(
        f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')} par {user.username}",
        normal_style
    ))
    story.append(Spacer(1, 12))

    # Summary
    on_target = sum(1 for k in kpi_context if k.get('status') == 'on_target')
    warning = sum(1 for k in kpi_context if k.get('status') == 'warning')
    critical = sum(1 for k in kpi_context if k.get('status') == 'critical')

    story.append(Paragraph("Résumé", heading_style))
    summary_data = [
        ['Indicateur', 'Valeur'],
        ['Total KPIs', str(len(kpi_context))],
        ['Sous contrôle', str(on_target)],
        ['À surveiller', str(warning)],
        ['Critiques', str(critical)],
    ]
    summary_table = Table(summary_data, colWidths=[120, 80])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # KPI Details
    story.append(Paragraph("Détail des KPIs", heading_style))

    if kpi_context:
        kpi_data = [['Nom', 'Mesure', 'Valeur', 'Statut']]
        for kpi in kpi_context[:20]:
            kpi_data.append([
                str(kpi.get('name', 'N/A'))[:30],
                str(kpi.get('measure', 'N/A'))[:20],
                str(kpi.get('value', 'N/A')),
                str(kpi.get('status', 'N/A')),
            ])

        kpi_table = Table(kpi_data, colWidths=[140, 100, 80, 80])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(kpi_table)
    else:
        story.append(Paragraph("Aucun KPI disponible.", normal_style))

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_dashboard_pdf(
    user: User,
    dashboard_name: str,
    source_name: str,
    widgets: List[Dict[str, Any]],
    title: str = "Dashboard DécisioBI",
) -> Optional[bytes]:
    """Generate a PDF report with KPI summaries and breakdown tables from widget payloads."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image
        )
    except ImportError:
        logger.warning("reportlab not installed; cannot generate PDF reports")
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DTitle', parent=styles['Title'],
        fontSize=20, spaceAfter=4, textColor=colors.HexColor('#1a3a5c')
    )
    subtitle_style = ParagraphStyle(
        'DSubtitle', parent=styles['Normal'],
        fontSize=10, spaceAfter=16, textColor=colors.HexColor('#6b7280')
    )
    normal_style = ParagraphStyle(
        'DNormal', parent=styles['Normal'],
        fontSize=9, spaceAfter=4
    )
    kpi_value_style = ParagraphStyle(
        'KPIValue', parent=styles['Normal'],
        fontSize=22, spaceAfter=2, textColor=colors.HexColor('#1a3a5c'),
        fontName='Helvetica-Bold',
    )
    kpi_label_style = ParagraphStyle(
        'KPILabel', parent=styles['Normal'],
        fontSize=9, spaceAfter=2, textColor=colors.HexColor('#6b7280'),
    )
    widget_title_style = ParagraphStyle(
        'WTitle', parent=styles['Heading3'],
        fontSize=12, spaceAfter=6, spaceBefore=10, textColor=colors.HexColor('#1a3a5c')
    )

    story = []

    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=40, height=40)
        story.append(logo)
        story.append(Spacer(1, 8))

    story.append(Paragraph(title, title_style))
    story.append(Paragraph(
        f"{dashboard_name} — {source_name}",
        subtitle_style
    ))
    story.append(Paragraph(
        f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')} par {user.get_full_name() or user.username}",
        normal_style
    ))
    story.append(Spacer(1, 8))

    gold_color = colors.HexColor('#d4a843')
    header_bg = colors.HexColor('#1a3a5c')
    alt_row_bg = colors.HexColor('#f3f4f6')

    AGG_LABELS = {
        'sum': 'Somme', 'mean': 'Moyenne', 'avg': 'Moyenne',
        'count': 'Nombre', 'max': 'Maximum', 'min': 'Minimum',
        'median': 'Médiane', 'std': 'Écart-type',
    }

    for i, w in enumerate(widgets):
        wtype = w.get('type', 'metric_card')
        title = w.get('title', f'Widget {i+1}')
        payload = w.get('payload', {})
        if not payload:
            continue

        value = payload.get('value', 0)
        formatted_value = payload.get('formatted_value', str(value))
        agg = payload.get('aggregation', 'sum')
        agg_label = AGG_LABELS.get(agg, agg)
        measure = payload.get('measure', '')
        rows_processed = payload.get('rows_processed', 0)
        breakdown = payload.get('breakdown', [])
        group_by = payload.get('group_by', [])

        widget_elements = []

        widget_elements.append(Paragraph(f"{i+1}. {title}", widget_title_style))

        if wtype == 'metric_card' or not breakdown:
            widget_elements.append(Paragraph(formatted_value, kpi_value_style))
            widget_elements.append(Paragraph(
                f"{agg_label} de « {measure} » — {rows_processed:,} lignes analysées".replace(',', ' '),
                kpi_label_style
            ))
        else:
            widget_elements.append(Paragraph(
                f"{agg_label} de « {measure} » par « {', '.join(group_by)} » — {rows_processed:,} lignes analysées".replace(',', ' '),
                kpi_label_style
            ))

        if breakdown and len(breakdown) > 0:
            dim_col = group_by[0] if group_by else 'Catégorie'
            table_data = [[dim_col, 'Valeur', '% du total']]
            total = sum(item.get('value', 0) for item in breakdown) or 1
            for item in breakdown:
                dim_val = str(item.get(dim_col, item.get('categorie', item.get('region', item.get('produit', '')))))
                val = item.get('value', 0)
                pct = (val / total * 100) if total else 0
                table_data.append([dim_val, f"{val:,.2f}".replace(',', ' '), f"{pct:.1f}%"])

            t = Table(table_data, colWidths=[None, None, None])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), header_bg),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ] + [
                ('BACKGROUND', (0, row), (-1, row), alt_row_bg)
                for row in range(2, len(table_data), 2)
            ]))
            widget_elements.append(Spacer(1, 4))
            widget_elements.append(t)

        widget_elements.append(Spacer(1, 10))
        story.append(KeepTogether(widget_elements))

    if not widgets:
        story.append(Paragraph("Aucun widget dans ce dashboard.", normal_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_pivot_report_pdf(
    user: User,
    pivot_data: dict,
    title: str = "Tableau Croisé Dynamique",
) -> Optional[bytes]:
    """Generate a PDF report from pivot table data."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        )
    except ImportError:
        logger.warning("reportlab not installed; cannot generate PDF reports")
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontSize=18, spaceAfter=10, textColor=colors.HexColor('#1a3a5c')
    )
    normal_style = ParagraphStyle(
        'CustomNormal', parent=styles['Normal'],
        fontSize=9, spaceAfter=4
    )

    story = []

    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=40, height=40)
        story.append(logo)
        story.append(Spacer(1, 8))

    story.append(Paragraph(title, title_style))
    story.append(Paragraph(
        f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')} par {user.username}",
        normal_style
    ))
    story.append(Spacer(1, 10))

    pivot = pivot_data.get('pivot', [])
    row_headers = pivot_data.get('row_headers', [])
    col_headers = pivot_data.get('col_headers', [])
    totals = pivot_data.get('totals', {})

    if pivot and col_headers:
        header_row = [''] + col_headers
        if totals.get('col_totals'):
            header_row.append('Total')

        table_data = [header_row]
        for i, row in enumerate(pivot):
            row_label = row_headers[i] if i < len(row_headers) else ''
            table_row = [str(row_label)]
            for val in row:
                if isinstance(val, (int, float)):
                    table_row.append(f'{val:,.0f}')
                else:
                    table_row.append(str(val))
            if totals.get('row_totals') and i < len(totals['row_totals']):
                table_row.append(f'{totals["row_totals"][i]:,.0f}')
            table_data.append(table_row)

        if totals.get('col_totals'):
            total_row = ['Total']
            for ct in totals['col_totals']:
                total_row.append(f'{ct:,.0f}')
            total_row.append(f'{totals.get("grand_total", 0):,.0f}')
            table_data.append(total_row)

        n_cols = len(header_row)
        col_width = (landscape(A4)[0] - 3*cm) / n_cols
        col_widths = [col_width * 1.5] + [col_width] * (n_cols - 1)

        data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        data_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f9fafb')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8edf3')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(data_table)
    else:
        story.append(Paragraph("Aucune donnée disponible.", normal_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
