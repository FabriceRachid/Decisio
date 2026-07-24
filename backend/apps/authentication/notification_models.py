"""
User notification system for real-time updates on jobs.
Tracks ingestion completion, cleaning status, export progress.
"""

from django.db import models
from django.contrib.auth.models import User


class UserNotification(models.Model):
    """
    Real-time notifications sent to users about their jobs.
    Frontend polls or uses WebSocket to fetch these.
    """
    NOTIFICATION_TYPES = [
        ('ingestion_completed', 'File Upload Completed'),
        ('cleaning_started', 'Cleaning Started'),
        ('cleaning_progress', 'Cleaning Progress'),
        ('cleaning_completed', 'Cleaning Completed'),
        ('cleaning_failed', 'Cleaning Failed'),
        ('export_completed', 'Export Completed'),
        ('error', 'Error Occurred'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Links to related objects for context
    source_id = models.IntegerField(null=True, blank=True, help_text="DataSource ID (M1)")
    job_id = models.IntegerField(null=True, blank=True, help_text="CleaningJob ID (M2)")
    
    # Progress tracking
    progress_percent = models.IntegerField(default=0, help_text="0-100 progress")
    data = models.JSONField(default=dict, blank=True, help_text="Additional context (rows_affected, quality_score, etc.)")
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    action_url = models.CharField(max_length=500, blank=True, null=True, help_text="Link to view results")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'auth_usernotification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.user.username}"
