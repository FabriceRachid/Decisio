from django.db import models
from django.contrib.auth.models import User


class KPI(models.Model):
    """
    Key Performance Indicator definitions.
    Defines metrics, formulas, targets, and calculation frequency.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    OPERATOR_CHOICES = [
        ('>=', 'Greater than or equal'),
        ('<=', 'Less than or equal'),
        ('=', 'Equals'),
        ('>', 'Greater than'),
        ('<', 'Less than'),
    ]
    
    FORMULA_TYPE_CHOICES = [
        ('sql', 'SQL Expression'),
        ('python', 'Python Code'),
        ('excel', 'Excel Formula'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, help_text="Short code: REV_Q1, CHURN_RATE")
    description = models.TextField(blank=True, null=True)
    formula = models.TextField(help_text="SQL expression or Python code")
    formula_type = models.CharField(max_length=20, choices=FORMULA_TYPE_CHOICES, default='sql')
    target_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    operator = models.CharField(max_length=2, choices=OPERATOR_CHOICES, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, null=True, help_text="%, $, units, hours, etc.")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    category = models.CharField(max_length=100, blank=True, null=True, help_text="Financial, Operational, Customer, etc.")
    
    # Data source configuration
    source_table = models.CharField(max_length=100, blank=True, null=True)
    measure_column = models.CharField(max_length=100, blank=True, null=True)
    dimension_columns = models.JSONField(default=list, blank=True, help_text="Group by fields")
    filter_conditions = models.JSONField(default=dict, blank=True, help_text="WHERE clauses")
    
    # Metadata
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_kpis')
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Thresholds for alerts
    warning_threshold = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    # Additional features
    parent_kpi = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_kpis')
    aggregation_method = models.CharField(max_length=20, blank=True, null=True, help_text="SUM, AVG, COUNT, MIN, MAX")
    benchmark_source = models.CharField(max_length=100, blank=True, null=True, help_text="Industry benchmark")
    visualization_type = models.CharField(max_length=20, blank=True, null=True, help_text="gauge, trend, bar")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_calculated_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        db_table = 'kpi_kpi'
        verbose_name = 'KPI'
        verbose_name_plural = 'KPIs'
        ordering = ['category', 'name']


class KPICalculation(models.Model):
    """
    Stores calculated KPI values for specific time periods.
    Tracks historical performance and trends.
    """
    STATUS_CHOICES = [
        ('on_target', 'On Target'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    CALCULATION_METHOD_CHOICES = [
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('estimated', 'Estimated'),
    ]
    
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='calculations')
    period_start = models.DateField()
    period_end = models.DateField()
    period_label = models.CharField(max_length=100, blank=True, null=True, help_text="Q1 2026, January 2026")
    
    # Calculation result
    calculated_value = models.DecimalField(max_digits=20, decimal_places=4)
    previous_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    variance_absolute = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    variance_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    target_variance = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    
    # Breakdown by dimensions
    breakdown = models.JSONField(default=dict, blank=True, help_text="By region, product, etc.")
    
    # Execution details
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHOD_CHOICES, default='automatic')
    data_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rows_processed = models.IntegerField(null=True, blank=True)
    execution_time_ms = models.IntegerField(null=True, blank=True)
    executed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='executed_kpi_calcs')
    notes = models.TextField(blank=True, null=True, help_text="Manual adjustments?")
    
    # Advanced features
    forecast_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    confidence_interval = models.JSONField(default=list, blank=True, help_text="[lower_bound, upper_bound]")
    anomaly_detected = models.BooleanField(default=False, help_text="Is this value unusual?")
    
    executed_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.kpi.code} - {self.period_label}"
    
    class Meta:
        db_table = 'kpi_kpicalculation'
        verbose_name = 'KPI Calculation'
        verbose_name_plural = 'KPI Calculations'
        unique_together = ['kpi', 'period_start', 'period_end']
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['kpi', 'period_start']),
        ]


class KPIAlert(models.Model):
    """
    Alert configurations for KPI threshold breaches.
    Notifies users when KPIs go above/below defined thresholds.
    """
    ALERT_TYPE_CHOICES = [
        ('threshold_breach', 'Threshold Breach'),
        ('anomaly', 'Anomaly Detection'),
        ('scheduled', 'Scheduled Report'),
    ]
    
    CONDITION_TYPE_CHOICES = [
        ('above', 'Above'),
        ('below', 'Below'),
        ('equals', 'Equals'),
        ('changed_by', 'Changed By %'),
    ]
    
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='alerts')
    alert_name = models.CharField(max_length=200)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    condition_type = models.CharField(max_length=10, choices=CONDITION_TYPE_CHOICES)
    threshold_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    threshold_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Notification settings
    notification_channels = models.JSONField(default=list, help_text="['email', 'slack', 'sms', 'webhook']")
    recipients = models.JSONField(default=list, help_text="List of user IDs or emails")
    webhook_url = models.URLField(max_length=500, blank=True, null=True)
    message_template = models.TextField(blank=True, null=True, help_text="Custom alert message")
    
    # Alert state
    is_active = models.BooleanField(default=True)
    is_triggered = models.BooleanField(default=False)
    trigger_count = models.IntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    # Cooldown settings
    cooldown_minutes = models.IntegerField(default=60, help_text="Minutes between alerts")
    mute_until = models.DateTimeField(null=True, blank=True, help_text="Temporarily disable")
    
    # Advanced features
    escalation_policy = models.JSONField(default=dict, blank=True, help_text="If not acknowledged in X hours")
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_kpi_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_kpi_alerts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.alert_name} ({self.kpi.code})"
    
    class Meta:
        db_table = 'kpi_kpialert'
        verbose_name = 'KPI Alert'
        verbose_name_plural = 'KPI Alerts'
        ordering = ['-is_active', 'alert_name']
