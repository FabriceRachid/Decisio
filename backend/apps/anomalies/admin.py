from django.contrib import admin

from apps.anomalies.models import Anomaly, AnomalyAlert, AnomalyModel


@admin.register(AnomalyModel)
class AnomalyModelAdmin(admin.ModelAdmin):
    list_display = ("name", "algorithm", "training_source", "is_active", "inference_count", "created_at")
    list_filter = ("algorithm", "is_active")
    search_fields = ("name",)


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ("id", "data_source", "model", "severity", "anomaly_score", "status", "detected_at")
    list_filter = ("severity", "status", "model__algorithm")
    search_fields = ("data_source__name",)
    readonly_fields = ("row_ids", "affected_columns", "contribution_scores")


@admin.register(AnomalyAlert)
class AnomalyAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "anomaly", "alert_type", "recipient", "sent_at")
    list_filter = ("alert_type", "delivery_status")
