from django.db import models
from django.contrib.auth.models import User


class ConflictType(models.Model):
    """
    Categories of data conflicts that can be detected.
    Defines conflict types like "Duplicate Record", "Missing Field", etc.
    """
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code for programmatic access")
    description = models.TextField(blank=True, null=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    auto_resolve = models.BooleanField(default=False, help_text="Can system auto-resolve this?")
    resolution_strategy = models.CharField(max_length=50, blank=True, null=True, help_text="default_value, majority_vote, latest_value")
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="UI icon for this conflict type")
    color_code = models.CharField(max_length=7, blank=True, null=True, help_text="UI color: #FF5733")
    documentation_url = models.URLField(max_length=500, blank=True, null=True, help_text="Link to resolution guide")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        db_table = 'conflits_conflicttype'
        verbose_name = 'Conflict Type'
        verbose_name_plural = 'Conflict Types'
        ordering = ['severity', 'name']


class Conflict(models.Model):
    """
    Detected data conflicts in uploaded datasets.
    Tracks specific instances of data quality issues.
    """
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('investigating', 'Investigating'),
        ('resolving', 'Resolving'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    
    data_source = models.ForeignKey('ingestion.DataSource', on_delete=models.CASCADE, related_name='conflicts')
    conflict_type = models.ForeignKey(ConflictType, on_delete=models.CASCADE, related_name='conflicts')
    affected_table = models.CharField(max_length=100, blank=True, null=True)
    affected_columns = models.JSONField(default=list, help_text="List of column names involved")
    affected_row_ids = models.JSONField(default=list, help_text="Row numbers or IDs involved")
    conflict_details = models.JSONField(help_text="Specific conflict information")
    description = models.TextField(blank=True, null=True)
    group_name = models.CharField(max_length=200, blank=True, null=True, help_text="User-defined group label for batch operations")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    priority = models.IntegerField(default=5, help_text="Priority 1-10 (manual override of severity)")
    detected_by = models.CharField(max_length=50, default='system', help_text="system, user, api")
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_conflicts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_conflicts')
    due_date = models.DateTimeField(null=True, blank=True, help_text="SLA deadline")
    recurrence_id = models.IntegerField(null=True, blank=True, help_text="Links recurring instances of same conflict")
    parent_conflict = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_conflicts')
    impact_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Business impact 0-100")
    estimated_resolution_time = models.IntegerField(null=True, blank=True, help_text="Estimated resolution time in minutes")
    
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True, null=True, help_text="How was it resolved?")
    
    detected_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.conflict_type.name} in {self.data_source.name}"
    
    class Meta:
        db_table = 'conflits_conflict'
        verbose_name = 'Conflict'
        verbose_name_plural = 'Conflicts'
        ordering = ['-priority', '-detected_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['detected_at']),
        ]


class ConflictResolution(models.Model):
    """
    Records of how conflicts were resolved.
    Maintains audit trail of data quality decisions.
    """
    RESOLUTION_METHOD_CHOICES = [
        ('manual_override', 'Manual Override'),
        ('auto_merge', 'Auto Merge'),
        ('default_value', 'Use Default Value'),
        ('user_selected', 'User Selected'),
        ('majority_vote', 'Majority Vote'),
        ('latest_value', 'Latest Value'),
        ('discard', 'Discard Invalid Data'),
    ]
    
    conflict = models.ForeignKey(Conflict, on_delete=models.CASCADE, related_name='resolutions')
    resolution_method = models.CharField(max_length=50, choices=RESOLUTION_METHOD_CHOICES)
    chosen_value = models.JSONField(blank=True, null=True, help_text="What value was chosen?")
    alternative_values = models.JSONField(blank=True, null=True, help_text="What were the options?")
    resolution_notes = models.TextField(blank=True, null=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Confidence in this resolution 0-100")
    is_reversible = models.BooleanField(default=True, help_text="Can we undo this if wrong?")
    rollback_data = models.JSONField(blank=True, null=True, help_text="What to restore if rolled back?")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_resolutions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approval_required = models.BooleanField(default=False, help_text="Needs manager approval?")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_resolutions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    resolved_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_resolutions')
    resolved_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Resolution for conflict {self.conflict.id}"
    
    class Meta:
        db_table = 'conflits_conflictresolution'
        verbose_name = 'Conflict Resolution'
        verbose_name_plural = 'Conflict Resolutions'
        ordering = ['-resolved_at']


# System & Audit Tables (in conflits app for organization)

class ActivityLog(models.Model):
    """
    Comprehensive audit trail of all user actions.
    Tracks who did what, when, and from where.
    """
    ACTION_TYPE_CHOICES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export'),
        ('import', 'Import'),
    ]
    
    # Actor
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_email = models.CharField(max_length=255, blank=True, null=True)
    user_role = models.CharField(max_length=20, blank=True, null=True)
    
    # Action
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES)
    resource_type = models.CharField(max_length=100)
    resource_id = models.IntegerField(null=True, blank=True)
    resource_name = models.CharField(max_length=500, blank=True, null=True)
    
    # Details
    action_details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Location
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=200, blank=True, null=True)
    
    # Performance
    response_time_ms = models.IntegerField(null=True, blank=True)
    status_code = models.IntegerField(default=200)
    
    # Risk assessment
    risk_score = models.IntegerField(null=True, blank=True)
    flagged_for_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_activity_logs')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"{self.action_type} {self.resource_type} by {self.user_email or 'Anonymous'}"
    
    class Meta:
        db_table = 'system_activitylog'
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['action_type']),
        ]


class SystemConfig(models.Model):
    """
    Application configuration settings.
    Centralized key-value store for system-wide settings.
    """
    VALUE_TYPE_CHOICES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('secret', 'Secret'),
    ]
    
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('security', 'Security'),
        ('email', 'Email'),
        ('storage', 'Storage'),
        ('ml', 'Machine Learning'),
        ('ui', 'User Interface'),
    ]
    
    config_key = models.CharField(max_length=100, unique=True)
    config_value = models.TextField()
    value_type = models.CharField(max_length=20, choices=VALUE_TYPE_CHOICES)
    
    # Metadata
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='general')
    is_public = models.BooleanField(default=False, help_text="Visible to all users?")
    is_editable = models.BooleanField(default=True, help_text="Can admins modify?")
    
    # Validation
    validation_regex = models.CharField(max_length=500, blank=True, null=True)
    allowed_values = models.JSONField(default=list, blank=True)
    min_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    # Change tracking
    previous_value = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.TextField(blank=True, null=True)
    
    # Advanced features
    environment = models.CharField(max_length=20, choices=[
        ('development', 'Development'),
        ('staging', 'Staging'),
        ('production', 'Production'),
    ], default='production')
    encrypted = models.BooleanField(default=False)
    requires_restart = models.BooleanField(default=False)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.config_key
    
    class Meta:
        db_table = 'system_systemconfig'
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configurations'
        ordering = ['category', 'config_key']


class ScheduledJob(models.Model):
    """
    Automated background tasks with scheduling.
    Manages recurring jobs like data ingestion, KPI calculation, backups.
    """
    JOB_TYPE_CHOICES = [
        ('data_ingestion', 'Data Ingestion'),
        ('cleaning', 'Data Cleaning'),
        ('kpi_calc', 'KPI Calculation'),
        ('backup', 'Database Backup'),
        ('report_generation', 'Report Generation'),
        ('anomaly_detection', 'Anomaly Detection'),
    ]
    
    SCHEDULE_TYPE_CHOICES = [
        ('cron', 'Cron Expression'),
        ('interval', 'Fixed Interval'),
        ('once', 'One-time'),
    ]
    
    job_name = models.CharField(max_length=200)
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES)
    
    # Schedule
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES)
    cron_expression = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., '0 2 * * *' for daily at 2 AM")
    interval_minutes = models.IntegerField(null=True, blank=True)
    run_at = models.DateTimeField(null=True, blank=True, help_text="For one-time jobs")
    
    # Job configuration
    job_parameters = models.JSONField()
    
    # Execution tracking
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_run_status = models.CharField(max_length=20, blank=True, null=True)
    last_run_duration_ms = models.IntegerField(null=True, blank=True)
    last_error_message = models.TextField(blank=True, null=True)
    
    next_run_at = models.DateTimeField(null=True, blank=True)
    
    # Control
    is_active = models.BooleanField(default=True)
    is_running = models.BooleanField(default=False)
    concurrency_policy = models.CharField(max_length=20, choices=[
        ('skip', 'Skip If Running'),
        ('queue', 'Queue For Later'),
        ('parallel', 'Run In Parallel'),
    ], default='skip')
    
    # Retry logic
    max_retries = models.IntegerField(default=3)
    retry_delay_minutes = models.IntegerField(default=5)
    current_retry_count = models.IntegerField(default=0)
    
    # Notifications
    notify_on_success = models.BooleanField(default=False)
    notify_on_failure = models.BooleanField(default=True)
    notification_recipients = models.JSONField(default=list, blank=True)
    
    # Ownership
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_jobs')
    owned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_jobs')
    
    # Advanced features
    timeout_minutes = models.IntegerField(default=60)
    resource_limit = models.JSONField(default=dict, blank=True)
    run_history_days = models.IntegerField(default=30)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.job_name} ({self.get_job_type_display()})"
    
    class Meta:
        db_table = 'system_scheduledjob'
        verbose_name = 'Scheduled Job'
        verbose_name_plural = 'Scheduled Jobs'
        ordering = ['-is_active', 'next_run_at']
        indexes = [
            models.Index(fields=['next_run_at']),
            models.Index(fields=['is_active']),
        ]
