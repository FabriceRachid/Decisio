"""
M4: KPI Serializers
Define request/response schemas for KPI API endpoints.
"""

import ast
import ipaddress
import re
from urllib.parse import urlparse

from rest_framework import serializers
from django.contrib.auth.models import User
from apps.kpi.models import KPI, KPICalculation, KPIAlert


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user information for nested display."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class KPITypeSerializer(serializers.Serializer):
    """Display KPI type choices."""
    value = serializers.CharField()
    label = serializers.CharField()


class KPIListSerializer(serializers.ModelSerializer):
    """Lightweight KPI list view."""
    
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    latest_calculation = serializers.SerializerMethodField()
    calculation_count = serializers.SerializerMethodField()
    
    class Meta:
        model = KPI
        fields = [
            'id', 'name', 'code', 'description', 'category', 'frequency',
            'unit', 'target_value', 'is_active', 'owner_name', 'last_calculated_at',
            'latest_calculation', 'calculation_count', 'created_at'
        ]
    
    def get_latest_calculation(self, obj):
        calc = obj.calculations.first()
        if calc:
            return {
                'value': float(calc.calculated_value),
                'status': calc.status,
                'period_label': calc.period_label
            }
        return None
    
    def get_calculation_count(self, obj):
        return obj.calculations.count()


class KPIDetailSerializer(serializers.ModelSerializer):
    """Complete KPI detail view with full configuration."""
    
    owner_detail = UserMinimalSerializer(source='owner', read_only=True)
    parent_kpi_name = serializers.CharField(source='parent_kpi.name', read_only=True, allow_null=True)
    child_kpis_count = serializers.SerializerMethodField()
    calculations_count = serializers.SerializerMethodField()
    alerts_count = serializers.SerializerMethodField()
    latest_calculation = serializers.SerializerMethodField()
    formula_safe = serializers.BooleanField(read_only=True, default=True)  # Mark if formula is safe
    
    class Meta:
        model = KPI
        fields = [
            'id', 'name', 'code', 'description', 'category', 'frequency',
            'unit', 'formula', 'formula_type', 'target_value', 'operator',
            'warning_threshold', 'critical_threshold',
            'source_table', 'measure_column', 'dimension_columns', 'filter_conditions',
            'aggregation_method', 'visualization_type',
            'owner_detail', 'is_active', 'is_public', 'tags',
            'parent_kpi_name', 'benchmark_source',
            'last_calculated_at', 'created_at', 'updated_at',
            'child_kpis_count', 'calculations_count', 'alerts_count',
            'latest_calculation', 'formula_safe'
        ]
    
    def get_child_kpis_count(self, obj):
        return obj.child_kpis.count()
    
    def get_calculations_count(self, obj):
        return obj.calculations.count()
    
    def get_alerts_count(self, obj):
        return obj.alerts.count()
    
    def get_latest_calculation(self, obj):
        calc = obj.calculations.first()
        if calc:
            return KPICalculationSummarySerializer(calc).data
        return None


class KPICreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating KPIs."""

    DANGEROUS_SQL_KEYWORDS = (
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
        'TRUNCATE', 'CREATE', 'GRANT', 'REVOKE'
    )
    DANGEROUS_PYTHON_PATTERNS = (
        '__', '__import__', 'exec', 'eval', 'open', 'file',
        'compile', 'globals', 'locals', 'subprocess', 'pickle', 'os.'
    )
    
    class Meta:
        model = KPI
        fields = [
            'name', 'code', 'description', 'category', 'frequency',
            'unit', 'formula', 'formula_type', 'target_value', 'operator',
            'warning_threshold', 'critical_threshold',
            'source_table', 'measure_column', 'dimension_columns', 'filter_conditions',
            'aggregation_method', 'visualization_type',
            'is_active', 'is_public', 'tags', 'parent_kpi', 'benchmark_source'
        ]
    
    def validate_code(self, value):
        """Ensure KPI code is unique (except when updating)."""
        if self.instance:
            # Updating
            if KPI.objects.filter(code=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("KPI code must be unique")
        else:
            # Creating
            if KPI.objects.filter(code=value).exists():
                raise serializers.ValidationError("KPI code must be unique")
        return value
    
    def validate_formula(self, value):
        """Validate formula syntax based on type."""
        formula_type = self.initial_data.get('formula_type', 'sql')
        normalized = value.strip()
        
        if formula_type == 'sql':
            upper_value = normalized.upper()

            if not upper_value.startswith('SELECT'):
                raise serializers.ValidationError("SQL formula must start with SELECT")
            if 'FROM' not in upper_value:
                raise serializers.ValidationError("SQL formula must contain SELECT and FROM")
            if ';' in normalized.rstrip(';'):
                raise serializers.ValidationError("SQL formula must contain only one statement")
            if '--' in value or '/*' in value or '*/' in value:
                raise serializers.ValidationError("SQL comments are not allowed in formulas")
            if any(re.search(rf'\b{keyword}\b', upper_value) for keyword in self.DANGEROUS_SQL_KEYWORDS):
                raise serializers.ValidationError("Only read-only SELECT statements are allowed")
        elif formula_type == 'python':
            lower_value = normalized.lower()
            for pattern in self.DANGEROUS_PYTHON_PATTERNS:
                if pattern.lower() in lower_value:
                    raise serializers.ValidationError(f"Formula cannot contain '{pattern}'")
            try:
                ast.parse(normalized, mode='eval')
            except SyntaxError as exc:
                raise serializers.ValidationError("Python formula must be a single expression") from exc
        
        return value

    def validate_source_table(self, value):
        """Limit source table names to a safe identifier format."""
        if value and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
            raise serializers.ValidationError("Source table must be a simple table identifier")
        return value


class KPICalculationSummarySerializer(serializers.ModelSerializer):
    """Summary view of KPI calculation."""
    
    kpi_name = serializers.CharField(source='kpi.name', read_only=True)
    kpi_code = serializers.CharField(source='kpi.code', read_only=True)
    executed_by_name = serializers.CharField(source='executed_by.get_full_name', read_only=True)
    
    class Meta:
        model = KPICalculation
        fields = [
            'id', 'kpi_name', 'kpi_code', 'period_label',
            'calculated_value', 'previous_value', 'variance_percent', 'status',
            'executed_by_name', 'executed_at', 'data_quality_score'
        ]


class KPICalculationDetailSerializer(serializers.ModelSerializer):
    """Complete KPI calculation with all details and breakdown."""
    
    kpi_detail = KPIDetailSerializer(source='kpi', read_only=True)
    executed_by_detail = UserMinimalSerializer(source='executed_by', read_only=True)
    variance_display = serializers.SerializerMethodField()
    
    class Meta:
        model = KPICalculation
        fields = [
            'id', 'kpi_detail', 'period_start', 'period_end', 'period_label',
            'calculated_value', 'previous_value', 'variance_absolute', 'variance_percent',
            'target_variance', 'status', 'breakdown',
            'calculation_method', 'data_quality_score', 'rows_processed',
            'execution_time_ms', 'executed_by_detail', 'notes',
            'forecast_value', 'confidence_interval', 'anomaly_detected',
            'executed_at', 'variance_display'
        ]
    
    def get_variance_display(self, obj):
        """Human-readable variance display."""
        if obj.variance_percent is not None:
            direction = "↑" if obj.variance_percent > 0 else "↓"
            return f"{direction} {abs(obj.variance_percent):.2f}% from previous period"
        return "No previous data"


class KPICalculationCreateSerializer(serializers.Serializer):
    """Request schema for manual KPI calculation triggering."""
    
    kpi_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of KPI IDs to calculate"
    )
    period_start = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    period_end = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    recalculate = serializers.BooleanField(default=False, help_text="Force recalculation even if exists")

    def validate_kpi_ids(self, value):
        """Prevent oversized batch operations."""
        if not value:
            raise serializers.ValidationError("At least one KPI must be provided")
        if len(value) > 100:
            raise serializers.ValidationError("Batch calculation is limited to 100 KPIs per request")
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        """Ensure the requested date range is coherent."""
        period_start = attrs.get('period_start')
        period_end = attrs.get('period_end')

        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError("period_end must be on or after period_start")

        return attrs


class AutoKPIColumnSerializer(serializers.Serializer):
    name = serializers.CharField()
    type = serializers.CharField()
    samples = serializers.ListField()
    null_ratio = serializers.FloatField()
    unique_ratio = serializers.FloatField()


class AutoKPIDetectResponseSerializer(serializers.Serializer):
    source_id = serializers.IntegerField()
    source_name = serializers.CharField()
    domain_profile = serializers.JSONField()
    columns = serializers.DictField(child=AutoKPIColumnSerializer(many=True))
    suggestions = serializers.ListField(child=serializers.JSONField())
    period_label = serializers.CharField()


class KPIAnomalySerializer(serializers.Serializer):
    """Anomaly detection result for a KPI."""
    
    has_anomaly = serializers.BooleanField()
    z_score = serializers.FloatField(required=False)
    mean = serializers.FloatField(required=False)
    std_dev = serializers.FloatField(required=False)
    latest_value = serializers.FloatField(required=False)
    method = serializers.CharField()
    reason = serializers.CharField(required=False)
    explanation = serializers.CharField()
    recommendation = serializers.CharField()


class KPIForecastSerializer(serializers.Serializer):
    """KPI forecast for future periods."""
    
    success = serializers.BooleanField()
    forecast_values = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        help_text="Projected values for next periods"
    )
    confidence_intervals = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        required=False
    )
    trend = serializers.CharField(required=False, help_text="increasing, decreasing, stable")
    confidence = serializers.FloatField(required=False, help_text="Forecast confidence 0-100")
    r_squared = serializers.FloatField(required=False, help_text="Model fit quality")


class KPIAlertListSerializer(serializers.ModelSerializer):
    """Alert list view."""
    
    kpi_name = serializers.CharField(source='kpi.name', read_only=True)
    kpi_code = serializers.CharField(source='kpi.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = KPIAlert
        fields = [
            'id', 'alert_name', 'kpi_name', 'kpi_code', 'alert_type',
            'condition_type', 'threshold_value', 'is_active', 'is_triggered',
            'last_triggered_at', 'trigger_count', 'created_by_name', 'created_at'
        ]


class KPIAlertDetailSerializer(serializers.ModelSerializer):
    """Complete alert configuration."""
    
    kpi_detail = KPIDetailSerializer(source='kpi', read_only=True)
    created_by_detail = UserMinimalSerializer(source='created_by', read_only=True)
    acknowledged_by_detail = UserMinimalSerializer(source='acknowledged_by', read_only=True, required=False)
    
    class Meta:
        model = KPIAlert
        fields = [
            'id', 'kpi_detail', 'alert_name', 'alert_type',
            'condition_type', 'threshold_value', 'threshold_percent',
            'notification_channels', 'recipients', 'webhook_url', 'message_template',
            'is_active', 'is_triggered', 'trigger_count', 'last_triggered_at', 'last_value',
            'cooldown_minutes', 'mute_until',
            'escalation_policy', 'acknowledged_by_detail', 'acknowledged_at',
            'resolution_notes', 'created_by_detail', 'created_at', 'updated_at'
        ]


class KPIAlertCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/update alert configuration."""
    
    class Meta:
        model = KPIAlert
        fields = [
            'kpi', 'alert_name', 'alert_type', 'condition_type',
            'threshold_value', 'threshold_percent',
            'notification_channels', 'recipients', 'webhook_url', 'message_template',
            'is_active', 'cooldown_minutes', 'mute_until', 'escalation_policy'
        ]

    def validate_webhook_url(self, value):
        """Reject internal and metadata endpoints to reduce SSRF exposure."""
        if not value:
            return value

        parsed = urlparse(value)
        host = (parsed.hostname or '').lower()

        blocked_hosts = {'localhost', 'metadata.google.internal'}
        if host in blocked_hosts:
            raise serializers.ValidationError("Internal webhook endpoints are not allowed")

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise serializers.ValidationError("Internal webhook endpoints are not allowed")
        except ValueError:
            if host.endswith('.local'):
                raise serializers.ValidationError("Internal webhook endpoints are not allowed")

        return value


class KPIAcknowledgeAlertSerializer(serializers.Serializer):
    """Acknowledge alert with optional notes."""
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Resolution or investigation notes"
    )


class KPIDashboardStatSerializer(serializers.Serializer):
    """KPI dashboard statistics and metrics."""
    
    total_kpis = serializers.IntegerField()
    kpis_active = serializers.IntegerField()
    kpis_on_target = serializers.IntegerField()
    kpis_warning = serializers.IntegerField()
    kpis_critical = serializers.IntegerField()
    
    by_category = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Count of KPIs by category"
    )
    by_frequency = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Count of KPIs by calculation frequency"
    )
    
    calculation_success_rate = serializers.FloatField(help_text="Percentage of successful calculations")
    avg_data_quality = serializers.FloatField(help_text="Average data quality score")
    
    active_alerts = serializers.IntegerField()
    triggered_this_week = serializers.IntegerField()
    
    top_performers = serializers.ListField(
        child=serializers.DictField(),
        help_text="Top 5 KPIs by performance"
    )
    bottom_performers = serializers.ListField(
        child=serializers.DictField(),
        help_text="Bottom 5 KPIs needing attention"
    )


class KPIVarianceAnalysisSerializer(serializers.Serializer):
    """Variance analysis between two periods."""
    
    kpi_name = serializers.CharField()
    kpi_code = serializers.CharField()
    
    current_period = serializers.DictField(help_text="Current period data")
    previous_period = serializers.DictField(help_text="Previous period data")
    
    absolute_variance = serializers.FloatField()
    percent_variance = serializers.FloatField()
    trend = serializers.CharField(help_text="increasing, decreasing, stable")
    
    vs_target = serializers.DictField(help_text="Performance vs target")
    
    key_drivers = serializers.ListField(
        child=serializers.DictField(),
        help_text="What drove the variance"
    )


class KPIHistorySerializer(serializers.ModelSerializer):
    """Historical KPI calculations for charting."""
    
    kpi_code = serializers.CharField(source='kpi.code', read_only=True)
    
    class Meta:
        model = KPICalculation
        fields = [
            'id', 'kpi_code', 'period_label', 'period_start', 'period_end',
            'calculated_value', 'previous_value', 'variance_percent', 'status',
            'target_variance', 'data_quality_score', 'anomaly_detected', 'executed_at'
        ]


class KPIExportRequestSerializer(serializers.Serializer):
    """Request schema for exporting KPI data."""
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('pdf', 'PDF Report')
    ]
    
    kpi_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="KPI IDs to export"
    )
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='csv')
    include_history = serializers.BooleanField(default=True)
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)


class KPIEngineFilterSerializer(serializers.Serializer):
    field = serializers.CharField()
    operator = serializers.ChoiceField(
        choices=['eq', 'neq', 'in', 'not_in', 'contains', 'gte', 'lte', 'gt', 'lt', 'between'],
        default='eq',
    )
    value = serializers.JSONField()


class KPIEngineRequestSerializer(serializers.Serializer):
    nom_kpi = serializers.CharField(required=False, allow_blank=True, default="")
    mesure = serializers.CharField(required=False, allow_blank=True)
    measure = serializers.CharField(required=False, allow_blank=True, write_only=True)
    aggregation = serializers.ChoiceField(choices=['sum', 'avg', 'mean', 'count', 'min', 'max', 'median', 'std', 'first', 'last'])
    source_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_table = serializers.CharField(required=False, default='nettoyage_cleaneddata')
    group_by = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    filters = serializers.ListField(child=KPIEngineFilterSerializer(), required=False, default=list)
    filtres = serializers.JSONField(required=False, default=dict)
    include_totals = serializers.BooleanField(required=False, default=False)
    fill_nulls = serializers.JSONField(required=False, allow_null=True, default=0)
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)

    def validate(self, attrs):
        measure = (attrs.get('mesure') or attrs.get('measure') or '').strip()
        aggregation = attrs.get('aggregation')

        if not measure and aggregation != 'count':
            raise serializers.ValidationError({'mesure': 'This field is required.'})

        attrs['mesure'] = measure
        attrs.pop('measure', None)

        if not attrs.get('nom_kpi'):
            attrs['nom_kpi'] = measure or 'count'

        return attrs


class PivotTableRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, default='Tableau croise')
    source_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_table = serializers.CharField(required=False, default='nettoyage_cleaneddata')
    valeur = serializers.CharField(required=False, allow_blank=True)
    lignes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    colonnes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    rows = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    columns = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    metric = serializers.CharField(required=False, allow_blank=True)
    aggregation = serializers.ChoiceField(choices=['sum', 'avg', 'mean', 'count', 'min', 'max', 'median', 'std', 'first', 'last'])
    aggfunc = serializers.JSONField(required=False, default='sum')
    filtres = serializers.JSONField(required=False, default=dict)
    filters = serializers.ListField(child=KPIEngineFilterSerializer(), required=False, default=list)
    totaux = serializers.BooleanField(required=False, default=True)
    include_totals = serializers.BooleanField(required=False, default=True)
    top_n = serializers.IntegerField(required=False, allow_null=True)
    fill_nulls = serializers.JSONField(required=False, allow_null=True, default=0)
    dropna = serializers.BooleanField(required=False, default=False)
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)


class DashboardWidgetRequestSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(required=False, allow_blank=True)
    type = serializers.ChoiceField(
        choices=['kpi_card', 'bar_chart', 'line_chart', 'table', 'pivot_table', 'alerts', 'trend']
    )
    source_table = serializers.CharField(default='nettoyage_cleaneddata')
    mesure = serializers.CharField(required=False, allow_blank=True)
    aggregation = serializers.ChoiceField(choices=['sum', 'avg', 'mean', 'count', 'min', 'max', 'median'], required=False, default='sum')
    group_by = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    rows = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    columns = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    filters = serializers.ListField(child=KPIEngineFilterSerializer(), required=False, default=list)
    show_totals = serializers.BooleanField(required=False, default=True)
    visible = serializers.BooleanField(required=False, default=True)


class DashboardPreviewRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, default='Dashboard dynamique')
    period_start = serializers.DateField(required=False)
    period_end = serializers.DateField(required=False)
    filters = serializers.ListField(child=KPIEngineFilterSerializer(), required=False, default=list)
    widgets = DashboardWidgetRequestSerializer(many=True)


class DashboardPreviewWidgetSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField()
    type = serializers.CharField()
    visible = serializers.BooleanField()
    payload = serializers.JSONField()


class DashboardPreviewResponseSerializer(serializers.Serializer):
    title = serializers.CharField()
    widgets = DashboardPreviewWidgetSerializer(many=True)
    filters = serializers.ListField(child=KPIEngineFilterSerializer(), required=False)
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)


class AdvancedPivotFilterSerializer(serializers.Serializer):
    """Filter for advanced pivot table."""
    field = serializers.CharField()
    operator = serializers.ChoiceField(choices=['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'between', 'contains'])
    value = serializers.JSONField()


class AdvancedPivotRequestSerializer(serializers.Serializer):
    """Request schema for advanced pivot table with multi-level hierarchies."""

    source_id = serializers.IntegerField()
    source_type = serializers.ChoiceField(choices=['raw', 'cleaned'], default='cleaned')
    row_fields = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    column_fields = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    value_field = serializers.CharField()
    aggregation = serializers.ChoiceField(
        choices=['sum', 'avg', 'mean', 'count', 'min', 'max', 'median', 'std'],
        default='sum'
    )
    filters = AdvancedPivotFilterSerializer(many=True, required=False, default=list)
    include_totals = serializers.BooleanField(default=True)
    include_running_totals = serializers.BooleanField(default=False)
    format_currency = serializers.BooleanField(default=False)
    sort_by = serializers.ChoiceField(choices=['value', 'label'], default='value')
    sort_direction = serializers.ChoiceField(choices=['asc', 'desc'], default='desc')
    top_n = serializers.IntegerField(required=False, allow_null=True)

    def validate_row_fields(self, value):
        """Validate row fields are strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("row_fields must be a list")
        if any(not isinstance(f, str) for f in value):
            raise serializers.ValidationError("All row fields must be strings")
        return value

    def validate_column_fields(self, value):
        """Validate column fields are strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("column_fields must be a list")
        if any(not isinstance(f, str) for f in value):
            raise serializers.ValidationError("All column fields must be strings")
        return value

    def validate(self, attrs):
        """Validate combined constraints."""
        if not attrs.get('row_fields') and not attrs.get('column_fields'):
            raise serializers.ValidationError("At least one of row_fields or column_fields must be specified")

        if not attrs.get('value_field'):
            raise serializers.ValidationError("value_field is required")

        top_n = attrs.get('top_n')
        if top_n is not None and (top_n < 1 or top_n > 10000):
            raise serializers.ValidationError("top_n must be between 1 and 10000")

        return attrs


class AdvancedPivotResponseSerializer(serializers.Serializer):
    """Response schema for advanced pivot table."""

    pivot = serializers.ListField(child=serializers.ListField(child=serializers.FloatField()))
    formatted_pivot = serializers.ListField(child=serializers.ListField(child=serializers.CharField()), required=False)
    row_headers = serializers.ListField(child=serializers.CharField())
    col_headers = serializers.ListField(child=serializers.CharField())
    row_labels = serializers.ListField(child=serializers.CharField())
    col_labels = serializers.ListField(child=serializers.CharField())
    totals = serializers.JSONField()
    metadata = serializers.JSONField()
    drill_down_available = serializers.JSONField()


class PivotDrillDownRequestSerializer(serializers.Serializer):
    """Request schema for pivot drill-down."""

    pivot_config = AdvancedPivotRequestSerializer()
    row_key = serializers.CharField(required=False, allow_blank=True)
    col_key = serializers.CharField(required=False, allow_blank=True)


class PivotDrillDownResponseSerializer(serializers.Serializer):
    """Response schema for pivot drill-down."""

    rows = serializers.ListField(child=serializers.JSONField())
    row_count = serializers.IntegerField()
    columns = serializers.ListField(child=serializers.CharField())

