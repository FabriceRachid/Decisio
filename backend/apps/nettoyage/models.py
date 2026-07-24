from django.db import models
from django.contrib.auth.models import User


class CleaningRule(models.Model):
    """
    Reusable data cleaning rules that can be applied to datasets.
    Defines transformation logic like "remove nulls", "standardize format", etc.
    """
    RULE_TYPE_CHOICES = [
        ('remove_nulls', 'Remove Null Values'),
        ('remove_empty_rows', 'Remove Empty or Whitespace Rows'),
        ('drop_rows_by_missing_threshold', 'Drop Rows by Missing Threshold'),
        ('drop_columns_by_missing_threshold', 'Drop Columns by Missing Threshold'),
        ('fill_mean', 'Fill with Mean'),
        ('fill_median', 'Fill with Median'),
        ('fill_mode', 'Fill with Mode'),
        ('fill_value', 'Fill with Custom Value'),
        ('standardize', 'Standardize Format'),
        ('regex_replace', 'Regex Replace'),
        ('remove_duplicates', 'Remove Duplicates'),
        ('normalize', 'Normalize Values'),
        ('convert_dtype', 'Convert Data Type'),
        ('value_map', 'Map Values'),
        ('rename_columns', 'Rename Columns'),
        ('split_column', 'Split Column'),
        ('merge_columns', 'Merge Columns'),
        ('validate_format', 'Validate Format'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    rule_type = models.CharField(max_length=50, choices=RULE_TYPE_CHOICES)
    column_pattern = models.CharField(max_length=200, blank=True, null=True, help_text="Regex pattern for column matching")
    column_names = models.JSONField(default=list, blank=True, help_text="Specific column names to apply rule to")
    parameters = models.JSONField(default=dict, blank=True, help_text="Rule-specific configuration parameters")
    priority = models.IntegerField(default=5, help_text="Execution priority (1-10, higher = first)")
    is_active = models.BooleanField(default=True)
    apply_to_all = models.BooleanField(default=False, help_text="Auto-apply to all new data sources")
    category = models.CharField(max_length=50, blank=True, null=True, help_text="Grouping: formatting, validation, imputation")
    tags = models.JSONField(default=list, blank=True)
    version = models.IntegerField(default=1)
    replaced_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replacements')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rules')
    execution_count = models.IntegerField(default=0)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"
    
    class Meta:
        db_table = 'nettoyage_cleaningrule'
        verbose_name = 'Cleaning Rule'
        verbose_name_plural = 'Cleaning Rules'
        ordering = ['-priority', '-created_at']


class CleaningPipeline(models.Model):
    """
    Named rule sets that can be executed as a reusable cleaning pipeline.
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    rules = models.ManyToManyField(CleaningRule, related_name='pipelines', blank=True)
    source_type_scope = models.CharField(max_length=20, blank=True, null=True, help_text='Optional source type filter')
    quality_gate = models.JSONField(default=dict, blank=True, help_text='Thresholds such as min_quality_score')
    is_active = models.BooleanField(default=True)
    apply_to_all = models.BooleanField(default=False)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cleaning_pipelines')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'nettoyage_cleaningpipeline'
        verbose_name = 'Cleaning Pipeline'
        verbose_name_plural = 'Cleaning Pipelines'
        ordering = ['name']


class CleaningJob(models.Model):
    """
    Tracks execution of cleaning jobs on specific datasets.
    Records progress, results, and any errors encountered.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    source = models.ForeignKey('ingestion.DataSource', on_delete=models.CASCADE, related_name='cleaning_jobs')
    rule = models.ForeignKey(CleaningRule, on_delete=models.CASCADE, related_name='jobs', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_rows = models.IntegerField(null=True, blank=True)
    rows_processed = models.IntegerField(default=0)
    rows_affected = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)
    rows_failed = models.IntegerField(default=0)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True, help_text="Execution time in milliseconds")
    error_message = models.TextField(blank=True, null=True)
    log_file_path = models.CharField(max_length=500, blank=True, null=True)
    batch_size = models.IntegerField(default=1000)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When should it run?")
    worker_id = models.CharField(max_length=100, blank=True, null=True, help_text="Which worker processed this?")
    memory_usage_mb = models.IntegerField(null=True, blank=True, help_text="Peak memory usage")
    cpu_time_ms = models.IntegerField(null=True, blank=True, help_text="CPU time consumed")
    execution_context = models.JSONField(default=dict, blank=True, help_text="Resolved pipeline, rules, and quality gate used for execution")
    is_auto_triggered = models.BooleanField(default=False, help_text='Was this cleaning triggered automatically after upload?')
    export_path = models.CharField(max_length=500, blank=True, null=True, help_text='Latest exported file path')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cleaning_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.rule_id and self.rule:
            return f"Cleaning {self.source.name} with {self.rule.name}"
        return f"Cleaning {self.source.name}"
    
    class Meta:
        db_table = 'nettoyage_cleaningjob'
        verbose_name = 'Cleaning Job'
        verbose_name_plural = 'Cleaning Jobs'
        ordering = ['-created_at']


class CleanedData(models.Model):
    """
    Stores cleaned/transformed data after cleaning jobs complete.
    Links back to original raw data for comparison and audit trail.
    """
    job = models.ForeignKey(CleaningJob, on_delete=models.CASCADE, related_name='cleaned_results')
    original_data = models.ForeignKey('ingestion.RawData', on_delete=models.SET_NULL, null=True, related_name='cleaned_versions')
    data = models.JSONField(help_text="Cleaned row data as JSON object")
    changes_made = models.JSONField(default=list, help_text="List of transformations applied")
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Data quality score 0-100")
    is_validated = models.BooleanField(default=False, help_text="Has human validated this?")
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_cleaned_data')
    validation_notes = models.TextField(blank=True, null=True)
    export_path = models.CharField(max_length=500, blank=True, null=True, help_text="Where exported cleaned data?")
    
    cleaned_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Cleaned data from job {self.job.id}"
    
    class Meta:
        db_table = 'nettoyage_cleaneddata'
        verbose_name = 'Cleaned Data'
        verbose_name_plural = 'Cleaned Data'
        unique_together = ['job', 'original_data']
        indexes = [
            models.Index(fields=['job', 'original_data']),
        ]
