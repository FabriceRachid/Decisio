"""
M4: KPI Admin Interface
Django admin registration and customization for KPI management.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg

from apps.kpi.models import KPI, KPICalculation, KPIAlert


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    """Admin for KPI definitions."""
    
    list_display = ['code', 'name', 'category', 'frequency_badge', 'target_value', 'status_badge', 'last_calculated_at', 'calculation_count']
    list_filter = ['category', 'frequency', 'is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_calculated_at', 'calculation_count_display']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'category')
        }),
        ('Formula Configuration', {
            'fields': ('formula', 'formula_type', 'aggregation_method')
        }),
        ('Data Source', {
            'fields': ('source_table', 'measure_column', 'dimension_columns', 'filter_conditions')
        }),
        ('Target & Thresholds', {
            'fields': ('target_value', 'operator', 'warning_threshold', 'critical_threshold', 'unit')
        }),
        ('Schedule & Visibility', {
            'fields': ('frequency', 'is_active', 'is_public', 'tags')
        }),
        ('Hierarchy & Benchmarking', {
            'fields': ('parent_kpi', 'benchmark_source', 'visualization_type')
        }),
        ('Ownership', {
            'fields': ('owner',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'last_calculated_at', 'calculation_count_display'),
            'classes': ('collapse',)
        })
    )
    
    def frequency_badge(self, obj):
        """Display frequency with badge."""
        colors = {
            'daily': '#0dcaf0',
            'weekly': '#0d6efd',
            'monthly': '#6f42c1',
            'quarterly': '#fd7e14',
            'yearly': '#dc3545'
        }
        color = colors.get(obj.frequency, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_frequency_display()
        )
    frequency_badge.short_description = 'Frequency'
    
    def status_badge(self, obj):
        """Display active status."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">✓ Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )
    status_badge.short_description = 'Status'
    
    def calculation_count(self, obj):
        """Display count of calculations."""
        return obj.calculations.count()
    calculation_count.short_description = 'Calcs'
    
    def calculation_count_display(self, obj):
        """Display detailed calculation count."""
        return obj.calculations.count()
    calculation_count_display.short_description = 'Total Calculations'


@admin.register(KPICalculation)
class KPICalculationAdmin(admin.ModelAdmin):
    """Admin for KPI calculations."""
    
    list_display = ['id', 'kpi_code', 'period_label', 'calculated_value_display', 'status_badge', 'variance_display', 'data_quality_badge', 'executed_at']
    list_filter = ['status', 'calculation_method', 'anomaly_detected', 'executed_at', 'kpi__category']
    search_fields = ['kpi__name', 'kpi__code', 'period_label']
    readonly_fields = ['executed_at', 'execution_details', 'breakdown_display']
    date_hierarchy = 'executed_at'
    
    fieldsets = (
        ('KPI & Period', {
            'fields': ('kpi', 'period_start', 'period_end', 'period_label')
        }),
        ('Calculation Result', {
            'fields': ('calculated_value', 'previous_value', 'variance_absolute', 'variance_percent', 'target_variance', 'status')
        }),
        ('Data Quality', {
            'fields': ('data_quality_score', 'rows_processed', 'execution_time_ms', 'calculation_method')
        }),
        ('Advanced Analysis', {
            'fields': ('breakdown_display', 'forecast_value', 'confidence_interval', 'anomaly_detected')
        }),
        ('Management', {
            'fields': ('notes', 'executed_by')
        }),
        ('Metadata', {
            'fields': ('executed_at', 'execution_details'),
            'classes': ('collapse',)
        })
    )
    
    def kpi_code(self, obj):
        return obj.kpi.code
    kpi_code.short_description = 'KPI Code'
    
    def calculated_value_display(self, obj):
        """Display calculated value with unit."""
        unit = obj.kpi.unit or ''
        return f"{obj.calculated_value} {unit}"
    calculated_value_display.short_description = 'Value'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'on_target': '#198754',
            'warning': '#ffc107',
            'critical': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, 'white' if obj.status != 'warning' else 'black', obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def variance_display(self, obj):
        """Display variance with direction indicator."""
        if obj.variance_percent is not None:
            direction = "↑" if obj.variance_percent > 0 else "↓"
            return f"{direction} {abs(obj.variance_percent):.2f}%"
        return "—"
    variance_display.short_description = 'Variance'
    
    def data_quality_badge(self, obj):
        """Display data quality as badge."""
        score = obj.data_quality_score or 0
        if score >= 80:
            color = '#198754'
        elif score >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{:.0f}%</span>',
            color, score
        )
    data_quality_badge.short_description = 'Quality'
    
    def execution_details(self, obj):
        """Display execution details."""
        return f"Rows: {obj.rows_processed}, Time: {obj.execution_time_ms}ms"
    execution_details.short_description = 'Execution Details'
    
    def breakdown_display(self, obj):
        """Display breakdown JSON."""
        import json
        if obj.breakdown:
            return json.dumps(obj.breakdown, indent=2)
        return "—"
    breakdown_display.short_description = 'Dimensional Breakdown'


@admin.register(KPIAlert)
class KPIAlertAdmin(admin.ModelAdmin):
    """Admin for KPI alerts."""
    
    list_display = ['alert_name', 'kpi_code', 'condition_display', 'is_active_badge', 'is_triggered_badge', 'trigger_count', 'last_triggered_at', 'acknowledgment_status']
    list_filter = ['alert_type', 'condition_type', 'is_active', 'is_triggered', 'created_at']
    search_fields = ['alert_name', 'kpi__name', 'kpi__code']
    readonly_fields = ['created_at', 'updated_at', 'last_triggered_at', 'trigger_history']
    
    fieldsets = (
        ('Alert Configuration', {
            'fields': ('kpi', 'alert_name', 'alert_type')
        }),
        ('Trigger Condition', {
            'fields': ('condition_type', 'threshold_value', 'threshold_percent')
        }),
        ('Notification Channels', {
            'fields': ('notification_channels', 'recipients', 'webhook_url', 'message_template')
        }),
        ('Alert State', {
            'fields': ('is_active', 'is_triggered', 'trigger_count', 'last_triggered_at', 'last_value')
        }),
        ('Cooldown & Escalation', {
            'fields': ('cooldown_minutes', 'mute_until', 'escalation_policy')
        }),
        ('Acknowledgment', {
            'fields': ('acknowledged_by', 'acknowledged_at', 'resolution_notes')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'trigger_history'),
            'classes': ('collapse',)
        })
    )
    
    def kpi_code(self, obj):
        return obj.kpi.code
    kpi_code.short_description = 'KPI'
    
    def condition_display(self, obj):
        """Display trigger condition."""
        threshold = obj.threshold_value or obj.threshold_percent or "?"
        return f"{obj.get_condition_type_display()} {threshold}"
    condition_display.short_description = 'Condition'
    
    def is_active_badge(self, obj):
        """Display active status."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">✓ Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Active'
    
    def is_triggered_badge(self, obj):
        """Display trigger status."""
        if obj.is_triggered:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">⚠️ Triggered</span>'
            )
        return format_html(
            '<span style="background-color: #198754; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">OK</span>'
        )
    is_triggered_badge.short_description = 'Status'
    
    def acknowledgment_status(self, obj):
        """Display acknowledgment status."""
        if obj.acknowledged_at:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">✓ Acked</span>'
            )
        elif obj.is_triggered:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">Pending</span>'
            )
        return "—"
    acknowledgment_status.short_description = 'Acked'
    
    def trigger_history(self, obj):
        """Display trigger history."""
        return f"Triggered {obj.trigger_count} times, Last: {obj.last_triggered_at}"
    trigger_history.short_description = 'History'
