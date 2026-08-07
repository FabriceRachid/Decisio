"""
PDF report generation for DécisioBI.
Professional multi-page reports with cover page, KPI cards, charts, and branding.
"""

import io
import os
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font registration (Unicode support for French characters)
# ---------------------------------------------------------------------------

_FONT_REGISTERED = False

def _register_fonts():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts_dir = os.path.join(os.path.dirname(__import__('reportlab').__file__), 'fonts')
    vera = os.path.join(fonts_dir, 'Vera.ttf')
    vera_bold = os.path.join(fonts_dir, 'VeraBd.ttf')
    vera_italic = os.path.join(fonts_dir, 'VeraIt.ttf')
    vera_bi = os.path.join(fonts_dir, 'VeraBI.ttf')
    if os.path.exists(vera):
        pdfmetrics.registerFont(TTFont('Vera', vera))
        pdfmetrics.registerFont(TTFont('Vera-Bold', vera_bold))
        pdfmetrics.registerFont(TTFont('Vera-Italic', vera_italic))
        pdfmetrics.registerFont(TTFont('Vera-BoldItalic', vera_bi))
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily('Vera', normal='Vera', bold='Vera-Bold',
                           italic='Vera-Italic', boldItalic='Vera-BoldItalic')
    _FONT_REGISTERED = True


def _font(bold=False, italic=False):
    _register_fonts()
    if bold and italic:
        return 'Vera-BoldItalic'
    if bold:
        return 'Vera-Bold'
    if italic:
        return 'Vera-Italic'
    return 'Vera'


# ---------------------------------------------------------------------------
# Branding helper
# ---------------------------------------------------------------------------

def get_company_branding(user: User) -> Dict[str, Any]:
    """Return the current user's organization branding (name, logo, brand color)."""
    org = getattr(getattr(user, 'profile', None), 'organization', None)
    if org is None:
        return {'name': 'DécisioBI', 'logo_path': None, 'brand_color': '#1a3a5c'}
    logo_path = None
    if org.logo:
        try:
            logo_path = org.logo.path
        except Exception:
            logo_path = None
    return {
        'name': org.name or 'DécisioBI',
        'logo_path': logo_path,
        'brand_color': org.brand_color or '#1a3a5c',
    }


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

DARK_BLUE = '#0f2744'
MID_BLUE = '#1a3a5c'
ACCENT_BLUE = '#2563eb'
LIGHT_BLUE = '#3b82f6'
PALE_BLUE = '#dbeafe'
GOLD = '#d4a843'
GREEN = '#16a34a'
RED = '#dc2626'
ORANGE = '#ea580c'
GRAY = '#6b7280'
LIGHT_GRAY = '#f3f4f6'
WHITE = '#ffffff'

CARD_COLORS = [ACCENT_BLUE, GOLD, GREEN, '#8b5cf6', ORANGE, RED, '#06b6d4', '#ec4899']

# ---------------------------------------------------------------------------
# Canvas callbacks
# ---------------------------------------------------------------------------

def _draw_cover_page(canvas, doc, branding, dashboard_name, source_name, widgets):
    """Draw the cover page — clean white professional design."""
    from reportlab.lib import colors as c
    from reportlab.lib.units import cm

    canvas.saveState()
    W, H = doc.pagesize
    brand_color = branding.get('brand_color', MID_BLUE)
    font_name = _font()
    font_bold = _font(bold=True)

    LM = 3 * cm
    RM = W - 3 * cm

    # === Thin accent line at very top ===
    canvas.setFillColor(c.HexColor(brand_color))
    canvas.rect(0, H - 0.25 * cm, W, 0.25 * cm, fill=True, stroke=False)

    # === Company logo ===
    logo_path = branding.get('logo_path')
    logo_y = H - 4 * cm
    logo_drawn = False
    if logo_path and os.path.exists(logo_path):
        try:
            canvas.drawImage(logo_path, LM, logo_y,
                             width=1.8 * cm, height=1.8 * cm, mask='auto')
            logo_drawn = True
        except Exception:
            pass

    canvas.setFillColor(c.HexColor(DARK_BLUE))
    canvas.setFont(font_bold, 16)
    name_x = LM + (2.2 * cm if logo_drawn else 0)
    canvas.drawString(name_x, logo_y + 0.5 * cm, branding['name'].upper())

    # === Title ===
    y_title = logo_y - 3 * cm
    canvas.setFont(font_bold, 30)
    canvas.setFillColor(c.HexColor(DARK_BLUE))
    canvas.drawString(LM, y_title, 'BUSINESS')
    canvas.drawString(LM, y_title - 1.3 * cm, 'INTELLIGENCE')
    canvas.drawString(LM, y_title - 2.6 * cm, 'REPORT')

    # Blue accent line
    canvas.setStrokeColor(c.HexColor(brand_color))
    canvas.setLineWidth(2.5)
    canvas.line(LM, y_title - 3.2 * cm, LM + 7 * cm, y_title - 3.2 * cm)

    # Subtitle
    canvas.setFont(font_name, 11)
    canvas.setFillColor(c.HexColor(brand_color))
    canvas.drawString(LM, y_title - 4.1 * cm, 'Synthese de Performance et Qualite des Donnees')

    # Description
    canvas.setFont(font_name, 9)
    canvas.setFillColor(c.HexColor(GRAY))
    canvas.drawString(LM, y_title - 5.3 * cm,
                      "Apercu analytique de la performance et de la qualite des donnees")
    canvas.drawString(LM, y_title - 5.8 * cm,
                      "pour orienter la prise de decision strategique.")

    # === Metadata with icon circles ===
    ym = y_title - 7.8 * cm
    icon_r = 0.3 * cm
    items = [
        ('P', 'PERIODE DU RAPPORT', dashboard_name),
        ('E', 'ENTREPRISE', branding['name']),
        ('G', 'GENERE PAR', 'DecisioBI Platform'),
        ('D', 'DATE DE GENERATION', timezone.now().strftime('%d %B %Y - %H:%M')),
    ]
    for initial, label, value in items:
        # Circle icon
        canvas.setFillColor(c.HexColor('#e8eef6'))
        canvas.circle(LM + icon_r + 0.15 * cm, ym, icon_r + 0.15 * cm, fill=True, stroke=False)
        canvas.setFillColor(c.HexColor(brand_color))
        canvas.setFont(font_bold, 11)
        canvas.drawCentredString(LM + icon_r + 0.15 * cm, ym - 0.14 * cm, initial)

        # Label + value
        canvas.setFont(font_name, 6.5)
        canvas.setFillColor(c.HexColor(GRAY))
        canvas.drawString(LM + icon_r * 2 + 0.8 * cm, ym + 0.25 * cm, label)
        canvas.setFont(font_bold, 9)
        canvas.setFillColor(c.HexColor(DARK_BLUE))
        canvas.drawString(LM + icon_r * 2 + 0.8 * cm, ym - 0.2 * cm, value)
        ym -= 1.3 * cm

    # === Bottom ===
    canvas.setStrokeColor(c.HexColor('#e2e8f0'))
    canvas.setLineWidth(0.5)
    canvas.line(LM, 3.8 * cm, RM, 3.8 * cm)

    canvas.setFont(font_name, 7)
    canvas.setFillColor(c.HexColor(GRAY))
    canvas.drawString(LM, 3.1 * cm, 'APPROUVE PAR')
    canvas.setFont(font_bold, 8)
    canvas.setFillColor(c.HexColor(DARK_BLUE))
    canvas.drawString(LM, 2.5 * cm, 'Direction')

    canvas.setFont(font_bold, 13)
    canvas.setFillColor(c.HexColor(DARK_BLUE))
    canvas.drawRightString(RM, 3.1 * cm, 'DecisioBI')
    canvas.setFont(font_name, 7)
    canvas.setFillColor(c.HexColor(GRAY))
    canvas.drawRightString(RM, 2.5 * cm, 'Intelligent. Fiable. Utile.')

    # Thin accent line at very bottom
    canvas.setFillColor(c.HexColor(brand_color))
    canvas.rect(0, 0, W, 0.25 * cm, fill=True, stroke=False)

    canvas.restoreState()


def _draw_content_page(canvas, doc, branding, dashboard_name):
    """Draw header bar and footer for content pages."""
    from reportlab.lib import colors as c
    from reportlab.lib.units import cm

    canvas.saveState()
    W, H = doc.pagesize
    brand_color = branding.get('brand_color', MID_BLUE)

    # --- Header bar ---
    canvas.setFillColor(c.HexColor(DARK_BLUE))
    canvas.rect(0, H - 1.6 * cm, W, 1.6 * cm, fill=True, stroke=False)

    # Company name (left)
    canvas.setFillColor(c.white)
    canvas.setFont(_font(bold=True), 9)
    canvas.drawString(1.5 * cm, H - 1.1 * cm, branding['name'].upper())

    # Report title (right)
    canvas.setFont(_font(), 8)
    canvas.drawRightString(W - 1.5 * cm, H - 0.7 * cm, 'RAPPORT BUSINESS INTELLIGENCE')
    canvas.setFont(_font(), 7)
    canvas.drawRightString(W - 1.5 * cm, H - 1.15 * cm, dashboard_name)

    # Blue accent line
    canvas.setStrokeColor(c.HexColor(brand_color))
    canvas.setLineWidth(2.5)
    canvas.line(0, H - 1.6 * cm, W, H - 1.6 * cm)

    # --- Footer ---
    canvas.setFont(_font(), 7)
    canvas.setFillColor(c.HexColor('#9ca3af'))
    canvas.drawString(1.5 * cm, 0.8 * cm, 'Confidentiel - Usage interne uniquement')
    canvas.drawRightString(W - 1.5 * cm, 0.8 * cm, f'Page {doc.page}')

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Platypus content builders
# ---------------------------------------------------------------------------

def _build_executive_summary(widgets, normal_style, heading_style):
    """Build a brief executive summary section from widget data."""
    from reportlab.platypus import Paragraph, Spacer

    total = len(widgets)
    total_rows = sum(w.get('payload', {}).get('rows_processed', 0) for w in widgets)
    elements = [
        Paragraph('RESUME EXECUTIF', heading_style),
        Paragraph(
            f"Ce rapport presente une vue consolidee de la performance et de la qualite "
            f"des donnees. Il analyse <b>{total}</b> indicateur(s) a partir de "
            f"<b>{total_rows:,}</b> ligne(s) de donnees.",
            normal_style,
        ),
        Spacer(1, 6),
    ]
    return elements


def _build_metric_cards(widgets, brand_color):
    """Build a row of KPI metric cards from widget data."""
    from reportlab.lib import colors as c
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Table, TableStyle, Spacer, KeepTogether, Paragraph
    from reportlab.graphics.shapes import Drawing, Circle

    if not widgets:
        return []

    val_style = ParagraphStyle('CardVal', fontName=_font(bold=True), fontSize=14,
                               alignment=1, leading=18, spaceAfter=0)
    lbl_style = ParagraphStyle('CardLbl', fontName=_font(), fontSize=7,
                               textColor=c.HexColor(GRAY), alignment=1, leading=10, spaceAfter=0)

    cards_data = []
    for i, w in enumerate(widgets[:5]):
        payload = w.get('payload', {})
        value = payload.get('formatted_value', str(payload.get('value', 0)))
        label = w.get('title', f'Indicateur {i+1}')[:20]
        color = CARD_COLORS[i % len(CARD_COLORS)]
        cards_data.append((label, value, color))

    if not cards_data:
        return []

    n = len(cards_data)
    card_w = 3.3 * cm
    icon_size = 0.6 * cm

    cells_top = []
    cells_mid = []
    cells_bot = []
    for label, value, color in cards_data:
        d = Drawing(card_w, icon_size + 4)
        circle = Circle(card_w / 2, 2, icon_size / 2, fillColor=c.HexColor(color), strokeColor=None)
        d.add(circle)
        cells_top.append(d)
        cells_mid.append(Paragraph(str(value), val_style))
        cells_bot.append(Paragraph(label, lbl_style))

    card_table = Table([cells_top, cells_mid, cells_bot], colWidths=[card_w] * n)
    card_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, -1), c.HexColor(LIGHT_GRAY)),
        ('BOX', (0, 0), (-1, -1), 0.5, c.HexColor('#e5e7eb')),
    ]))

    return [Spacer(1, 4), KeepTogether([card_table]), Spacer(1, 8)]


def _build_bar_chart(widget, brand_color, width=460, height=180):
    """Build a vertical bar chart from widget breakdown data."""
    from reportlab.lib import colors as c
    from reportlab.platypus import Spacer
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart

    payload = widget.get('payload', {})
    breakdown = payload.get('breakdown', [])
    group_by = payload.get('group_by', [])
    if not breakdown:
        return []

    dim_col = group_by[0] if group_by else list(breakdown[0].keys())[0]
    categories = []
    values = []
    for item in breakdown[:8]:
        cat = str(item.get(dim_col, ''))[:15]
        val = item.get('value', 0)
        if isinstance(val, str):
            try:
                val = float(val.replace(',', '').replace(' ', ''))
            except (ValueError, AttributeError):
                val = 0
        categories.append(cat)
        values.append(float(val))

    d = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 30
    chart.width = width - 80
    chart.height = height - 60
    chart.data = [values]
    chart.categoryAxis.categoryNames = categories
    chart.categoryAxis.labels.fontName = _font()
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = _font()
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = c.HexColor(brand_color)
    chart.bars[0].strokeColor = None
    chart.barWidth = max(8, min(30, (chart.width / max(len(categories), 1)) * 0.6))
    chart.groupSpacing = 10
    d.add(chart)
    return [d, Spacer(1, 6)]


def _build_donut_chart(widget, brand_color, width=220, height=180):
    """Build a donut/pie chart from widget breakdown data."""
    from reportlab.lib import colors as c
    from reportlab.platypus import Spacer
    from reportlab.graphics.shapes import Drawing, String, Rect
    from reportlab.graphics.charts.piecharts import Pie

    payload = widget.get('payload', {})
    breakdown = payload.get('breakdown', [])
    group_by = payload.get('group_by', [])
    if not breakdown or len(breakdown) < 2:
        return []

    dim_col = group_by[0] if group_by else list(breakdown[0].keys())[0]
    labels_list = []
    values = []
    for item in breakdown[:6]:
        cat = str(item.get(dim_col, ''))[:15]
        val = item.get('value', 0)
        if isinstance(val, str):
            try:
                val = float(val.replace(',', '').replace(' ', ''))
            except (ValueError, AttributeError):
                val = 0
        labels_list.append(cat)
        values.append(float(val))

    pie_colors = [c.HexColor(clr) for clr in CARD_COLORS[:len(values)]]

    d = Drawing(width, height)
    pie = Pie()
    pie.x = 30
    pie.y = 20
    pie.width = 120
    pie.height = 120
    pie.data = values
    pie.labels = None
    pie.slices.strokeWidth = 1
    pie.slices.strokeColor = c.white
    for i, clr in enumerate(pie_colors):
        pie.slices[i].fillColor = clr
    d.add(pie)

    for i, lbl in enumerate(labels_list):
        y_pos = 130 - i * 16
        d.add(Rect(165, y_pos - 3, 8, 8, fillColor=pie_colors[i % len(pie_colors)], strokeColor=None))
        d.add(String(177, y_pos - 1, lbl, fontSize=7, fontName=_font(), fillColor=c.HexColor(GRAY)))

    return [d, Spacer(1, 6)]


def _build_data_quality(widgets, normal_style, heading_style, brand_color):
    """Build a data quality section from widget data."""
    from reportlab.lib import colors as c
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    quality_items = []
    for w in widgets:
        payload = w.get('payload', {})
        rows = payload.get('rows_processed', 0)
        breakdown = payload.get('breakdown', [])
        if rows > 0:
            quality_items.append({
                'name': w.get('title', 'Indicateur'),
                'rows': rows,
                'has_breakdown': len(breakdown) > 0,
            })

    if not quality_items:
        return []

    elements = [
        Paragraph('QUALITE DES DONNEES', heading_style),
        Spacer(1, 4),
    ]

    header = ['Indicateur', 'Lignes analysees', 'Details']
    data = [header]
    for qi in quality_items[:10]:
        data.append([
            qi['name'][:30],
            f"{qi['rows']:,}",
            'Disponible' if qi['has_breakdown'] else 'Statistiques',
        ])

    t = Table(data, colWidths=[180, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c.HexColor(brand_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), c.white),
        ('FONTNAME', (0, 0), (-1, 0), _font(bold=True)),
        ('FONTNAME', (0, 1), (-1, -1), _font()),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, c.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [c.white, c.HexColor(LIGHT_GRAY)]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))
    return elements


def _build_insights(widgets, normal_style, heading_style):
    """Build an insights section from widget data."""
    from reportlab.platypus import Paragraph, Spacer

    elements = [
        Paragraph('POINTS CLES', heading_style),
        Spacer(1, 4),
    ]

    total = len(widgets)
    if total == 0:
        elements.append(Paragraph("Aucune donnee disponible pour generer des insights.", normal_style))
        return elements

    total_rows = sum(w.get('payload', {}).get('rows_processed', 0) for w in widgets)
    elements.append(Paragraph(
        f"<b>{total}</b> indicateur(s) analyse(s) a partir de <b>{total_rows:,}</b> lignes de donnees.",
        normal_style,
    ))

    for i, w in enumerate(widgets[:5]):
        payload = w.get('payload', {})
        value = payload.get('formatted_value', str(payload.get('value', 0)))
        label = w.get('title', f'Indicateur {i+1}')
        elements.append(Paragraph(
            f"<b>{label}</b> : valeur aggregée de <b>{value}</b>.",
            normal_style,
        ))

    elements.append(Spacer(1, 8))
    return elements


# ---------------------------------------------------------------------------
# Main PDF generation
# ---------------------------------------------------------------------------

def generate_dashboard_pdf(
    user: User,
    dashboard_name: str,
    source_name: str,
    widgets: List[Dict[str, Any]],
    title: str = "Rapport DécisioBI",
) -> Optional[bytes]:
    """Generate a professional multi-page PDF report."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            BaseDocTemplate, PageTemplate, Frame, NextPageTemplate,
            Paragraph, Spacer, PageBreak, KeepTogether,
        )
    except ImportError:
        logger.warning("reportlab not installed; cannot generate PDF reports")
        return None

    _register_fonts()
    branding = get_company_branding(user)
    brand_color = branding.get('brand_color', MID_BLUE)
    buffer = io.BytesIO()
    W, H = A4

    # --- Styles ---
    styles = getSampleStyleSheet()

    section_heading = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontSize=11, spaceAfter=6, spaceBefore=12,
        textColor=colors.HexColor(brand_color),
        fontName=_font(bold=True),
    )
    normal = ParagraphStyle(
        'ReportNormal', parent=styles['Normal'],
        fontSize=8.5, spaceAfter=4, leading=12,
        fontName=_font(),
    )

    # --- Document with two templates ---
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2.2 * cm, bottomMargin=1.5 * cm,
    )

    cover_frame = Frame(0, 0, W, H, leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0)
    content_frame = Frame(1.5 * cm, 1.5 * cm, W - 3 * cm, H - 3.7 * cm)

    cover_template = PageTemplate(
        id='cover', frames=[cover_frame],
        onPage=lambda c, d: _draw_cover_page(c, d, branding, dashboard_name, source_name, widgets),
    )
    content_template = PageTemplate(
        id='content', frames=[content_frame],
        onPage=lambda c, d: _draw_content_page(c, d, branding, dashboard_name),
    )
    doc.addPageTemplates([cover_template, content_template])

    # --- Story ---
    story = []

    # Cover page (blank - canvas draws everything)
    story.append(NextPageTemplate('content'))
    story.append(PageBreak())

    # Executive summary
    story.extend(_build_executive_summary(widgets, normal, section_heading))

    # KPI cards
    story.extend(_build_metric_cards(widgets, brand_color))

    # Charts from breakdowns
    has_donut = False
    for w in widgets:
        payload = w.get('payload', {})
        breakdown = payload.get('breakdown', [])
        if not breakdown or len(breakdown) < 2:
            continue

        chart_title = w.get('title', 'Analyse')
        if not has_donut and len(breakdown) >= 3:
            story.append(Paragraph(f'Repartition - {chart_title}', section_heading))
            story.extend(_build_donut_chart(w, brand_color))
            has_donut = True
        else:
            story.append(Paragraph(f'{chart_title}', section_heading))
            story.extend(_build_bar_chart(w, brand_color))

    # Data quality
    story.extend(_build_data_quality(widgets, normal, section_heading, brand_color))

    # Insights
    story.extend(_build_insights(widgets, normal, section_heading))

    # Build
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# KPI Report PDF
# ---------------------------------------------------------------------------

def generate_kpi_report_pdf(
    user: User,
    kpi_context: List[Dict[str, Any]],
    title: str = "Rapport KPI DécisioBI",
    include_charts: bool = True,
) -> Optional[bytes]:
    """Generate a PDF report with KPI data."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError:
        logger.warning("reportlab not installed; cannot generate PDF reports")
        return None

    _register_fonts()
    branding = get_company_branding(user)
    brand_color = branding.get('brand_color', MID_BLUE)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            onFirstPage=lambda c, d: _draw_content_page(c, d, branding, title),
                            onLaterPages=lambda c, d: _draw_content_page(c, d, branding, title))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'KTitle', parent=styles['Title'],
        fontSize=18, spaceAfter=4, textColor=colors.HexColor(brand_color),
        fontName=_font(bold=True),
    )
    heading_style = ParagraphStyle(
        'KHeading', parent=styles['Heading2'],
        fontSize=12, spaceAfter=8, textColor=colors.HexColor(GOLD),
        fontName=_font(bold=True),
    )
    normal_style = ParagraphStyle(
        'KNormal', parent=styles['Normal'],
        fontSize=9, spaceAfter=6, fontName=_font(),
    )

    story = []

    report_title = title if title != "Rapport KPI DécisioBI" else f"Rapport KPI - {branding['name']}"
    story.append(Paragraph(report_title, title_style))
    story.append(Paragraph(
        f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')} par {user.get_full_name() or user.username}",
        normal_style,
    ))
    story.append(Spacer(1, 12))

    on_target = sum(1 for k in kpi_context if k.get('status') == 'on_target')
    warning = sum(1 for k in kpi_context if k.get('status') == 'warning')
    critical = sum(1 for k in kpi_context if k.get('status') == 'critical')

    story.append(Paragraph("Resume", heading_style))
    summary_data = [
        ['Indicateur', 'Valeur'],
        ['Total KPIs', str(len(kpi_context))],
        ['Sous controle', str(on_target)],
        ['A surveiller', str(warning)],
        ['Critiques', str(critical)],
    ]
    summary_table = Table(summary_data, colWidths=[120, 80])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(brand_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), _font(bold=True)),
        ('FONTNAME', (0, 1), (-1, -1), _font()),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_GRAY)]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Detail des KPIs", heading_style))
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
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(brand_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), _font(bold=True)),
            ('FONTNAME', (0, 1), (-1, -1), _font()),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT_GRAY)]),
        ]))
        story.append(kpi_table)
    else:
        story.append(Paragraph("Aucun KPI disponible.", normal_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Pivot Report PDF
# ---------------------------------------------------------------------------

def generate_pivot_report_pdf(
    user: User,
    pivot_data: dict,
    title: str = "Tableau Croise Dynamique",
) -> Optional[bytes]:
    """Generate a PDF report from pivot table data."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError:
        logger.warning("reportlab not installed; cannot generate PDF reports")
        return None

    _register_fonts()
    branding = get_company_branding(user)
    brand_color = branding.get('brand_color', MID_BLUE)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            onFirstPage=lambda c, d: _draw_content_page(c, d, branding, title),
                            onLaterPages=lambda c, d: _draw_content_page(c, d, branding, title))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'PTitle', parent=styles['Title'],
        fontSize=18, spaceAfter=10, textColor=colors.HexColor(brand_color),
        fontName=_font(bold=True),
    )
    normal_style = ParagraphStyle(
        'PNormal', parent=styles['Normal'],
        fontSize=9, spaceAfter=4, fontName=_font(),
    )

    story = []

    story.append(Paragraph(title, title_style))
    story.append(Paragraph(
        f"Genere le {timezone.now().strftime('%d/%m/%Y a %H:%M')} par {user.get_full_name() or user.username}",
        normal_style,
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
        col_width = (landscape(A4)[0] - 3 * cm) / n_cols
        col_widths = [col_width * 1.5] + [col_width] * (n_cols - 1)

        data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        data_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(brand_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), _font(bold=True)),
            ('FONTNAME', (0, 1), (-1, -1), _font()),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor(LIGHT_GRAY)]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8edf3')),
            ('FONTNAME', (0, -1), (-1, -1), _font(bold=True)),
        ]))
        story.append(data_table)
    else:
        story.append(Paragraph("Aucune donnee disponible.", normal_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
