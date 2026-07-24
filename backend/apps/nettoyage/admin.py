from django.contrib import admin

from apps.nettoyage.models import CleanedData, CleaningJob, CleaningPipeline, CleaningRule


@admin.register(CleaningRule)
class CleaningRuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'rule_type', 'priority', 'is_active', 'apply_to_all', 'created_by', 'created_at')
    list_filter = ('rule_type', 'is_active', 'apply_to_all', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')


@admin.register(CleaningPipeline)
class CleaningPipelineAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'source_type_scope', 'is_active', 'apply_to_all', 'created_by', 'created_at')
    list_filter = ('source_type_scope', 'is_active', 'apply_to_all')
    search_fields = ('name', 'description', 'created_by__username')
    filter_horizontal = ('rules',)


@admin.register(CleaningJob)
class CleaningJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'rule', 'status', 'rows_processed', 'rows_affected', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('source__name', 'rule__name', 'created_by__username')
    readonly_fields = ('started_at', 'completed_at', 'duration_ms', 'execution_context')


@admin.register(CleanedData)
class CleanedDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'original_data', 'quality_score', 'cleaned_at')
    list_filter = ('cleaned_at', 'is_validated')
    search_fields = ('job__source__name',)
