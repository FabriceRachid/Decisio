from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.db import models
from django.contrib.auth.models import User

from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData
from apps.kpi.models import KPI


PRODUCT_KEYS = ('product', 'produit', 'sku', 'item', 'article', 'designation')
CLIENT_KEYS = ('client', 'customer', 'account', 'partner', 'customer_name', 'client_name')
TERRITORY_KEYS = ('region', 'zone', 'territory', 'city', 'ville', 'country', 'pays', 'agency', 'agence', 'depot')
AMOUNT_KEYS = ('total', 'amount', 'revenue', 'ca', 'sales', 'montant', 'total_amount', 'net_amount')
QUANTITY_KEYS = ('quantity', 'quantite', 'qty', 'volume', 'units', 'unites')
DATE_KEYS = ('date', 'order_date', 'sale_date', 'transaction_date', 'document_date')
CATEGORY_KEYS = ('categorie', 'category', 'famille', 'subcategory', 'productcategory', 'device_type')

COUNTRY_KEYWORDS = (
    'country', 'pays', 'nation', 'region', 'territory', 'state',
    'ville', 'city', 'geo', 'geography', 'geographie',
)

TIME_KEYWORDS = (
    'date', 'month', 'mois', 'year', 'annee', 'annee', 'quarter', 'trimestre',
    'week', 'semaine', 'jour', 'day',
)

MEASURE_ICONS = {
    'montant_total': 'dollar',
    'amount': 'dollar',
    'sales': 'dollar',
    'revenue': 'dollar',
    'ca': 'dollar',
    'total': 'dollar',
    'quantite': 'package',
    'quantity': 'package',
    'qty': 'package',
    'units': 'package',
    'stock_final': 'package',
    'stock': 'package',
    'client': 'users',
    'customer': 'users',
    'nombre': 'hash',
    'count': 'hash',
    'nb_commandes': 'shopping-cart',
    'order_id': 'shopping-cart',
}


def _normalize_mapping(row: dict) -> dict[str, object]:
    return {str(key).strip().lower(): value for key, value in row.items()}


def _first_value(row: dict[str, object], candidates: Iterable[str]) -> object | None:
    for key in candidates:
        if key in row and row[key] not in (None, ''):
            return row[key]
    return None


def _parse_decimal(value: object) -> Decimal | None:
    if value in (None, ''):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    raw = str(value).strip().replace('\xa0', '').replace(' ', '')
    if not raw:
        return None
    raw = raw.replace(',', '.')
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _parse_date(value: object) -> datetime | None:
    if value in (None, ''):
        return None

    raw = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _source_queryset_for_user(user: User):
    qs = DataSource.objects.filter(status='completed', is_archived=False).order_by('-created_at')
    if user.is_superuser:
        return qs
    return qs.filter(uploaded_by=user)


def build_business_rankings(user: User, source_limit: int = 10) -> dict:
    sources = list(_source_queryset_for_user(user)[:source_limit])
    source_ids = [source.id for source in sources]

    product_totals: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    product_qty: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    client_totals: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    territory_totals: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    trend_totals: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))

    revenue_total = Decimal('0')
    rows_count = 0

    rows = RawData.objects.filter(source_id__in=source_ids).values('data')
    for item in rows.iterator():
        row = _normalize_mapping(item['data'] or {})
        rows_count += 1

        amount = _parse_decimal(_first_value(row, AMOUNT_KEYS)) or Decimal('0')
        quantity = _parse_decimal(_first_value(row, QUANTITY_KEYS)) or Decimal('0')
        product = _first_value(row, PRODUCT_KEYS)
        client = _first_value(row, CLIENT_KEYS)
        territory = _first_value(row, TERRITORY_KEYS)
        row_date = _parse_date(_first_value(row, DATE_KEYS))

        revenue_total += amount

        if product:
            product_key = str(product).strip()
            product_totals[product_key] += amount
            product_qty[product_key] += quantity

        if client:
            client_key = str(client).strip()
            client_totals[client_key] += amount

        if territory:
            territory_key = str(territory).strip()
            territory_totals[territory_key] += amount

        if row_date:
            trend_key = row_date.strftime('%b %Y')
            trend_totals[trend_key] += amount

    def _format_amount(value: Decimal) -> str:
        return f"{float(value):,.2f}".replace(',', ' ')

    products_sorted = sorted(product_totals.items(), key=lambda item: item[1], reverse=True)[:5]
    clients_sorted = sorted(client_totals.items(), key=lambda item: item[1], reverse=True)[:5]
    territories_sorted = sorted(territory_totals.items(), key=lambda item: item[1], reverse=True)[:6]

    return {
        'summary': {
            'sources_count': len(source_ids),
            'rows_count': rows_count,
            'revenue_total': float(revenue_total),
        },
        'sales_trend': [
            {'label': label, 'value': float(value)}
            for label, value in sorted(trend_totals.items(), key=lambda item: datetime.strptime(item[0], '%b %Y'))
        ],
        'top_products': [
            {
                'name': name,
                'revenue': float(total),
                'revenue_label': _format_amount(total),
                'quantity': float(product_qty[name]),
            }
            for name, total in products_sorted
        ],
        'top_clients': [
            {
                'name': name,
                'revenue': float(total),
                'revenue_label': _format_amount(total),
                'share_percent': round(float((total / revenue_total) * 100), 2) if revenue_total else 0,
            }
            for name, total in clients_sorted
        ],
        'territories': [
            {
                'name': name,
                'revenue': float(total),
                'revenue_label': _format_amount(total),
                'share_percent': round(float((total / revenue_total) * 100), 2) if revenue_total else 0,
            }
            for name, total in territories_sorted
        ],
    }


def _user_source_ids(user: User) -> list[int]:
    qs = DataSource.objects.filter(status='completed', is_archived=False)
    if not user.is_superuser:
        qs = qs.filter(uploaded_by=user)
    return list(qs.values_list('id', flat=True)[:10])


def discover_available_columns(user: User) -> list[str]:
    column_names: set[str] = set()
    source_ids = _user_source_ids(user)
    if not source_ids:
        return []

    for payload in RawData.objects.filter(source_id__in=source_ids).values_list('data', flat=True)[:500]:
        if isinstance(payload, dict):
            column_names.update(str(key) for key in payload.keys())

    for payload in CleanedData.objects.filter(job__source_id__in=source_ids).values_list('data', flat=True)[:500]:
        if isinstance(payload, dict):
            column_names.update(str(key) for key in payload.keys())

    column_names.update({'date', 'region', 'produit', 'categorie', 'vendeur', 'client', 'montant_total', 'quantite'})
    return sorted(column_names)


def discover_available_kpis(user: User) -> list[str]:
    qs = KPI.objects.filter(is_active=True)
    if not user.is_superuser:
        qs = qs.filter(models.Q(is_public=True) | models.Q(owner=user))
    return sorted({kpi.code for kpi in qs} | {kpi.name for kpi in qs})


def _detect_column_type(col_name: str, col_info: dict) -> str:
    """Detect the semantic type of a column for smart widget selection."""
    normalized = col_name.lower().replace('_', '').replace(' ', '')

    if any(kw in normalized for kw in COUNTRY_KEYWORDS):
        return 'geo'
    if any(kw in normalized for kw in TIME_KEYWORDS):
        return 'time'
    if any(kw in normalized for kw in ('categorie', 'category', 'famille', 'type', 'mode', 'device')):
        return 'category'
    if any(kw in normalized for kw in ('product', 'produit', 'article', 'item', 'sku', 'designation')):
        return 'product'
    if any(kw in normalized for kw in ('client', 'customer', 'account', 'partner')):
        return 'client'
    if any(kw in normalized for kw in ('region', 'zone', 'territory', 'pays', 'country', 'city', 'ville', 'depot', 'agence')):
        return 'geo'
    return 'other'


def _build_smart_widget_defs(
    suggestions: list[dict],
    numeric_cols: list[dict],
    categorical_cols: list[dict],
    date_cols: list[dict],
) -> list[dict]:
    """
    Build an optimized list of widget definitions based on detected columns.
    Priority: KPI cards (4 max) → Geo map → Time trend → Category donut → Ranking bars.
    """
    widget_defs: list[dict] = []
    used_measures: set[str] = set()
    used_dimensions: set[str] = set()

    for s in suggestions:
        if s['measure_column'] in used_measures:
            continue
        if 'par ' in s['label']:
            continue
        used_measures.add(s['measure_column'])
        widget_defs.append({
            'type': 'metric_card',
            'title': s['label'],
            'measure': s['measure_column'],
            'aggregation': s['aggregation'],
            'group_by': None,
            'semantic_type': 'kpi',
        })
        if len([w for w in widget_defs if w['type'] == 'metric_card']) >= 4:
            break

    if not widget_defs:
        for col in numeric_cols[:4]:
            used_measures.add(col['name'])
            widget_defs.append({
                'type': 'metric_card',
                'title': col['name'],
                'measure': col['name'],
                'aggregation': 'sum',
                'group_by': None,
                'semantic_type': 'kpi',
            })

    first_measure = next(iter(used_measures), None) or (numeric_cols[0]['name'] if numeric_cols else None)
    second_measure = list(used_measures)[1] if len(used_measures) > 1 else (numeric_cols[1]['name'] if len(numeric_cols) > 1 else None)

    first_agg = 'sum'
    for s in suggestions:
        if s['measure_column'] == first_measure:
            first_agg = s['aggregation']
            break

    geo_cols = [c for c in categorical_cols if _detect_column_type(c['name'], c) == 'geo']
    time_cols = date_cols
    category_cols = [c for c in categorical_cols if _detect_column_type(c['name'], c) == 'category']
    product_cols = [c for c in categorical_cols if _detect_column_type(c['name'], c) == 'product']
    client_cols = [c for c in categorical_cols if _detect_column_type(c['name'], c) == 'client']

    agg_label = {'sum': 'Total', 'mean': 'Moyenne', 'count': 'Nombre', 'max': 'Maximum', 'min': 'Minimum'}

    # Use second measure for charts to avoid showing the same data everywhere
    chart_measure = second_measure or first_measure
    chart_agg = 'sum'
    for s in suggestions:
        if s['measure_column'] == chart_measure:
            chart_agg = s['aggregation']
            break

    used_configs: set[tuple] = set()
    def _add_chart(wtype, title, measure, aggregation, group_by, semantic):
        key = (measure, aggregation, group_by if isinstance(group_by, str) else None)
        if key not in used_configs:
            used_configs.add(key)
            widget_defs.append({
                'type': wtype, 'title': title,
                'measure': measure, 'aggregation': aggregation,
                'group_by': group_by, 'semantic_type': semantic,
            })

    # Max 3 charts: one geo, one time, one ranking/category
    charts_added = 0
    if geo_cols and first_measure:
        geo = geo_cols[0]
        if geo['name'] not in used_dimensions:
            used_dimensions.add(geo['name'])
            _add_chart('world_map',
                f"{agg_label.get(first_agg, 'Total')} de {prettify_field(first_measure)} par {prettify_field(geo['name'])}",
                first_measure, first_agg, geo['name'], 'geo')
            charts_added += 1

    if charts_added < 3 and time_cols and first_measure:
        tc = time_cols[0]
        if tc['name'] not in used_dimensions:
            used_dimensions.add(tc['name'])
            _add_chart('area_chart',
                f"Évolution de {prettify_field(first_measure)} par {prettify_field(tc['name'])}",
                first_measure, first_agg, tc['name'], 'trend')
            charts_added += 1

    if charts_added < 3 and category_cols and chart_measure:
        cc = category_cols[0]
        if cc['name'] not in used_dimensions:
            used_dimensions.add(cc['name'])
            _add_chart('pie_chart',
                f"Répartition de {prettify_field(chart_measure)} par {prettify_field(cc['name'])}",
                chart_measure, chart_agg, cc['name'], 'category')
            charts_added += 1

    if charts_added < 3 and product_cols and chart_measure:
        pc = product_cols[0]
        if pc['name'] not in used_dimensions:
            used_dimensions.add(pc['name'])
            _add_chart('bar_chart',
                f"Classement des {prettify_field(pc['name'])} par {prettify_field(chart_measure)}",
                chart_measure, chart_agg, pc['name'], 'ranking')
            charts_added += 1

    if charts_added < 3 and client_cols and chart_measure:
        cc = client_cols[0]
        if cc['name'] not in used_dimensions:
            used_dimensions.add(cc['name'])
            _add_chart('bar_chart',
                f"Classement des {prettify_field(cc['name'])} par {prettify_field(chart_measure)}",
                chart_measure, chart_agg, cc['name'], 'ranking')
            charts_added += 1

    return widget_defs


def prettify_field(value: str) -> str:
    """Convert a field name to a human-readable label."""
    return value.replace('_', ' ').replace('-', ' ').title()


def auto_build_dashboard(user: User, source_id: int, period_start: date | None = None, period_end: date | None = None, filters: dict | None = None) -> dict:
    """
    Génère automatiquement un dashboard complet à partir des colonnes détectées.
    Crée un Dashboard persisté avec des widgets, calcule les métriques, retourne le tout.
    """
    from apps.dashboard.models import Dashboard, Widget
    from apps.kpi.auto_service import KPIAutoService
    from apps.kpi.services import M4WorkbenchService

    source = _source_queryset_for_user(user).filter(pk=source_id).first()
    if source is None:
        raise ValueError("Source introuvable ou non autorisée.")

    try:
        detected = KPIAutoService().detect_and_suggest(source=source)
    except ValueError as e:
        raise ValueError(f"Impossible d'analyser la source : {e}")
    except Exception as e:
        raise ValueError(f"Erreur lors de l'analyse de la source : {e}")

    workbench = M4WorkbenchService(user)
    domain = detected.get('domain_profile', {}).get('domain', 'generic')

    dashboard, _ = Dashboard.objects.get_or_create(
        created_by=user,
        slug=f"dashboard-auto-{user.id}-{source.id}",
        defaults={
            'name': source.name,
            'description': f"Dashboard automatique — {source.name}",
            'layout': {'columns': 4},
            'grid_columns': 12,
        },
    )

    suggestions = detected.get('suggestions', [])
    numeric_cols = detected.get('columns', {}).get('numeric', [])
    categorical_cols = detected.get('columns', {}).get('categorical', [])
    date_cols = detected.get('columns', {}).get('date', [])

    for w in dashboard.widgets.all():
        if w.configuration.get('auto_generated') is not False:
            w.delete()

    widget_defs = _build_smart_widget_defs(suggestions, numeric_cols, categorical_cols, date_cols)

    WIDGET_SIZES = {
        'metric_card': {'width': 3, 'height': 2},
        'world_map': {'width': 7, 'height': 6},
        'area_chart': {'width': 5, 'height': 6},
        'line_chart': {'width': 5, 'height': 6},
        'pie_chart': {'width': 4, 'height': 4},
        'bar_chart': {'width': 4, 'height': 4},
        'radar': {'width': 4, 'height': 4},
        'treemap': {'width': 4, 'height': 4},
    }

    # Check if source has sheet relations → use rawdata with joined view
    has_relations = source.sheet_relations.filter(is_active=True).exists()
    source_table = 'ingestion_rawdata' if has_relations else 'nettoyage_cleaneddata'

    for i, wdef in enumerate(widget_defs):
        title = wdef['title']
        group_by = wdef.get('group_by')
        widget_type = wdef['type']

        config = {
            'measure': wdef['measure'],
            'aggregation': wdef['aggregation'],
            'group_by': [group_by] if group_by else [],
            'source_table': source_table,
            'source_id': source.id,
            'auto_generated': True,
            'semantic_type': wdef.get('semantic_type', 'other'),
        }
        if has_relations:
            config['use_joined_view'] = True
        if period_start:
            config['period_start'] = period_start.isoformat()
        if period_end:
            config['period_end'] = period_end.isoformat()

        sizes = WIDGET_SIZES.get(widget_type, {'width': 4, 'height': 4})

        if widget_type == 'metric_card':
            kpi_index = len([w for w in Widget.objects.filter(dashboard=dashboard) if w.widget_type == 'metric_card'])
            position_x = (kpi_index % 4) * 3
            position_y = 0
        elif widget_type in ('world_map', 'area_chart', 'line_chart'):
            large_index = len([w for w in Widget.objects.filter(dashboard=dashboard) if w.widget_type in ('world_map', 'area_chart', 'line_chart')])
            position_x = large_index * sizes['width']
            position_y = 4
        else:
            medium_index = len([w for w in Widget.objects.filter(dashboard=dashboard) if w.widget_type not in ('metric_card', 'world_map', 'area_chart', 'line_chart')])
            position_x = medium_index * sizes['width']
            position_y = 9

        Widget.objects.create(
            dashboard=dashboard,
            widget_type=widget_type,
            position_x=position_x,
            position_y=position_y,
            width=sizes['width'],
            height=sizes['height'],
            data_source_type='kpi',
            data_source_id=source.id,
            configuration=config,
            title=title,
            name=title,
            is_visible=True,
        )

    seen: set[tuple] = set()
    for w in dashboard.widgets.all():
        if w.configuration.get('auto_generated') is False:
            continue
        config = w.configuration or {}
        key = (
            config.get('measure', ''),
            config.get('aggregation', ''),
            tuple(config.get('group_by') or []),
            w.widget_type,
        )
        if key in seen:
            w.delete()
        else:
            seen.add(key)

    widgets_result = []
    all_widgets = dashboard.widgets.all().order_by('position_y', 'position_x')
    for w in all_widgets:
        config = dict(w.configuration)
        config.pop('auto_generated', None)
        if filters:
            config['filters'] = filters
        try:
            payload = workbench.calculate_metric(config)
        except Exception:
            payload = {
                'nom_kpi': w.title, 'value': 0, 'formatted_value': '0',
                'rows_processed': 0, 'breakdown': [], 'chart_type': w.widget_type,
                'data_quality_score': 0,
            }
        widgets_result.append({
            'id': w.id,
            'title': w.title,
            'type': w.widget_type,
            'position': {'x': w.position_x, 'y': w.position_y, 'w': w.width, 'h': w.height},
            'payload': payload,
            'auto_generated': w.configuration.get('auto_generated', True),
            'chart_type_override': w.configuration.get('chart_type_override'),
        })

    return {
        'dashboard': {
            'id': dashboard.id,
            'name': dashboard.name,
            'slug': dashboard.slug,
            'source_name': source.name,
            'source_id': source.id,
            'domain': domain,
        },
        'widgets': widgets_result,
    }


def add_widget_to_dashboard(user: User, source_id: int, config: dict) -> dict:
    """Ajoute un widget personnalisé au dashboard automatique.

    Crée le dashboard s'il n'existe pas encore (auto-création).
    Accepte un breakdown pré-calculé (depuis le TCD) pour conserver la même visualisation.
    """
    from apps.dashboard.models import Dashboard, Widget
    from apps.kpi.auto_service import KPIAutoService
    from apps.kpi.services import M4WorkbenchService

    source = _source_queryset_for_user(user).filter(pk=source_id).first()
    if source is None:
        raise ValueError("Source introuvable ou non autorisée.")

    dashboard = Dashboard.objects.filter(created_by=user, slug=f"dashboard-auto-{user.id}-{source_id}").first()
    if not dashboard:
        try:
            detected = KPIAutoService().detect_and_suggest(source=source)
        except Exception:
            detected = {'domain_profile': {'domain': 'generic'}}
        domain = detected.get('domain_profile', {}).get('domain', 'generic')
        dashboard = Dashboard.objects.create(
            created_by=user,
            slug=f"dashboard-auto-{user.id}-{source.id}",
            name=source.name,
            description=f"Dashboard automatique — {source.name}",
            layout={'columns': 4},
            grid_columns=12,
        )

    title = config.get('title') or config.get('measure') or 'Indicateur personnalisé'
    measure = config.get('measure', '')
    aggregation = config.get('aggregation', 'sum')
    group_by = config.get('group_by', [])
    if isinstance(group_by, str):
        group_by = [group_by] if group_by else []

    is_chart = bool(group_by)
    request_filters = config.get('filters') or []

    chart_type_map = {
        "bar": "bar_chart",
        "line": "line_chart",
        "area": "area_chart",
        "donut": "pie_chart",
    }
    incoming_chart = config.get('chart_type', '')
    widget_type = chart_type_map.get(incoming_chart, 'bar_chart' if is_chart else 'metric_card')

    widget_config = {
        'measure': measure,
        'aggregation': aggregation,
        'group_by': group_by,
        'source_table': 'nettoyage_cleaneddata',
        'source_id': source_id,
        'auto_generated': False,
    }

    # Éviter les doublons manuels : si le même widget est ajouté 2x, on met à jour
    existing_manual = Widget.objects.filter(
        dashboard=dashboard,
        widget_type=widget_type,
    )
    dup = None
    for w in existing_manual:
        if w.configuration.get('auto_generated') is not False:
            continue
        cfg = w.configuration or {}
        if cfg.get('measure') == measure and cfg.get('aggregation') == aggregation and cfg.get('group_by') == group_by:
            dup = w
            break
    if dup:
        dup.title = title
        dup.name = title
        dup.save(update_fields=['title', 'name', 'updated_at'])
        widget = dup
    else:
        count = dashboard.widgets.count()
        widget = Widget.objects.create(
            dashboard=dashboard,
            widget_type=widget_type,
            position_x=(count % 4) * 3,
            position_y=(count // 4) * 2,
            width=6 if is_chart else 3,
            height=2,
            data_source_type='kpi',
            data_source_id=source_id,
            configuration=widget_config,
            title=title,
            name=title,
            is_visible=True,
        )

    precomputed_breakdown = config.get('breakdown')
    if precomputed_breakdown:
        total_value = sum(
            (row.get('value') or 0) for row in precomputed_breakdown
        ) if isinstance(precomputed_breakdown, list) else 0
        payload = {
            'nom_kpi': title,
            'measure': measure,
            'aggregation': aggregation,
            'group_by': group_by,
            'value': total_value,
            'formatted_value': f"{total_value:,.0f}".replace(',', ' '),
            'breakdown': precomputed_breakdown,
            'chart_type': widget_type,
            'rows_processed': 0,
            'data_quality_score': 100,
        }
    else:
        workbench = M4WorkbenchService(user)
        try:
            calc_config = dict(widget_config)
            if request_filters:
                calc_config['filters'] = request_filters
            payload = workbench.calculate_metric(calc_config)
        except Exception:
            payload = {
                'nom_kpi': title, 'value': 0, 'formatted_value': '0',
                'rows_processed': 0, 'breakdown': [], 'chart_type': widget.widget_type,
                'data_quality_score': 0,
            }

    return {
        'id': widget.id,
        'title': widget.title,
        'type': widget.widget_type,
        'position': {'x': widget.position_x, 'y': widget.position_y, 'w': widget.width, 'h': widget.height},
        'payload': payload,
        'auto_generated': widget.configuration.get('auto_generated', True),
        'chart_type_override': widget.configuration.get('chart_type_override'),
    }


def default_preferences_for_role(role: str) -> dict:
    if role == 'analyst':
        return {
            'colonnes_tableau': ['date', 'produit', 'quantite', 'montant_total', 'vendeur', 'region'],
            'kpis_visibles': ['CA', 'rotation_stocks', 'nb_commandes', 'valeur_stock'],
            'kpis_ordre': ['CA', 'rotation_stocks', 'nb_commandes', 'valeur_stock'],
            'layout_dashboard': {'colonnes': 4, 'widgets': []},
            'periode_defaut': 'mois_en_cours',
            'devise': 'FCFA',
            'format_nombres': 'fr-FR',
        }
    if role == 'admin':
        return {
            'colonnes_tableau': ['date', 'client', 'montant_total', 'region'],
            'kpis_visibles': ['CA', 'marge_brute', 'nb_commandes'],
            'kpis_ordre': ['CA', 'marge_brute', 'nb_commandes'],
            'layout_dashboard': {'colonnes': 4, 'widgets': []},
            'periode_defaut': 'mois_en_cours',
            'devise': 'FCFA',
            'format_nombres': 'fr-FR',
        }
    return {
        'colonnes_tableau': ['date', 'produit', 'montant_total'],
        'kpis_visibles': ['CA', 'nb_commandes'],
        'kpis_ordre': ['CA', 'nb_commandes'],
        'layout_dashboard': {'colonnes': 2, 'widgets': []},
        'periode_defaut': 'mois_en_cours',
        'devise': 'FCFA',
        'format_nombres': 'fr-FR',
    }
