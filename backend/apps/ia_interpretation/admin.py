from django.contrib import admin
from apps.ia_interpretation.models import AIAnalysis, AIInsight


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "analysis_type", "model_name", "status", "tokens_used", "processing_time_ms", "requested_by", "created_at")
    list_filter = ("status", "model_provider", "analysis_type")
    search_fields = ("prompt", "response")
    readonly_fields = ("created_at", "completed_at")


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ("id", "insight_type", "title", "severity", "urgency", "is_verified", "is_dismissed", "created_at")
    list_filter = ("insight_type", "severity", "urgency", "is_verified", "is_dismissed")
    search_fields = ("title", "description")
