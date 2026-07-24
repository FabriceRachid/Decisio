from django.db import models
from django.contrib.auth.models import User


class AnomalyModel(models.Model):
    """
    Machine learning models for anomaly detection.
    Stores model configuration, training parameters, and performance metrics.
    """
    ALGORITHM_CHOICES = [
        ('isolation_forest', 'Isolation Forest'),
        ('lof', 'Local Outlier Factor'),
        ('one_class_svm', 'One-Class SVM'),
        ('autoencoder', 'Autoencoder'),
        ('prophet', 'Prophet'),
        ('arima', 'ARIMA'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    algorithm = models.CharField(max_length=50, choices=ALGORITHM_CHOICES)
    algorithm_version = models.CharField(max_length=20, blank=True, null=True)
    
    # Training configuration
    training_parameters = models.JSONField(help_text="Hyperparameters")
    training_source = models.ForeignKey('ingestion.DataSource', on_delete=models.SET_NULL, null=True, blank=True)
    training_features = models.JSONField(help_text="Which columns used as features")
    training_start_date = models.DateField(null=True, blank=True)
    training_end_date = models.DateField(null=True, blank=True)
    training_samples = models.IntegerField(null=True, blank=True, help_text="How many rows trained on")
    
    # Model performance
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    precision = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    recall = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    evaluation_metrics = models.JSONField(default=dict, blank=True)
    
    # Model artifacts
    model_file_path = models.CharField(max_length=500, blank=True, null=True)
    model_checksum = models.CharField(max_length=64, blank=True, null=True, help_text="Verify integrity")
    
    # Deployment
    is_active = models.BooleanField(default=False)
    deployed_at = models.DateTimeField(null=True, blank=True)
    deployed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deployed_models')
    
    # Monitoring
    last_inference_at = models.DateTimeField(null=True, blank=True)
    inference_count = models.IntegerField(default=0)
    drift_detected = models.BooleanField(default=False, help_text="Model drift?")
    retrain_recommended = models.BooleanField(default=False)
    
    # Advanced features
    parent_model = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='model_versions')
    experiment_id = models.CharField(max_length=100, blank=True, null=True, help_text="ML experiment tracking")
    feature_importance = models.JSONField(default=dict, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_models')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_algorithm_display()})"
    
    class Meta:
        db_table = 'anomalies_anomalymodel'
        verbose_name = 'Anomaly Model'
        verbose_name_plural = 'Anomaly Models'
        unique_together = ['name', 'algorithm_version']
        ordering = ['-is_active', '-created_at']


class Anomaly(models.Model):
    """
    Detected anomalies in datasets.
    Tracks unusual patterns, outliers, and potential issues.
    """
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    ANOMALY_TYPE_CHOICES = [
        ('point', 'Point Anomaly'),
        ('contextual', 'Contextual Anomaly'),
        ('collective', 'Collective Anomaly'),
    ]
    
    BUSINESS_IMPACT_CHOICES = [
        ('financial', 'Financial Impact'),
        ('operational', 'Operational Impact'),
        ('reputational', 'Reputational Risk'),
        ('compliance', 'Compliance Issue'),
        (None, 'None'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'New'),
        ('investigating', 'Investigating'),
        ('confirmed', 'Confirmed'),
        ('false_positive', 'False Positive'),
        ('resolved', 'Resolved'),
    ]
    
    model = models.ForeignKey(AnomalyModel, on_delete=models.CASCADE, related_name='detected_anomalies')
    data_source = models.ForeignKey('ingestion.DataSource', on_delete=models.CASCADE)
    row_ids = models.JSONField(help_text="Which rows are anomalous")
    
    # Anomaly scores
    anomaly_score = models.DecimalField(max_digits=5, decimal_places=4)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Explanation
    affected_columns = models.JSONField()
    contribution_scores = models.JSONField(default=dict, help_text="How much each column contributed")
    explanation = models.TextField(help_text="Human-readable explanation")
    
    # Pattern detection
    anomaly_type = models.CharField(max_length=50, choices=ANOMALY_TYPE_CHOICES, blank=True, null=True)
    pattern_description = models.TextField(blank=True, null=True)
    
    # Impact assessment
    business_impact = models.CharField(max_length=50, choices=BUSINESS_IMPACT_CHOICES, blank=True, null=True)
    estimated_impact_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    # Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.IntegerField(default=5)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_anomalies')
    due_date = models.DateTimeField(null=True, blank=True)
    
    # Review
    is_reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_anomalies')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, null=True)
    
    # Advanced features
    similar_anomalies = models.JSONField(default=list, blank=True, help_text="Links to historical similar cases")
    auto_resolved = models.BooleanField(default=False, help_text="System auto-resolved?")
    resolution_method = models.CharField(max_length=50, blank=True, null=True)
    
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Anomaly in {self.data_source.name} (Score: {self.anomaly_score})"
    
    class Meta:
        db_table = 'anomalies_anomaly'
        verbose_name = 'Anomaly'
        verbose_name_plural = 'Anomalies'
        ordering = ['-severity', '-anomaly_score', '-detected_at']
        indexes = [
            models.Index(fields=['model', 'detected_at']),
            models.Index(fields=['severity']),
            models.Index(fields=['status']),
        ]


class AnomalyAlert(models.Model):
    """
    Notifications for detected anomalies.
    Manages multi-channel alert delivery and tracking.
    """
    ALERT_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('slack', 'Slack'),
        ('teams', 'Microsoft Teams'),
        ('webhook', 'Webhook'),
        ('push_notification', 'Push Notification'),
    ]
    
    DELIVERY_STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('bounced', 'Bounced'),
    ]
    
    anomaly = models.ForeignKey(Anomaly, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    recipient = models.CharField(max_length=500, help_text="Email, phone, webhook URL, channel ID")
    
    # Message
    subject = models.CharField(max_length=500, blank=True, null=True)
    message_body = models.TextField()
    include_details = models.BooleanField(default=True)
    include_chart = models.BooleanField(default=True)
    
    # Delivery
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    
    # Tracking
    opened_at = models.DateTimeField(null=True, blank=True, help_text="Email opened?")
    clicked_at = models.DateTimeField(null=True, blank=True, help_text="Link clicked?")
    response_action = models.TextField(blank=True, null=True)
    
    # Advanced features
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_anomaly_alerts')
    escalated_to = models.CharField(max_length=500, blank=True, null=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text="Delayed sending?")
    
    def __str__(self):
        return f"{self.get_alert_type_display()} for Anomaly {self.anomaly.id}"
    
    class Meta:
        db_table = 'anomalies_anomalyalert'
        verbose_name = 'Anomaly Alert'
        verbose_name_plural = 'Anomaly Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['anomaly', 'is_sent']),
        ]
