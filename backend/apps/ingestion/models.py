from django.db import models
from django.contrib.auth.models import User


class DataSource(models.Model):
    """
    Metadata about uploaded data sources (files, API connections, etc.).
    Tracks information about datasets without storing the actual data.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    SOURCE_TYPE_CHOICES = [
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
        ('api', 'API Connection'),
        ('database', 'Database'),
        ('json', 'JSON File'),
    ]
    
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    row_count = models.IntegerField(null=True, blank=True)
    column_count = models.IntegerField(null=True, blank=True)
    delimiter = models.CharField(max_length=10, default=',')
    encoding = models.CharField(max_length=20, default='utf-8')
    has_header = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_sources')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    validation_errors = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    checksum_md5 = models.CharField(max_length=32, blank=True, null=True, help_text="MD5 hash to detect duplicates")
    retention_days = models.IntegerField(default=90)
    is_archived = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    schema_version = models.IntegerField(default=1)
    parent_source = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='versions')
    lineage_info = models.JSONField(default=dict, blank=True, help_text="Data provenance information")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"
    
    class Meta:
        db_table = 'ingestion_datasource'
        verbose_name = 'Data Source'
        verbose_name_plural = 'Data Sources'
        ordering = ['-created_at']


class RawData(models.Model):
    """
    Stores raw data rows from uploaded sources.
    Uses JSONB for flexible schema - each row can have different structure.
    """
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='raw_data_rows')
    row_number = models.IntegerField(help_text="Original row number in source file")
    data = models.JSONField(help_text="Raw row data as JSON object")
    data_hash = models.CharField(max_length=64, blank=True, null=True, help_text="Hash to detect duplicate rows")
    validation_status = models.CharField(max_length=20, choices=[
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('warning', 'Warning'),
    ], default='valid')
    validation_messages = models.JSONField(default=list, blank=True)
    partition_key = models.IntegerField(null=True, blank=True, help_text="For partitioning large datasets")
    is_sample = models.BooleanField(default=False, help_text="Is this a sample row?")
    extraction_batch = models.IntegerField(null=True, blank=True, help_text="Batch processing ID")
    
    ingested_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Row {self.row_number} from {self.source.name}"
    
    class Meta:
        db_table = 'ingestion_rawdata'
        verbose_name = 'Raw Data'
        verbose_name_plural = 'Raw Data'
        unique_together = ['source', 'row_number']
        indexes = [
            models.Index(fields=['source', 'row_number']),
        ]


class IngestionJob(models.Model):
    """
    Tracks async ingestion jobs for file uploads.
    Enables long-running uploads without blocking the request.
    """
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    celery_task_id = models.CharField(max_length=200, unique=True, help_text="Celery task ID for tracking")
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ingestion_jobs',
        help_text="User who requested this async ingestion job",
    )
    source = models.OneToOneField(DataSource, on_delete=models.CASCADE, related_name='ingestion_job', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    progress_percent = models.IntegerField(default=0, help_text="0-100 completion percentage")
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"IngestionJob {self.celery_task_id} - {self.status}"
    
    class Meta:
        db_table = 'ingestion_ingestionjob'
        verbose_name = 'Ingestion Job'
        verbose_name_plural = 'Ingestion Jobs'
        ordering = ['-created_at']
