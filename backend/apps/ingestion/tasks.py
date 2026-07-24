"""
Celery tasks for ingestion module
Handles async file processing, validation, and cleanup
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db import models
from pathlib import Path
import logging

from apps.ingestion.models import DataSource, RawData, IngestionJob
from apps.ingestion.services import (
    ingest_uploaded_file,
    IngestionError,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_ingestion_async(
    self,
    job_id,
    user_id,
    file_path,
    source_name,
    source_type,
    delimiter,
    encoding,
    has_header,
    description,
    tags,
    retention_days,
    required_columns,
    key_columns,
    strict_validation,
    template_id,
    column_mapping,
):
    """
    Async task to process file ingestion without blocking the API request.
    
    Args:
        job_id: IngestionJob ID
        user_id: User ID who uploaded the file
        file_path: Path to uploaded file
        ... other ingestion parameters
    """
    from django.contrib.auth.models import User
    
    job = IngestionJob.objects.get(id=job_id)
    
    try:
        job.status = 'processing'
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])
        
        user = User.objects.get(id=user_id)
        
        # Read file from disk
        file_full_path = Path(settings.MEDIA_ROOT) / file_path
        if not file_full_path.exists():
            raise IngestionError(f"File not found: {file_path}")
        
        with open(file_full_path, 'rb') as f:
            file_bytes = f.read()
        
        # Create a simple file-like object
        class FileWrapper:
            def __init__(self, name, content):
                self.name = name
                self.content = content
            
            def read(self):
                return self.content
        
        uploaded_file = FileWrapper(source_name, file_bytes)
        
        # Process ingestion (same logic as synchronous)
        from apps.ingestion.services import (
            _analyze_file_bytes,
            _build_preview_response,
        )
        
        analysis = _analyze_file_bytes(
            user=user,
            filename=uploaded_file.name,
            file_bytes=file_bytes,
            source_type=source_type,
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            required_columns=required_columns,
            key_columns=key_columns,
            template_id=template_id,
            column_mapping=column_mapping,
        )
        
        # Check strict validation
        if strict_validation and any(error['severity'] == 'error' for error in analysis['validation_errors']):
            raise IngestionError('Strict validation failed. Resolve reported errors before importing.')
        
        # Create DataSource record
        source = DataSource.objects.create(
            name=source_name,
            source_type=source_type,
            file_path=str(file_path),
            file_size_bytes=analysis['file_size_bytes'],
            row_count=analysis['row_count'],
            column_count=analysis['column_count'],
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            uploaded_by=user,
            status='completed' if not any(error['severity'] == 'error' for error in analysis['validation_errors']) else 'failed',
            metadata=analysis['metadata'],
            validation_errors=analysis['validation_errors'],
            checksum_md5=analysis['checksum_md5'],
            retention_days=retention_days,
            description=description,
            tags=tags,
            lineage_info={
                'source_filename': uploaded_file.name,
                'ingestion_mode': 'async_upload',
            },
            processed_at=timezone.now(),
        )
        
        # Ingest raw data rows
        from apps.ingestion.services import _hash_row
        
        raw_rows = []
        start_row_number = 2 if has_header else 1
        row_issues = {item['row_number']: item for item in analysis['row_validation_results']}
        
        for offset, row in enumerate(analysis['rows']):
            row_number = start_row_number + offset
            row_result = row_issues.get(row_number, {'status': 'valid', 'messages': []})
            raw_rows.append(
                RawData(
                    source=source,
                    row_number=row_number,
                    data=row,
                    data_hash=_hash_row(row),
                    validation_status=row_result['status'],
                    validation_messages=row_result['messages'],
                    is_sample=offset < 10,
                )
            )
            
            # Update progress
            progress = int((offset + 1) / len(analysis['rows']) * 100)
            job.progress_percent = progress
            job.save(update_fields=['progress_percent'])
        
        # Bulk insert raw data
        RawData.objects.bulk_create(raw_rows, batch_size=1000)
        
        # Update job as completed
        job.status = 'completed'
        job.source = source
        job.completed_at = timezone.now()
        job.progress_percent = 100
        job.save()
        
        logger.info(f"Ingestion job {job_id} completed successfully. Source ID: {source.id}")
        return {'status': 'success', 'source_id': source.id, 'row_count': source.row_count}
        
    except IngestionError as e:
        logger.error(f"Ingestion job {job_id} failed with validation error: {str(e)}")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        raise
        
    except Exception as e:
        logger.exception(f"Ingestion job {job_id} failed with unexpected error")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        
        # Retry with exponential backoff
        retry_delay = 2 ** self.request.retries
        raise self.retry(exc=e, countdown=retry_delay)


@shared_task
def cleanup_expired_sources():
    """
    Delete data source files and records that have exceeded retention period.
    Runs daily via Celery Beat.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("Starting cleanup of expired data sources")
    
    # Find all sources that have exceeded retention period
    now = timezone.now()
    expired_sources = []
    for source in DataSource.objects.filter(is_archived=False).iterator():
        expiration_time = source.created_at + timedelta(days=source.retention_days)
        if expiration_time <= now:
            expired_sources.append(source)

    deleted_count = 0
    for source in expired_sources:
        try:
            # Delete physical file
            if source.file_path:
                file_path = Path(settings.MEDIA_ROOT) / source.file_path
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted file: {source.file_path}")
            
            # Delete source record (cascades to RawData)
            source_name = source.name
            source.delete()
            deleted_count += 1
            logger.info(f"Deleted source: {source_name}")
            
        except Exception as e:
            logger.error(f"Error deleting source {source.id}: {str(e)}")
    
    logger.info(f"Cleanup completed. Deleted {deleted_count} expired sources")
    return {'deleted_count': deleted_count}


@shared_task
def reconcile_sources_async(source_id_1, source_id_2):
    """
    Compare two data sources and identify differences.
    Used for reconciliation between uploads.
    """
    try:
        source1 = DataSource.objects.get(id=source_id_1)
        source2 = DataSource.objects.get(id=source_id_2)
        
        rows1 = set(RawData.objects.filter(source=source1).values_list('data_hash', flat=True))
        rows2 = set(RawData.objects.filter(source=source2).values_list('data_hash', flat=True))
        
        added = rows2 - rows1
        deleted = rows1 - rows2
        unchanged = rows1 & rows2
        
        result = {
            'source1_id': source_id_1,
            'source2_id': source_id_2,
            'added_count': len(added),
            'deleted_count': len(deleted),
            'unchanged_count': len(unchanged),
            'added_sample': list(added)[:10],
            'deleted_sample': list(deleted)[:10],
        }
        
        logger.info(f"Reconciliation completed: {result}")
        return result
        
    except DataSource.DoesNotExist as e:
        logger.error(f"Reconciliation failed: Source not found - {str(e)}")
        raise
