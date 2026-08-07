"""
M4: KPI Calculation Services
Automatic KPI calculation, forecasting, anomaly detection, and alert management.
"""

import ast
import re
import json
import logging
from decimal import Decimal
from datetime import datetime, timedelta, date
from dateutil import parser as dateutil_parser
from typing import Dict, List, Any, Tuple, Optional
from collections import Counter

import numpy as np
import pandas as pd
from django.db import connection
from django.db.models import Avg, Sum, Count, Max, Min
from django.utils import timezone
from django.contrib.auth.models import User

from apps.kpi.models import KPI, KPICalculation, KPIAlert
from apps.kpi.auto_service import KPIAutoService
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData

logger = logging.getLogger(__name__)


class KPICalculationService:
    """
    Orchestrates automatic KPI calculation with multiple formula evaluation methods.
    Supports SQL, Python, and Excel-based formulas with safety guards.
    """
    
    DANGEROUS_SQL_KEYWORDS = (
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
        'TRUNCATE', 'CREATE', 'GRANT', 'REVOKE'
    )
    DANGEROUS_PYTHON_PATTERNS = (
        '__', '__import__', 'exec', 'eval', 'open', 'input',
        'file', 'compile', 'globals', 'locals', 'subprocess', 'pickle', 'os.'
    )

    def __init__(self, user: Optional[User] = None, safe_mode: bool = True):
        """
        Initialize KPI calculation service.
        
        Args:
            user: User executing the calculation (for audit trail)
            safe_mode: Enable safety guards for Python formula execution
        """
        self.user = user
        self.safe_mode = safe_mode
        self.allowed_functions = {
            'sum': sum, 'min': min, 'max': max, 'len': len, 'round': round,
            'abs': abs, 'int': int, 'float': float, 'str': str,
            'Decimal': Decimal
        }
        
    def calculate_kpi(self, kpi: KPI, period_start: date, period_end: date) -> Dict[str, Any]:
        """
        Calculate a single KPI for a specific period.
        
        Returns dict with:
        - calculated_value: The computed KPI value
        - variance_absolute: Difference from previous period
        - variance_percent: Percentage change
        - target_variance: Difference from target
        - status: on_target, warning, or critical
        - breakdown: By dimensions (region, product, etc.)
        - data_quality_score: Confidence in the calculation
        - rows_processed: How many rows used
        - execution_time_ms: Performance metric
        """
        try:
            start_time = timezone.now()
            
            # Evaluate formula based on type
            if kpi.formula_type == 'sql':
                result = self._evaluate_sql_formula(kpi, period_start, period_end)
            elif kpi.formula_type == 'python':
                result = self._evaluate_python_formula(kpi, period_start, period_end)
            else:
                result = self._evaluate_excel_formula(kpi, period_start, period_end)
            
            calculated_value = Decimal(str(result['value']))
            rows_processed = result.get('rows_processed', 0)
            breakdown = result.get('breakdown', {})
            
            # Get previous calculation for variance
            previous_calc = KPICalculation.objects.filter(
                kpi=kpi, period_end__lt=period_start
            ).order_by('-period_end').first()
            previous_value = previous_calc.calculated_value if previous_calc else None
            
            # Calculate variances
            variance_absolute = None
            variance_percent = None
            if previous_value is not None:
                variance_absolute = calculated_value - previous_value
                variance_percent = float((variance_absolute / previous_value * 100)) if previous_value != 0 else None
            
            target_variance = None
            if kpi.target_value is not None:
                target_variance = calculated_value - kpi.target_value
            
            # Determine status based on thresholds
            status = self._determine_status(calculated_value, kpi, variance_percent)
            
            # Data quality scoring
            data_quality_score = self._calculate_data_quality(rows_processed, result)
            
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return {
                'calculated_value': float(calculated_value),
                'previous_value': float(previous_value) if previous_value is not None else None,
                'variance_absolute': float(variance_absolute) if variance_absolute is not None else None,
                'variance_percent': variance_percent,
                'target_variance': float(target_variance) if target_variance is not None else None,
                'status': status,
                'breakdown': breakdown,
                'data_quality_score': data_quality_score,
                'rows_processed': rows_processed,
                'execution_time_ms': int(execution_time),
                'success': True
            }
        except Exception as e:
            logger.error(f"Error calculating KPI {kpi.code}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'calculated_value': None
            }
    
    def _evaluate_sql_formula(self, kpi: KPI, period_start: date, period_end: date) -> Dict[str, Any]:
        """
        Evaluate KPI using SQL formula.
        Safely execute SQL query with parameterized inputs.
        """
        try:
            source_table = kpi.source_table or 'ingestion_rawdata'
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', source_table):
                raise ValueError("Invalid source table identifier")

            # Add period parameters to formula
            formula = kpi.formula.format(
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                source_table=source_table
            )
            self._validate_sql_formula(formula)
            
            # Execute query
            with connection.cursor() as cursor:
                cursor.execute(formula)
                result = cursor.fetchone()
            
            if not result or result[0] is None:
                value = 0
            else:
                value = float(result[0])
            
            # Get row count for data quality
            rows_processed = 0
            try:
                count_query = f"SELECT COUNT(*) FROM ({formula}) AS ct"
                with connection.cursor() as cursor:
                    cursor.execute(count_query)
                    count_result = cursor.fetchone()
                    rows_processed = self._coerce_rows_processed(
                        count_result[0] if count_result else 0
                    )
            except Exception as exc:
                logger.debug("Row count query failed for %s: %s", kpi.name, exc)
            
            return {
                'value': value,
                'rows_processed': rows_processed,
                'breakdown': {}
            }
        except Exception as e:
            logger.error(f"SQL formula evaluation failed: {str(e)}")
            raise
    
    def _evaluate_python_formula(self, kpi: KPI, period_start: date, period_end: date) -> Dict[str, Any]:
        """
        Evaluate KPI using Python formula with safety guards (if safe_mode enabled).
        Restricted to mathematical and aggregation operations.
        """
        try:
            # Prepare execution context with safe functions
            context = {
                'np': np,
                'Decimal': Decimal,
                'period_start': period_start,
                'period_end': period_end,
                **self.allowed_functions
            }
            
            # Add data from source tables if referenced
            if kpi.source_table:
                data = self._get_table_data(kpi.source_table, period_start, period_end)
                context['data'] = data
                context['rows_processed'] = len(data)
            
            # Safety: whitelist allowed globals
            if self.safe_mode:
                formula = kpi.formula
                lower_formula = formula.lower()
                for pattern in self.DANGEROUS_PYTHON_PATTERNS:
                    if pattern.lower() in lower_formula:
                        raise ValueError(f"Dangerous pattern '{pattern}' not allowed in formula")
                try:
                    compiled_formula = compile(
                        ast.parse(formula, mode='eval'),
                        '<kpi_formula>',
                        'eval'
                    )
                except SyntaxError as exc:
                    raise ValueError("Python formula must be a single expression") from exc
            else:
                compiled_formula = compile(kpi.formula, '<kpi_formula>', 'eval')
            
            # Evaluate formula
            result = eval(compiled_formula, {"__builtins__": {}}, context)
            
            return {
                'value': float(result),
                'rows_processed': context.get('rows_processed', 0),
                'breakdown': {}
            }
        except Exception as e:
            logger.error(f"Python formula evaluation failed: {str(e)}")
            raise
    
    def _evaluate_excel_formula(self, kpi: KPI, period_start: date, period_end: date) -> Dict[str, Any]:
        """
        Evaluate KPI using Excel-style formulas (converted to Python).
        Supports: SUM, AVG, COUNT, MIN, MAX, etc.
        """
        try:
            # Get data
            data = self._get_table_data(kpi.source_table, period_start, period_end, kpi.measure_column)
            
            if len(data) == 0:
                return {'value': 0, 'rows_processed': 0, 'breakdown': {}}
            
            # Extract measure column
            values = [float(d.get(kpi.measure_column, 0)) for d in data if d.get(kpi.measure_column)]
            
            # Apply aggregation method
            if kpi.aggregation_method == 'SUM':
                result = sum(values)
            elif kpi.aggregation_method == 'AVG':
                result = sum(values) / len(values) if values else 0
            elif kpi.aggregation_method == 'COUNT':
                result = len(values)
            elif kpi.aggregation_method == 'MIN':
                result = min(values) if values else 0
            elif kpi.aggregation_method == 'MAX':
                result = max(values) if values else 0
            else:
                result = sum(values)
            
            return {
                'value': result,
                'rows_processed': len(data),
                'breakdown': self._calculate_dimensional_breakdown(data, kpi)
            }
        except Exception as e:
            logger.error(f"Excel formula evaluation failed: {str(e)}")
            raise
    
    @staticmethod
    def _normalize_tabular_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten ingestion/cleaning ORM rows so measure_column / dimensions
        match keys stored inside the JSON `data` payload (CSV columns).
        """
        if not isinstance(row, dict):
            return {}
        out = dict(row)
        payload = out.pop('data', None)
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key not in out:
                    out[key] = value
        return out

    def _get_table_data(self, table_name: str, period_start: date, period_end: date, 
                       column: str = None) -> List[Dict]:
        """Retrieve data from specified table within date range."""
        try:
            if table_name == 'ingestion_rawdata':
                qs = RawData.objects.filter(
                    ingested_at__date__gte=period_start,
                    ingested_at__date__lte=period_end,
                ).values()
                return [self._normalize_tabular_row(r) for r in list(qs)[:10000]]
            elif table_name == 'nettoyage_cleaneddata':
                qs = CleanedData.objects.filter(
                    cleaned_at__date__gte=period_start,
                    cleaned_at__date__lte=period_end,
                ).values()
                return [self._normalize_tabular_row(r) for r in list(qs)[:10000]]
            else:
                # Raw SQL fallback
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT * FROM {table_name} WHERE date_column BETWEEN %s AND %s LIMIT 10000",
                        [period_start, period_end]
                    )
                    return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error retrieving table data: {str(e)}")
            return []
    
    def _calculate_dimensional_breakdown(self, data: List[Dict], kpi: KPI) -> Dict[str, float]:
        """Break down KPI by dimensions (e.g., by region, product)."""
        if not kpi.dimension_columns or len(kpi.dimension_columns) == 0:
            return {}
        
        breakdown = {}
        try:
            for dim_col in kpi.dimension_columns[:3]:  # Limit to 3 dimensions
                dimension_totals = {}
                for row in data:
                    dim_value = row.get(dim_col, 'Unknown')
                    val = float(row.get(kpi.measure_column, 0))
                    dimension_totals[str(dim_value)] = dimension_totals.get(str(dim_value), 0) + val
                
                breakdown[dim_col] = dimension_totals
        except Exception as e:
            logger.warning(f"Error calculating dimensional breakdown: {str(e)}")
        
        return breakdown
    
    def _determine_status(self, value: Decimal, kpi: KPI, variance_percent: Optional[float]) -> str:
        """Determine KPI status (on_target, warning, critical)."""
        if kpi.critical_threshold is not None:
            if kpi.operator in ['<', '<=']:
                if value < kpi.critical_threshold:
                    return 'critical'
                elif kpi.warning_threshold is not None and value < kpi.warning_threshold:
                    return 'warning'
            elif kpi.operator in ['>', '>=']:
                if value > kpi.critical_threshold:
                    return 'critical'
                elif kpi.warning_threshold is not None and value > kpi.warning_threshold:
                    return 'warning'
        
        # Default to on_target if within thresholds
        return 'on_target'
    
    def _calculate_data_quality(self, rows_processed: int, result: Dict) -> float:
        """Calculate data quality score (0-100) based on data completeness."""
        if rows_processed == 0:
            return 0.0
        
        # Score based on row count (more rows = more confidence)
        quality = min(100.0, (rows_processed / 100) * 100)
        
        return round(quality, 2)

    def _validate_sql_formula(self, formula: str) -> None:
        """Reject obviously dangerous SQL formulas before execution."""
        normalized = formula.strip()
        upper_formula = normalized.upper()

        if not upper_formula.startswith('SELECT'):
            raise ValueError("SQL formula must start with SELECT")
        if ';' in normalized.rstrip(';'):
            raise ValueError("SQL formula must contain only one statement")
        if '--' in normalized or '/*' in normalized or '*/' in normalized:
            raise ValueError("SQL comments are not allowed in formulas")
        if any(re.search(rf'\b{keyword}\b', upper_formula) for keyword in self.DANGEROUS_SQL_KEYWORDS):
            raise ValueError("Only read-only SELECT statements are allowed")

    def _coerce_rows_processed(self, value: Any) -> int:
        """Only trust integer row counts from COUNT(*) responses."""
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(0, value)
        return 0

    def persist_calculation(
        self,
        kpi: KPI,
        period_start: date,
        period_end: date,
        calc_result: Dict[str, Any],
    ) -> bool:
        """
        Persist a successful calculate_kpi result and bump last_calculated_at.
        Used by batch jobs and POST .../calculate_now/.
        """
        if not calc_result.get('success'):
            return False
        period_label = self._format_period_label(period_start, period_end, kpi.frequency)
        previous_value = calc_result.get('previous_value')
        variance_absolute = calc_result.get('variance_absolute')
        target_variance = calc_result.get('target_variance')
        calculation, _ = KPICalculation.objects.update_or_create(
            kpi=kpi,
            period_start=period_start,
            period_end=period_end,
            defaults={
                'calculated_value': Decimal(str(calc_result['calculated_value'])),
                'previous_value': Decimal(str(previous_value)) if previous_value is not None else None,
                'variance_absolute': Decimal(str(variance_absolute)) if variance_absolute is not None else None,
                'variance_percent': calc_result.get('variance_percent'),
                'target_variance': Decimal(str(target_variance)) if target_variance is not None else None,
                'status': calc_result['status'],
                'breakdown': calc_result.get('breakdown', {}),
                'data_quality_score': calc_result.get('data_quality_score'),
                'rows_processed': calc_result.get('rows_processed'),
                'execution_time_ms': calc_result.get('execution_time_ms'),
                'calculation_method': 'automatic',
                'executed_by': self.user,
                'period_label': period_label,
            },
        )
        KPI.objects.filter(pk=kpi.pk).update(last_calculated_at=timezone.now())
        try:
            KPIAlertingService(self.user or kpi.owner).evaluate_alerts(calculation)
        except Exception as exc:
            logger.warning("Alert evaluation failed for KPI %s: %s", kpi.code, exc)
        return True
    
    def batch_calculate_kpis(self, kpis: List[KPI], period_start: date = None, 
                            period_end: date = None) -> Dict[str, bool]:
        """Calculate multiple KPIs and save results.
        If periods not specified, calculates for most recent period.
        """
        if period_end is None:
            period_end = date.today()
        if period_start is None:
            period_start = period_end - timedelta(days=30)

        results = {}
        for kpi in kpis:
            try:
                calc_result = self.calculate_kpi(kpi, period_start, period_end)

                if calc_result['success'] and self.persist_calculation(kpi, period_start, period_end, calc_result):
                    results[kpi.code] = True
                    logger.info(f"KPI {kpi.code} calculated successfully: {calc_result['calculated_value']}")
                else:
                    results[kpi.code] = False
                    logger.warning(f"KPI {kpi.code} calculation failed: {calc_result.get('error')}")
            except Exception as e:
                results[kpi.code] = False
                logger.error(f"Error processing KPI {kpi.code}: {str(e)}")

        return results

    def _format_period_label(self, period_start: date, period_end: date, frequency: str) -> str:
        """Generate human-readable period label (e.g., 'Q1 2026', 'January 2026')."""
        if frequency == 'daily':
            return period_end.strftime('%Y-%m-%d')
        elif frequency == 'weekly':
            return f"W{period_end.strftime('%W %Y')}"
        elif frequency == 'monthly':
            return period_end.strftime('%B %Y')
        elif frequency == 'quarterly':
            quarter = (period_end.month - 1) // 3 + 1
            return f"Q{quarter} {period_end.year}"
        elif frequency == 'yearly':
            return str(period_end.year)
        return f"{period_start.isoformat()} to {period_end.isoformat()}"


class FilterService:
    """Apply business-friendly filters and expose available filter values."""

    FIELD_ALIASES = {
        'date': ('date', 'created_at', 'cleaned_at', 'ingested_at', 'order_date', 'sale_date', 'transaction_date'),
        'region': ('region', 'regions', 'zone', 'territory', 'city', 'ville'),
        'produit': ('produit', 'product', 'sku', 'item', 'article', 'designation'),
        'categorie': ('categorie', 'category'),
        'vendeur': ('vendeur', 'salesperson', 'seller', 'commercial'),
        'client': ('client', 'customer', 'account', 'partner', 'client_name', 'customer_name'),
        'montant_total': ('montant_total', 'amount', 'revenue', 'ca', 'sales', 'montant', 'total_amount', 'net_amount'),
        'quantite': ('quantite', 'quantity', 'qty', 'volume', 'units', 'unites'),
    }

    def _find_column(self, frame: pd.DataFrame, field: str) -> str | None:
        if field in frame.columns:
            return field
        aliases = self.FIELD_ALIASES.get(field, ())
        for candidate in aliases:
            if candidate in frame.columns:
                return candidate
        lowered = {str(column).lower(): column for column in frame.columns}
        for candidate in aliases:
            if candidate.lower() in lowered:
                return lowered[candidate.lower()]
        return None

    def _normalize_filter_payload(self, filtres: Any) -> dict[str, Any]:
        if isinstance(filtres, dict):
            return filtres
        normalized: dict[str, Any] = {}
        for item in filtres or []:
            field = item.get('field') or item.get('column')
            if not field:
                continue
            operator = str(item.get('operator', 'eq')).lower()
            value = item.get('value')
            if operator in {'eq', '='}:
                normalized[field] = [value] if value not in (None, '') else []
            elif operator == 'in':
                normalized[field] = list(value or [])
            elif operator == 'between':
                normalized[f'{field}_min'] = (value or [None, None])[0]
                normalized[f'{field}_max'] = (value or [None, None])[1]
            elif operator in {'gte', 'gt'}:
                normalized[f'{field}_min'] = value
            elif operator in {'lte', 'lt'}:
                normalized[f'{field}_max'] = value
        return normalized

    def apply(self, frame: pd.DataFrame, filtres: Any) -> pd.DataFrame:
        if frame.empty:
            return frame

        filters = self._normalize_filter_payload(filtres)
        filtered = frame.copy()

        date_column = self._find_column(filtered, 'date')
        if date_column and (filters.get('date_debut') or filters.get('date_fin')):
            dates = pd.to_datetime(filtered[date_column], errors='coerce')
            if filters.get('date_debut'):
                filtered = filtered[dates >= pd.to_datetime(filters['date_debut'])]
                dates = pd.to_datetime(filtered[date_column], errors='coerce')
            if filters.get('date_fin'):
                filtered = filtered[dates <= pd.to_datetime(filters['date_fin'])]

        for field in ('region', 'produit', 'categorie', 'vendeur', 'client'):
            column = self._find_column(filtered, field)
            selected = filters.get(field)
            if column and selected:
                values = [str(value) for value in selected if value not in (None, '')]
                if values:
                    filtered = filtered[filtered[column].astype(str).isin(values)]

            excluded = (filters.get('exclure') or {}).get(field)
            if column and excluded:
                values = [str(value) for value in excluded if value not in (None, '')]
                if values:
                    filtered = filtered[~filtered[column].astype(str).isin(values)]

        for field in ('montant_total', 'quantite'):
            column = self._find_column(filtered, field)
            if not column:
                continue
            numeric_series = pd.to_numeric(filtered[column], errors='coerce')
            minimum = filters.get(f'{field}_min')
            maximum = filters.get(f'{field}_max')
            if minimum is not None and minimum != '':
                minimum_value = pd.to_numeric(pd.Series([minimum]), errors='coerce').iloc[0]
                if pd.notna(minimum_value):
                    filtered = filtered[numeric_series >= minimum_value]
                    numeric_series = pd.to_numeric(filtered[column], errors='coerce')
            if maximum is not None and maximum != '':
                maximum_value = pd.to_numeric(pd.Series([maximum]), errors='coerce').iloc[0]
                if pd.notna(maximum_value):
                    filtered = filtered[numeric_series <= maximum_value]

        return filtered

    def available_values(self, frame: pd.DataFrame) -> dict[str, Any]:
        if frame.empty:
            return {
                'regions': [],
                'produits': [],
                'categories': [],
                'vendeurs': [],
                'date_min': None,
                'date_max': None,
                'montant_min': 0,
                'montant_max': 0,
            }

        def _unique_values(field: str) -> list[str]:
            column = self._find_column(frame, field)
            if not column:
                return []
            values = [str(value).strip() for value in frame[column].dropna().tolist() if str(value).strip()]
            return sorted(dict.fromkeys(values))

        def _numeric_bounds(field: str) -> tuple[float | int | None, float | int | None]:
            column = self._find_column(frame, field)
            if not column:
                return (None, None)
            numeric = pd.to_numeric(frame[column], errors='coerce').dropna()
            if numeric.empty:
                return (None, None)
            minimum = float(numeric.min())
            maximum = float(numeric.max())
            return (int(minimum) if minimum.is_integer() else minimum, int(maximum) if maximum.is_integer() else maximum)

        date_column = self._find_column(frame, 'date')
        if date_column:
            dates = pd.to_datetime(frame[date_column], errors='coerce').dropna()
            date_min = dates.min().date().isoformat() if not dates.empty else None
            date_max = dates.max().date().isoformat() if not dates.empty else None
        else:
            date_min = None
            date_max = None

        montant_min, montant_max = _numeric_bounds('montant_total')
        return {
            'regions': _unique_values('region'),
            'produits': _unique_values('produit'),
            'categories': _unique_values('categorie'),
            'vendeurs': _unique_values('vendeur'),
            'date_min': date_min,
            'date_max': date_max,
            'montant_min': montant_min or 0,
            'montant_max': montant_max or 0,
        }


class PivotService:
    """Build configurable pivot tables with time dimensions, top-N and variation metadata."""

    TIME_DIMENSIONS = {'mois', 'trimestre', 'semestre', 'annee', 'semaine'}

    def __init__(self, user: Optional[User] = None):
        self.user = user
        self.filter_service = FilterService()
        self.calculation_service = KPICalculationService(user)

    def _load_frame(self, config: dict[str, Any], df: pd.DataFrame | None = None) -> pd.DataFrame:
        if df is not None:
            frame = df.copy()
        else:
            source_table = config.get('source_table', 'nettoyage_cleaneddata')
            source_id = config.get('source_id')
            period_start = config.get('period_start')
            period_end = config.get('period_end')

            if source_id and source_table == 'ingestion_rawdata':
                source = DataSource.objects.filter(pk=source_id).first()
                # Check if source has sheet relations → use joined view
                if source and source.sheet_relations.filter(is_active=True).exists():
                    from apps.ingestion.services import build_joined_view
                    result = build_joined_view(source)
                    frame = pd.DataFrame(result.get('rows', []))
                else:
                    rows = RawData.objects.filter(source_id=source_id).values()
                    frame = pd.DataFrame(
                        [self.calculation_service._normalize_tabular_row(row) for row in rows]
                    )
            elif source_id and source_table == 'nettoyage_cleaneddata':
                source = DataSource.objects.filter(pk=source_id).first()
                if source is None:
                    frame = pd.DataFrame()
                else:
                    try:
                        frame, _ = KPIAutoService()._load_validated_frame(source)
                    except ValueError:
                        frame = pd.DataFrame()
            else:
                rows = self.calculation_service._get_table_data(source_table, period_start, period_end)
                frame = pd.DataFrame(rows)

            if source_id and not frame.empty and 'source_id' in frame.columns:
                frame = frame[frame['source_id'].astype(str) == str(source_id)]
        if frame.empty:
            return frame
        return frame.where(pd.notnull(frame), None)

    def _extract_time_dimensions(self, frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        if frame.empty:
            return frame
        requested = [field for field in (config.get('rows') or []) + (config.get('columns') or []) if field in self.TIME_DIMENSIONS]
        if not requested:
            return frame
        date_column = self.filter_service._find_column(frame, 'date')
        if not date_column:
            return frame
        dates = pd.to_datetime(frame[date_column], errors='coerce')
        if 'mois' in requested:
            frame['mois'] = dates.dt.to_period('M').astype(str)
        if 'trimestre' in requested:
            frame['trimestre'] = dates.dt.to_period('Q').astype(str)
        if 'semestre' in requested:
            semester = ((dates.dt.month.fillna(1).astype(int) - 1) // 6) + 1
            frame['semestre'] = dates.dt.year.astype('Int64').astype(str) + '-S' + semester.astype('Int64').astype(str)
        if 'annee' in requested:
            frame['annee'] = dates.dt.year.astype('Int64').astype(str)
        if 'semaine' in requested:
            frame['semaine'] = dates.dt.isocalendar().week.astype('Int64').astype(str)
        return frame

    def _apply_top_n(self, pivot: pd.DataFrame, n: int | None) -> pd.DataFrame:
        if not n or pivot.empty:
            return pivot
        if 'TOTAL' in pivot.columns:
            working = pivot.drop(index='TOTAL') if 'TOTAL' in pivot.index else pivot.copy()
            top_index = pd.to_numeric(working['TOTAL'], errors='coerce').nlargest(int(n)).index
            mask = pivot.index.isin(list(top_index) + (['TOTAL'] if 'TOTAL' in pivot.index else []))
            return pivot[mask]
        numeric_totals = pivot.select_dtypes(include='number').sum(axis=1)
        top_index = numeric_totals.nlargest(int(n)).index
        return pivot.loc[top_index]

    def _validate_columns(self, frame: pd.DataFrame, config: dict[str, Any]) -> None:
        required = [config.get('valeur') or config.get('metric') or config.get('mesure')]
        required.extend(config.get('rows') or [])
        required.extend(config.get('columns') or [])
        for field in filter(None, required):
            if field in self.TIME_DIMENSIONS:
                continue
            if field not in frame.columns:
                raise ValueError(f"Column '{field}' not found in source data")

    def _compute_variations(self, frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        value_field = config.get('valeur') or config.get('metric') or config.get('mesure')
        if not value_field or value_field not in frame.columns:
            return {}
        time_dimension = next((field for field in (config.get('rows') or []) + (config.get('columns') or []) if field in self.TIME_DIMENSIONS), None)
        if not time_dimension or time_dimension not in frame.columns:
            return {}
        grouped = frame.groupby(time_dimension, dropna=False)[value_field].sum().reset_index()
        grouped[time_dimension] = grouped[time_dimension].astype(str)
        grouped = grouped.sort_values(time_dimension)
        variations: dict[str, Any] = {}
        previous_value = None
        for _, row in grouped.iterrows():
            current_value = float(pd.to_numeric(pd.Series([row[value_field]]), errors='coerce').iloc[0] or 0)
            period = str(row[time_dimension])
            if previous_value is None:
                variations[period] = {'value': current_value, 'variation_pct': None, 'tendance': 'stable'}
            else:
                variation_pct = ((current_value - previous_value) / previous_value * 100) if previous_value else None
                variations[period] = {
                    'value': current_value,
                    'variation_pct': round(float(variation_pct), 2) if variation_pct is not None else None,
                    'tendance': 'up' if previous_value is not None and current_value > previous_value else 'down' if previous_value is not None and current_value < previous_value else 'stable',
                }
            previous_value = current_value
        return variations

    def _format_fcfa(self, pivot: pd.DataFrame, aggfunc: Any) -> pd.DataFrame:
        if pivot.empty:
            return pivot

        def _format_cell(value: Any) -> Any:
            if value in (None, ''):
                return value
            numeric = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
            if pd.isna(numeric):
                return value
            aggregation = str(aggfunc).lower() if not isinstance(aggfunc, dict) else 'sum'
            if aggregation == 'count':
                return f"{int(numeric):,}".replace(',', ' ') + ' commandes'
            if aggregation == 'std':
                return f"±{float(numeric):,.0f}".replace(',', ' ') + ' FCFA'
            if aggregation in {'avg', 'mean', 'median'}:
                return f"{float(numeric):,.0f}".replace(',', ' ') + ' FCFA (moy.)'
            return f"{float(numeric):,.0f}".replace(',', ' ') + ' FCFA'

        formatted = pivot.copy()
        for column in formatted.columns:
            formatted[column] = formatted[column].apply(_format_cell)
        return formatted

    def build(self, config: dict[str, Any], df: pd.DataFrame | None = None) -> dict[str, Any]:
        frame = self._load_frame(config, df)
        frame = self._extract_time_dimensions(frame, config)
        frame = self.filter_service.apply(frame, config.get('filtres') or config.get('filters') or {})
        self._validate_columns(frame, config)

        rows = [field for field in (config.get('lignes') or config.get('rows') or []) if field in frame.columns]
        columns = [field for field in (config.get('colonnes') or config.get('columns') or []) if field in frame.columns]
        value_field = config.get('valeur') or config.get('metric') or config.get('mesure')
        aggfunc = config.get('aggfunc', config.get('aggregation', 'sum'))
        include_totals = bool(config.get('totaux', config.get('include_totals', True)))
        top_n = config.get('top_n')
        fill_nulls = config.get('fill_nulls', 0)
        dropna = bool(config.get('dropna', False))

        if frame.empty:
            return {
                'data': [],
                'formatted_data': [],
                'colonnes': [],
                'lignes': [],
                'valeur': value_field,
                'aggfunc': aggfunc,
                'total_general': None,
                'variations': {},
                'nb_lignes': 0,
                'nb_colonnes': 0,
                'rows_processed': 0,
            }

        values = value_field if value_field in frame.columns else None
        pivot = pd.pivot_table(
            frame,
            values=values,
            index=rows or None,
            columns=columns or None,
            aggfunc=aggfunc,
            fill_value=fill_nulls,
            margins=include_totals,
            margins_name='TOTAL',
            dropna=dropna,
        )

        if isinstance(pivot, pd.Series):
            pivot = pivot.to_frame(name=value_field or 'value')

        if top_n:
            pivot = self._apply_top_n(pivot, int(top_n))

        formatted_pivot = self._format_fcfa(pivot, aggfunc)
        raw_table = pivot.reset_index()
        formatted_table = formatted_pivot.reset_index()
        raw_table.columns = [
            ' | '.join(str(part) for part in column if str(part) != 'nan').strip(' |')
            if isinstance(column, tuple)
            else str(column)
            for column in raw_table.columns
        ]
        formatted_table.columns = raw_table.columns
        raw_table = raw_table.where(pd.notnull(raw_table), None)
        formatted_table = formatted_table.where(pd.notnull(formatted_table), None)

        total_general = None
        if include_totals and 'TOTAL' in pivot.index and 'TOTAL' in pivot.columns:
            total_general = float(pd.to_numeric(pd.Series([pivot.loc['TOTAL', 'TOTAL']]), errors='coerce').iloc[0] or 0)

        return {
            'data': raw_table.to_dict(orient='records'),
            'formatted_data': formatted_table.to_dict(orient='records'),
            'colonnes': [str(column) for column in pivot.columns],
            'lignes': [str(index) for index in pivot.index],
            'valeur': value_field,
            'aggfunc': aggfunc,
            'total_general': total_general,
            'variations': self._compute_variations(frame, config),
            'nb_lignes': len(pivot) - (1 if include_totals and 'TOTAL' in pivot.index else 0),
            'nb_colonnes': len(pivot.columns) - (1 if include_totals and 'TOTAL' in pivot.columns else 0),
            'rows_processed': int(frame.shape[0]),
        }


class AdvancedPivotService(PivotService):
    """Advanced pivot table service with drill-down, hierarchies, and Excel export."""

    def build_pivot_with_hierarchy(self, config: dict[str, Any]) -> dict[str, Any]:
        frame = self._load_frame(config)
        frame = self._extract_time_dimensions(frame, config)
        frame = self.filter_service.apply(frame, config.get('filters', {}))

        row_fields = config.get('row_fields', [])
        col_fields = config.get('column_fields', [])
        value_field = config.get('value_field')
        aggregation = config.get('aggregation', 'sum')
        include_totals = config.get('include_totals', True)
        include_running_totals = config.get('include_running_totals', False)
        format_currency = config.get('format_currency', False)
        sort_by = config.get('sort_by', 'value')
        sort_direction = config.get('sort_direction', 'desc')
        top_n = config.get('top_n')

        if frame.empty:
            return {
                'pivot': [],
                'row_headers': [],
                'col_headers': [],
                'row_labels': [],
                'col_labels': [],
                'totals': {'row_totals': [], 'col_totals': [], 'grand_total': 0},
                'metadata': {'rows_processed': 0, 'execution_time_ms': 0, 'data_quality_score': 100},
                'drill_down_available': {},
            }

        start_time = pd.Timestamp.now()

        valid_rows = [f for f in row_fields if f in frame.columns]
        valid_cols = [f for f in col_fields if f in frame.columns]

        for col in list(valid_rows) + list(valid_cols):
            if col not in frame.columns:
                continue
            try:
                parsed = pd.to_datetime(frame[col], errors='coerce')
                if parsed.notna().sum() > len(frame) * 0.5:
                    frame[col + '_mois'] = parsed.dt.to_period('M').astype(str)
                    idx = valid_rows.index(col) if col in valid_rows else -1
                    if idx >= 0:
                        valid_rows[idx] = col + '_mois'
                    idx = valid_cols.index(col) if col in valid_cols else -1
                    if idx >= 0:
                        valid_cols[idx] = col + '_mois'
            except Exception:
                pass

        if valid_rows or valid_cols or value_field:
            pivot = pd.pivot_table(
                frame,
                values=value_field if value_field in frame.columns else None,
                index=valid_rows or None,
                columns=valid_cols or None,
                aggfunc=aggregation,
                fill_value=0,
                margins=include_totals,
                margins_name='TOTAL',
                dropna=False,
            )
        else:
            pivot = pd.DataFrame()

        if isinstance(pivot, pd.Series):
            pivot = pivot.to_frame(name=value_field or 'value')

        if top_n:
            pivot = self._apply_top_n(pivot, int(top_n))

        if sort_by == 'value' and 'TOTAL' in pivot.columns:
            if sort_direction == 'desc':
                pivot = pivot.sort_values('TOTAL', ascending=False)
            else:
                pivot = pivot.sort_values('TOTAL', ascending=True)

        row_labels = [str(idx) for idx in pivot.index]
        col_labels = [str(col) for col in pivot.columns]

        def _safe_float(val):
            """Safely convert a pivot cell to float, handling Series from duplicate columns."""
            if isinstance(val, pd.Series):
                val = val.iloc[0] if len(val) > 0 else 0
            return float(val) if pd.notna(val) else 0

        row_totals = [_safe_float(pivot.loc[idx, 'TOTAL']) if 'TOTAL' in pivot.columns else 0 for idx in pivot.index]
        col_totals = [_safe_float(pivot.loc['TOTAL', col]) if 'TOTAL' in pivot.index else 0 for col in pivot.columns]
        grand_total = _safe_float(pivot.loc['TOTAL', 'TOTAL']) if ('TOTAL' in pivot.index and 'TOTAL' in pivot.columns) else 0

        pivot_data = [[_safe_float(pivot.iloc[i, j]) for j in range(len(pivot.columns))] for i in range(len(pivot.index))]

        if format_currency:
            formatted_data = [[f"{val:,.0f}".replace(',', ' ') + ' FCFA' if val != 0 else '0 FCFA' for val in row] for row in pivot_data]
        else:
            formatted_data = pivot_data

        drill_down_available = {
            f"row_{i}_col_{j}": True
            for i in range(len(pivot.index))
            for j in range(len(pivot.columns))
            if i < len(pivot.index) - 1 or j < len(pivot.columns) - 1
        }

        execution_time = (pd.Timestamp.now() - start_time).total_seconds() * 1000

        return {
            'pivot': pivot_data,
            'formatted_pivot': formatted_data,
            'row_headers': row_labels,
            'col_headers': col_labels,
            'row_labels': [f for f in valid_rows] if valid_rows else [],
            'col_labels': [f for f in valid_cols] if valid_cols else [],
            'totals': {
                'row_totals': row_totals,
                'col_totals': col_totals,
                'grand_total': grand_total,
            },
            'metadata': {
                'rows_processed': int(frame.shape[0]),
                'execution_time_ms': int(execution_time),
                'data_quality_score': 98.5,
            },
            'drill_down_available': drill_down_available,
        }

    def compute_drill_down(self, config: dict[str, Any], row_key: str, col_key: str) -> list[dict]:
        frame = self._load_frame(config)
        frame = self._extract_time_dimensions(frame, config)
        frame = self.filter_service.apply(frame, config.get('filters', {}))

        row_fields = config.get('row_fields', [])
        col_fields = config.get('column_fields', [])

        for idx, field in enumerate(row_fields):
            if field in frame.columns:
                row_values = row_key.split(' | ') if row_key else []
                if idx < len(row_values):
                    frame = frame[frame[field].astype(str) == row_values[idx]]

        for idx, field in enumerate(col_fields):
            if field in frame.columns:
                col_values = col_key.split(' | ') if col_key else []
                if idx < len(col_values):
                    frame = frame[frame[field].astype(str) == col_values[idx]]

        return frame.head(100).to_dict(orient='records')

    def export_to_excel(self, pivot_data: dict) -> bytes:
        import io
        import pandas as pd
        from openpyxl.styles import Font, PatternFill, Alignment

        pivot = pivot_data.get('pivot', [])
        row_headers = pivot_data.get('row_headers', [])
        col_headers = pivot_data.get('col_headers', [])

        df = pd.DataFrame(pivot, columns=col_headers if col_headers else None, index=row_headers if row_headers else None)
        df.index.name = 'Total' if len(row_headers) <= 1 else None

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as output:
            df.to_excel(output, sheet_name='Données', index=True)

            workbook = output.book
            worksheet = workbook['Données']

            header_fill = PatternFill(start_color='1a3a5c', end_color='1a3a5c', fill_type='solid')
            header_font = Font(bold=True, color='FFFFFF')

            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center')

            for cell in worksheet['A']:
                cell.font = Font(bold=True)

            worksheet.auto_filter.ref = worksheet.dimensions

        buffer.seek(0)
        return buffer.getvalue()


class M4WorkbenchService:
    AGGREGATION_MAP = {
        'sum': 'sum',
        'avg': 'mean',
        'mean': 'mean',
        'count': 'count',
        'min': 'min',
        'max': 'max',
        'median': 'median',
        'std': 'std',
        'first': 'first',
        'last': 'last',
    }

    SUPPORTED_TABLES = {'ingestion_rawdata', 'nettoyage_cleaneddata'}

    def __init__(self, user: Optional[User] = None):
        self.user = user
        self.calculation_service = KPICalculationService(user)
        self.filter_service = FilterService()
        self.pivot_service = PivotService(user)

    def _load_frame(
        self,
        source_table: str,
        source_id: Any = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> pd.DataFrame:
        if source_table not in self.SUPPORTED_TABLES:
            raise ValueError('Unsupported source table for the configurable engine')

        if source_id and source_table == 'ingestion_rawdata':
            source = DataSource.objects.filter(pk=source_id).first()
            # Check if source has sheet relations → use joined view
            if source and source.sheet_relations.filter(is_active=True).exists():
                from apps.ingestion.services import build_joined_view
                result = build_joined_view(source)
                frame = pd.DataFrame(result.get('rows', []))
            else:
                rows = RawData.objects.filter(source_id=source_id).values()
                frame = pd.DataFrame(
                    [self.calculation_service._normalize_tabular_row(row) for row in rows]
                )
        elif source_id and source_table == 'nettoyage_cleaneddata':
            source = DataSource.objects.filter(pk=source_id).first()
            if source is None:
                frame = pd.DataFrame()
            else:
                frame, _ = KPIAutoService()._load_validated_frame(source)
        else:
            end_date = period_end or date.today()
            start_date = period_start or (end_date - timedelta(days=30))
            rows = self.calculation_service._get_table_data(source_table, start_date, end_date)
            frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        prepared = KPIAutoService()._prepare_frame(frame)
        return prepared.where(pd.notnull(prepared), None)

    def _apply_filters(self, frame: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
        if frame.empty or not filters:
            return frame

        filtered = frame.copy()
        for condition in filters:
            field = condition.get('field') or condition.get('column')
            if not field:
                continue
            resolved = self.filter_service._find_column(filtered, field)
            if not resolved:
                continue
            field = resolved

            series = filtered[field]
            operator = str(condition.get('operator', 'eq')).lower()
            value = condition.get('value')

            if operator in {'eq', '='}:
                filtered = filtered[series.astype(str).str.lower() == str(value).lower()]
            elif operator in {'neq', '!='}:
                filtered = filtered[series.astype(str).str.lower() != str(value).lower()]
            elif operator == 'in':
                values = value if isinstance(value, (list, tuple, set)) else [value]
                lookup = {str(item).lower() for item in values}
                filtered = filtered[series.astype(str).str.lower().isin(lookup)]
            elif operator == 'not_in':
                values = value if isinstance(value, (list, tuple, set)) else [value]
                lookup = {str(item).lower() for item in values}
                filtered = filtered[~series.astype(str).str.lower().isin(lookup)]
            elif operator == 'contains':
                filtered = filtered[series.astype(str).str.contains(str(value), case=False, na=False)]
            elif operator in {'gt', 'gte', 'lt', 'lte'}:
                numeric_series = pd.to_numeric(series, errors='coerce')
                numeric_value = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
                if pd.isna(numeric_value):
                    continue
                if operator == 'gt':
                    filtered = filtered[numeric_series > numeric_value]
                elif operator == 'gte':
                    filtered = filtered[numeric_series >= numeric_value]
                elif operator == 'lt':
                    filtered = filtered[numeric_series < numeric_value]
                elif operator == 'lte':
                    filtered = filtered[numeric_series <= numeric_value]
            elif operator == 'between' and isinstance(value, (list, tuple)) and len(value) == 2:
                numeric_series = pd.to_numeric(series, errors='coerce')
                low = pd.to_numeric(pd.Series([value[0]]), errors='coerce').iloc[0]
                high = pd.to_numeric(pd.Series([value[1]]), errors='coerce').iloc[0]
                if pd.notna(low) and pd.notna(high):
                    filtered = filtered[(numeric_series >= low) & (numeric_series <= high)]

        return filtered

    def _format_frame(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        if frame.empty:
            return []
        clean = frame.where(pd.notnull(frame), None)
        return clean.to_dict(orient='records')

    def _format_aggregation(self, aggregation: str) -> str:
        return self.AGGREGATION_MAP.get(str(aggregation).lower(), 'sum')

    def calculate_metric(self, config: dict[str, Any]) -> dict[str, Any]:
        frame = self._load_frame(
            config.get('source_table', 'nettoyage_cleaneddata'),
            config.get('source_id'),
            config.get('period_start'),
            config.get('period_end'),
        )
        frame = self._apply_filters(frame, config.get('filters') or [])

        measure = str(config.get('mesure') or config.get('measure') or '').strip()
        aggregation = str(config.get('aggregation', 'sum')).lower()

        col_map = {c.lower(): c for c in frame.columns}
        raw_group = [field for field in (config.get('group_by') or []) if field]
        group_by = [col_map[field.lower()] for field in raw_group if field.lower() in col_map]
        if measure and measure.lower() in col_map and measure not in frame.columns:
            measure = col_map[measure.lower()]

        if frame.empty:
            return {
                'nom_kpi': config.get('nom_kpi') or measure,
                'aggregation': aggregation,
                'measure': measure,
                'group_by': group_by,
                'value': 0,
                'formatted_value': '0',
                'rows_processed': 0,
                'breakdown': [],
                'chart_type': 'metric_card',
                'data_quality_score': 0,
            }

        if measure and measure not in frame.columns and aggregation != 'count':
            raise ValueError(f"Measure column '{measure}' not found in source data")

        scalar_value = self._aggregate_series(frame[measure] if measure in frame.columns else frame.iloc[:, 0], aggregation)
        breakdown: list[dict[str, Any]] = []

        if group_by:
            grouped = frame.groupby(group_by, dropna=False)
            if aggregation == 'count':
                grouped_frame = grouped.size().reset_index(name='value')
            else:
                grouped_frame = grouped[measure].agg(self._format_aggregation(aggregation)).reset_index(name='value')
            breakdown = self._format_frame(grouped_frame)

        return {
            'nom_kpi': config.get('nom_kpi') or measure,
            'aggregation': aggregation,
            'measure': measure,
            'group_by': group_by,
            'value': scalar_value,
            'formatted_value': self._format_value(scalar_value),
            'rows_processed': int(frame.shape[0]),
            'breakdown': breakdown,
            'chart_type': 'bar_chart' if group_by else 'metric_card',
            'data_quality_score': round((frame[measure].notna().mean() * 100) if measure in frame.columns else 100, 2),
        }

    def build_pivot_table(self, config: dict[str, Any]) -> dict[str, Any]:
        return self.pivot_service.build(config)

    def build_dashboard(self, config: dict[str, Any]) -> dict[str, Any]:
        widgets = []
        for widget in config.get('widgets') or []:
            widget_type = str(widget.get('type', 'kpi_card'))
            visible = bool(widget.get('visible', True))
            payload: dict[str, Any]

            if not visible:
                payload = {'message': 'Widget masqué'}
            elif widget_type in {'kpi_card'}:
                payload = self.calculate_metric(widget)
            elif widget_type in {'table', 'pivot_table'}:
                payload = self.build_pivot_table(widget)
            else:
                payload = self.calculate_metric(widget)
                if payload.get('breakdown'):
                    payload['series'] = payload['breakdown']

            widgets.append(
                {
                    'id': widget.get('id') or widget.get('title') or widget_type,
                    'title': widget.get('title') or widget.get('nom_kpi') or widget.get('mesure') or widget_type,
                    'type': widget_type,
                    'visible': visible,
                    'payload': payload,
                }
            )

        return {
            'title': config.get('title') or 'Dashboard dynamique',
            'widgets': widgets,
            'filters': config.get('filters') or [],
            'period_start': config.get('period_start'),
            'period_end': config.get('period_end'),
        }

    def _aggregate_series(self, series: pd.Series, aggregation: str) -> float:
        numeric = pd.to_numeric(series, errors='coerce')
        aggregation = str(aggregation).lower()
        if aggregation == 'count':
            return float(series.notna().sum())
        if aggregation in {'avg', 'mean'}:
            return float(numeric.mean() or 0)
        if aggregation == 'median':
            return float(numeric.median() or 0)
        if aggregation == 'std':
            return float(numeric.std(ddof=0) or 0)
        if aggregation == 'min':
            return float(numeric.min() or 0)
        if aggregation == 'max':
            return float(numeric.max() or 0)
        if aggregation == 'first':
            non_null = series.dropna()
            first_value = non_null.iloc[0] if not non_null.empty else 0
            return float(pd.to_numeric(pd.Series([first_value]), errors='coerce').iloc[0] or 0)
        if aggregation == 'last':
            non_null = series.dropna()
            last_value = non_null.iloc[-1] if not non_null.empty else 0
            return float(pd.to_numeric(pd.Series([last_value]), errors='coerce').iloc[0] or 0)
        return float(numeric.sum() or 0)

    def _format_value(self, value: float) -> str:
        return f"{value:,.2f}".replace(',', ' ')

    def _build_chart_payload(self, pivot: pd.DataFrame, *, rows: list[str], metric: str) -> list[dict[str, Any]]:
        if pivot.empty or not rows:
            return []
        x_field = rows[0]
        if x_field not in pivot.columns:
            return []
        value_columns = [column for column in pivot.columns if column != x_field]
        series_field = value_columns[0] if value_columns else None
        if not series_field:
            return []
        return [
            {
                'label': str(item.get(x_field)),
                'value': float(pd.to_numeric(pd.Series([item.get(series_field)]), errors='coerce').iloc[0] or 0),
                'metric': metric,
            }
            for item in pivot.to_dict(orient='records')
            if item.get(x_field) not in (None, '')
        ]


class KPIAnomalyDetectionService:
    """
    Detects anomalies in KPI calculations using statistical methods.
    Identifies unusual values that deviate from expected patterns.
    """
    
    def __init__(self, user: Optional[User] = None):
        self.user = user
    
    def detect_anomalies(self, kpi: KPI, lookback_periods: int = 12) -> Dict[str, Any]:
        """
        Detect anomalies in KPI history using statistical methods.
        
        Returns:
        - has_anomaly: Boolean indicating if latest calculation is anomalous
        - z_score: How many standard deviations from the mean
        - method: 'z_score', 'iqr', or 'isolation_forest'
        - explanation: Human readable description
        - recommendation: Suggested action
        """
        try:
            # Get historical calculations
            calcs = KPICalculation.objects.filter(kpi=kpi).order_by('-period_end')[:lookback_periods]
            
            if len(calcs) < 3:
                return self._build_anomaly_result(
                    has_anomaly=False,
                    method='insufficient_data',
                    explanation='Not enough history to evaluate anomalies reliably',
                    recommendation='Collect at least 3 calculation periods before anomaly detection',
                    reason='Insufficient historical data'
                )
            
            values = [float(c.calculated_value) for c in reversed(calcs)]
            latest_value = values[-1]
            baseline_values = values[:-1]
            
            # Compare the latest point against previous history so one outlier does not dilute itself.
            mean = np.mean(baseline_values)
            std = np.std(baseline_values)
            
            if std == 0:
                has_anomaly = latest_value != mean
                return self._build_anomaly_result(
                    has_anomaly=has_anomaly,
                    z_score=999.0 if has_anomaly else 0.0,
                    mean=mean,
                    std_dev=std,
                    latest_value=latest_value,
                    method='z_score',
                    explanation='Latest value deviates from a perfectly stable baseline' if has_anomaly else 'Historical values are perfectly stable',
                    recommendation='Review the latest input data and recent business changes' if has_anomaly else 'No action needed',
                    reason='Zero variance in baseline history'
                )
            
            z_score = abs((latest_value - mean) / std)
            is_anomaly = z_score > 2.5  # More than 2.5 std deviations
            
            return self._build_anomaly_result(
                has_anomaly=is_anomaly,
                z_score=z_score,
                mean=mean,
                std_dev=std,
                latest_value=latest_value,
                method='z_score',
                explanation=f"Latest value is {z_score:.2f} standard deviations from the baseline mean" if is_anomaly else "Latest value is within the expected range",
                recommendation="Review recent data quality or business changes" if is_anomaly else "No action needed"
            )
        except Exception as e:
            logger.error(f"Error detecting anomalies for KPI {kpi.code}: {str(e)}")
            return self._build_anomaly_result(
                has_anomaly=False,
                method='error',
                explanation='Anomaly detection could not be completed',
                recommendation='Review the KPI configuration and try again',
                reason=str(e)
            )

    def _build_anomaly_result(
        self,
        *,
        has_anomaly: bool,
        method: str,
        explanation: str,
        recommendation: str,
        z_score: Optional[float] = None,
        mean: Optional[float] = None,
        std_dev: Optional[float] = None,
        latest_value: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build a serializer-compatible anomaly response."""
        result = {
            'has_anomaly': has_anomaly,
            'method': method,
            'explanation': explanation,
            'recommendation': recommendation,
        }

        if z_score is not None:
            result['z_score'] = round(float(z_score), 2)
        if mean is not None:
            result['mean'] = round(float(mean), 2)
        if std_dev is not None:
            result['std_dev'] = round(float(std_dev), 2)
        if latest_value is not None:
            result['latest_value'] = float(latest_value)
        if reason:
            result['reason'] = reason

        return result


class KPIForecastingService:
    """
    Forecasts future KPI values using trend analysis and seasonal decomposition.
    Provides confidence intervals for projections.
    """
    
    def __init__(self, user: User):
        self.user = user
    
    def forecast_kpi(self, kpi: KPI, forecast_periods: int = 3) -> Dict[str, Any]:
        """
        Forecast next N periods of KPI values.
        
        Returns:
        - forecast_values: List of projected values
        - confidence_intervals: Upper and lower bounds
        - trend: 'increasing', 'decreasing', or 'stable'
        - confidence: Confidence level (0-100)
        """
        try:
            # Get historical calculations (at least 6 periods)
            calcs = KPICalculation.objects.filter(kpi=kpi).order_by('period_end')[:12]
            
            if len(calcs) < 3:
                return {
                    'success': False,
                    'error': 'Insufficient historical data (minimum 3 periods)'
                }
            
            values = np.array([float(c.calculated_value) for c in calcs])
            
            # Simple linear regression for trend
            x = np.arange(len(values))
            coefficients = np.polyfit(x, values, 1)
            trend_line = np.poly1d(coefficients)
            
            # Forecast next periods
            future_x = np.arange(len(values), len(values) + forecast_periods)
            forecast = trend_line(future_x)
            
            # Calculate residuals and confidence interval
            residuals = values - trend_line(x)
            residual_std = np.std(residuals)
            
            # Determine trend direction
            if coefficients[0] > 0.01:
                trend_direction = 'increasing'
            elif coefficients[0] < -0.01:
                trend_direction = 'decreasing'
            else:
                trend_direction = 'stable'
            
            # Calculate confidence based on fit quality
            r_squared = 1 - (np.sum(residuals**2) / np.sum((values - np.mean(values))**2))
            confidence = max(0, min(100, r_squared * 100))
            
            return {
                'success': True,
                'forecast_values': [round(float(v), 2) for v in forecast],
                'confidence_intervals': [
                    [round(float(forecast[i] - 1.96 * residual_std), 2),
                     round(float(forecast[i] + 1.96 * residual_std), 2)]
                    for i in range(len(forecast))
                ],
                'trend': trend_direction,
                'trend_slope': round(float(coefficients[0]), 4),
                'confidence': round(confidence, 2),
                'r_squared': round(r_squared, 3)
            }
        except Exception as e:
            logger.error(f"Error forecasting KPI {kpi.code}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class KPIAlertingService:
    """
    Manages KPI alert triggering, notifications, and escalation workflows.
    Integrates with notification system for multi-channel delivery.
    """
    
    def __init__(self, user: User):
        self.user = user
    
    def evaluate_alerts(self, calculation: KPICalculation) -> Dict[str, Any]:
        """
        Evaluate all active alerts for a KPI calculation.
        Trigger alerts if conditions are met.
        
        Returns:
        - triggered_alerts: List of alert IDs that were triggered
        - notifications_sent: Count of notifications sent
        """
        triggered_alerts = []
        notifications_sent = 0
        
        try:
            alerts = KPIAlert.objects.filter(kpi=calculation.kpi, is_active=True)
            
            for alert in alerts:
                # Check if alert should be triggered
                should_trigger = self._check_alert_condition(alert, calculation)
                
                # Check cooldown
                if should_trigger and alert.mute_until and alert.mute_until > timezone.now():
                    should_trigger = False
                
                if should_trigger:
                    # Check cooldown period since last trigger
                    if alert.last_triggered_at:
                        elapsed = (timezone.now() - alert.last_triggered_at).total_seconds() / 60
                        if elapsed < alert.cooldown_minutes:
                            should_trigger = False
                
                if should_trigger:
                    # Trigger alert
                    alert.is_triggered = True
                    alert.trigger_count += 1
                    alert.last_triggered_at = timezone.now()
                    alert.last_value = calculation.calculated_value
                    alert.save()
                    
                    # Send notifications
                    notifications_sent += self._send_alert_notifications(alert, calculation)
                    triggered_alerts.append(alert.id)
                    
                    logger.info(f"Alert triggered: {alert.alert_name} (KPI: {calculation.kpi.code})")
        
        except Exception as e:
            logger.error(f"Error evaluating alerts for KPI calculation: {str(e)}")
        
        return {
            'triggered_alerts': triggered_alerts,
            'notifications_sent': notifications_sent,
            'success': True
        }
    
    def _check_alert_condition(self, alert: KPIAlert, calculation: KPICalculation) -> bool:
        """Check if alert condition is met."""
        value = calculation.calculated_value
        threshold = alert.threshold_value
        
        if alert.condition_type == 'above':
            return value > threshold if threshold else False
        elif alert.condition_type == 'below':
            return value < threshold if threshold else False
        elif alert.condition_type == 'equals':
            return value == threshold if threshold else False
        elif alert.condition_type == 'changed_by':
            if not calculation.previous_value or not alert.threshold_percent:
                return False
            pct_change = (abs(value - calculation.previous_value) / calculation.previous_value) * 100
            return pct_change >= alert.threshold_percent
        
        return False
    
    def _send_alert_notifications(self, alert: KPIAlert, calculation: KPICalculation) -> int:
        """Send alert notifications through configured channels."""
        sent_count = 0
        
        try:
            from apps.notifications.services import NotificationService
            from apps.notifications.tasks import send_kpi_alert_notification

            # Queue async notification delivery
            send_kpi_alert_notification.delay(
                alert_id=alert.id,
                calculation_data={
                    'value': str(calculation.calculated_value),
                    'previous_value': str(calculation.previous_value) if calculation.previous_value else None,
                    'status': calculation.status,
                }
            )
            sent_count += 1
            
        except Exception as e:
            logger.warning(f"Error queueing alert notification: {str(e)}")
        
        return sent_count
    
    def _format_alert_message(self, alert: KPIAlert, calculation: KPICalculation) -> str:
        """Format alert message with KPI details."""
        template = alert.message_template or """
        Alert: {alert_name}
        KPI: {kpi_name} ({kpi_code})
        Current Value: {value}
        Status: {status}
        Condition: {condition}
        """
        
        return template.format(
            alert_name=alert.alert_name,
            kpi_name=calculation.kpi.name,
            kpi_code=calculation.kpi.code,
            value=calculation.calculated_value,
            status=calculation.status,
            condition=f"{alert.get_condition_type_display()} {alert.threshold_value or alert.threshold_percent}"
        )
    
    def acknowledge_alert(self, alert: KPI, notes: str = None) -> bool:
        """Mark alert as acknowledged."""
        try:
            alert.acknowledged_by = self.user
            alert.acknowledged_at = timezone.now()
            if notes:
                alert.resolution_notes = notes
            alert.save()
            return True
        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            return False
