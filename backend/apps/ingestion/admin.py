from django.contrib import admin

from apps.ingestion.models import DataSource, RawData, IngestionJob


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'source_type', 'status', 'uploaded_by', 'row_count', 'created_at')
    list_filter = ('source_type', 'status', 'created_at')
    search_fields = ('name', 'file_path', 'uploaded_by__username', 'checksum_md5')
    readonly_fields = ('checksum_md5', 'created_at', 'updated_at', 'processed_at')


@admin.register(RawData)
class RawDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'row_number', 'validation_status', 'ingested_at')
    list_filter = ('validation_status', 'ingested_at')
    search_fields = ('source__name',)
    readonly_fields = ('ingested_at',)


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'celery_task_id', 'status', 'progress_percent', 'source', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('celery_task_id', 'source__name')
    readonly_fields = ('celery_task_id', 'created_at', 'started_at', 'completed_at')

