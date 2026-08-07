"""
Celery tasks for nettoyage (cleaning) module
Handles async cleaning operations without blocking the request
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import logging

from apps.nettoyage.models import CleaningJob
from apps.nettoyage.services import apply_cleaning, CleaningError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def apply_cleaning_async(
    self,
    job_id,
    source_id,
    user_id,
    pipeline_id,
    rule_ids,
    include_all_auto_rules,
    quality_gate,
    decision_overrides=None,
):
    """
    Async task to apply cleaning rules without blocking the API request.
    Returns 202 Accepted immediately, processes in background.
    
    Args:
        job_id: CleaningJob ID to track progress
        source_id: DataSource ID to clean
        user_id: User ID who requested cleaning
        pipeline_id: Optional pipeline ID
        rule_ids: List of rule IDs to apply
        include_all_auto_rules: Boolean to include auto-apply rules
        quality_gate: Quality thresholds dict
    """
    from django.contrib.auth.models import User
    from apps.ingestion.models import DataSource
    
    job = CleaningJob.objects.get(id=job_id)
    
    try:
        job.status = 'running'
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])
        
        user = User.objects.get(id=user_id)
        source = DataSource.objects.get(id=source_id)
        
        # Apply cleaning (synchronous logic, but in background)
        result = apply_cleaning(
            source=source,
            user=user,
            pipeline_id=pipeline_id,
            rule_ids=rule_ids,
            include_all_auto_rules=include_all_auto_rules,
            quality_gate=quality_gate,
            decision_overrides=decision_overrides or [],
        )
        
        # M3: Detect conflicts in cleaned data
        try:
            from apps.conflits.services import ConflictDetectionService
            
            conflict_service = ConflictDetectionService(user)
            conflict_result = conflict_service.detect_conflicts_in_source(
                source=source,
                check_types=[
                    'DUPLICATE_RECORDS',
                    'MISSING_VALUES',
                    'DATA_TYPE_MISMATCH',
                    'FORMAT_INCONSISTENCY'
                ]
            )
            
            if conflict_result['total_conflicts'] > 0:
                logger.warning(
                    f"Detected {conflict_result['total_conflicts']} conflicts in source {source.id} "
                    f"after cleaning: {conflict_result['summary']}"
                )
        except Exception as e:
            logger.warning(f"Could not run conflict detection after cleaning: {str(e)}")
        
        # Update job as completed
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.progress_percent = 100
        job.rows_processed = result['summary']['rows_processed']
        job.rows_affected = result['summary']['rows_affected']
        job.rows_skipped = result['summary']['rows_skipped']
        job.rows_failed = result['summary']['rows_failed']
        job.execution_context = {
            **(job.execution_context or {}),
            'result_job_id': result['job_id'],
        }
        job.save(
            update_fields=[
                'status',
                'completed_at',
                'progress_percent',
                'rows_processed',
                'rows_affected',
                'rows_skipped',
                'rows_failed',
                'execution_context',
            ]
        )
        
        logger.info(f"Cleaning job {job_id} completed successfully")
        return {'status': 'success', 'job_id': job_id, 'rows_affected': result['summary']['rows_affected']}
        
    except CleaningError as e:
        logger.error(f"Cleaning job {job_id} failed with validation error: {str(e)}")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        raise
        
    except Exception as e:
        logger.exception(f"Cleaning job {job_id} failed with unexpected error")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        
        # Retry with exponential backoff
        retry_delay = 2 ** self.request.retries
        raise self.retry(exc=e, countdown=retry_delay)


@shared_task
def export_cleaned_data_async(job_id, format='csv', include_metadata=False, include_validation_status=False):
    """
    Export cleaned data from a cleaning job to file.
    Runs asynchronously to avoid blocking.
    
    Args:
        job_id: CleaningJob ID to export
        format: 'csv', 'excel', or 'json'
    
    Returns:
        Path to exported file
    """
    import pandas as pd
    from pathlib import Path
    
    try:
        job = CleaningJob.objects.prefetch_related('cleaned_results').get(id=job_id)
        
        # Build dataframe from cleaned data
        records = []
        for item in job.cleaned_results.all():
            record = dict(item.data)
            if include_metadata:
                record['changes_made'] = item.changes_made
                record['quality_score'] = float(item.quality_score or 0)
            if include_validation_status:
                record['is_validated'] = item.is_validated
                record['validation_notes'] = item.validation_notes
            records.append(record)
        
        if not records:
            logger.warning(f"No cleaned data to export for job {job_id}")
            return {'status': 'warning', 'message': 'No cleaned data found'}
        
        df = pd.DataFrame(records)
        
        # Determine export path
        export_dir = Path(settings.MEDIA_ROOT) / 'nettoyage_exports'
        export_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"cleaned_job_{job_id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        if format.lower() == 'csv':
            filepath = export_dir / f"{filename}.csv"
            df.to_csv(filepath, index=False)
        elif format.lower() == 'excel':
            filepath = export_dir / f"{filename}.xlsx"
            df.to_excel(filepath, index=False)
        elif format.lower() == 'json':
            filepath = export_dir / f"{filename}.json"
            df.to_json(filepath, orient='records', indent=2)
        else:
            return {'status': 'error', 'message': f'Unsupported format: {format}'}
        
        # Save export path to job
        relative_path = str(filepath.relative_to(settings.MEDIA_ROOT))
        job.export_path = relative_path
        job.save(update_fields=['export_path'])
        job.cleaned_results.update(export_path=relative_path)
        
        logger.info(f"Exported cleaned data from job {job_id} to {filepath}")
        return {
            'status': 'success',
            'job_id': job_id,
            'filepath': relative_path,
            'row_count': len(df),
            'column_count': len(df.columns),
        }
    except Exception as e:
        logger.exception(f"Export failed for job {job_id}")
        return {
            'status': 'error',
            'job_id': job_id,
            'message': str(e),
        }


@shared_task
def auto_clean_after_ingestion(source_id, user_id):
    """
    Auto-clean data source immediately after successful upload.
    Uses default pipeline if available, sends notifications at each step.
    
    This is triggered automatically by ingestion signal when upload completes.
    User sees progressive notifications:
    1. ✅ File loaded
    2. 🔄 Cleaning started
    3. 🔄 Cleaning progress (50%, 75%, etc.)
    4. ✅ Cleaning completed with results
    
    Args:
        source_id: DataSource ID that was just uploaded
        user_id: User who uploaded the file
    """
    from django.contrib.auth.models import User
    from apps.ingestion.models import DataSource
    from apps.nettoyage.models import CleaningPipeline, CleaningJob
    from apps.nettoyage.services import apply_cleaning
    from apps.authentication.notification_service import (
        notify_cleaning_started,
        notify_cleaning_progress,
        notify_cleaning_completed,
        notify_cleaning_failed,
    )
    
    try:
        source = DataSource.objects.get(id=source_id)
        user = User.objects.get(id=user_id)
        
        # Find default pipeline for this source type
        default_pipeline = CleaningPipeline.objects.filter(
            source_type_scope=source.source_type,
            is_active=True,
            name__icontains='default'
        ).first()
        
        if not default_pipeline:
            logger.info(f"No default pipeline found for source {source_id} type {source.source_type}")
            return {
                'status': 'skipped',
                'message': 'No default pipeline for this file type',
            }
        
        execution_context = {
            'pipeline_id': default_pipeline.id,
            'rule_ids': list(default_pipeline.rules.values_list('id', flat=True)),
            'include_all_auto_rules': False,
            'quality_gate': default_pipeline.quality_gate or {},
        }

        # Create cleaning job
        job = CleaningJob.objects.create(
            source=source,
            status='queued',
            created_by=user,
            total_rows=source.row_count or 0,
            is_auto_triggered=True,  # Track this was automatic
            execution_context=execution_context,
        )
        
        logger.info(f"Starting auto-clean for source {source_id} with job {job.id}")
        
        # STEP 1: Notify cleaning started
        notify_cleaning_started(
            job_id=job.id,
            user_id=user_id,
            source_name=source.name,
        )
        
        # STEP 2: Apply the default pipeline
        job.status = 'running'
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])
        
        # Progress update at 25%
        notify_cleaning_progress(job.id, user_id, 25)
        
        result = apply_cleaning(
            source=source,
            user=user,
            pipeline_id=default_pipeline.id,
            rule_ids=[],
            include_all_auto_rules=False,
            quality_gate=default_pipeline.quality_gate or {},
        )
        
        # Progress update at 75%
        notify_cleaning_progress(
            job.id, 
            user_id, 
            75,
            rows_affected=result['summary']['rows_affected']
        )
        
        # STEP 3: Mark job as completed
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.progress_percent = 100
        job.rows_processed = result['summary']['rows_processed']
        job.rows_affected = result['summary']['rows_affected']
        job.rows_skipped = result['summary']['rows_skipped']
        job.rows_failed = result['summary']['rows_failed']
        job.execution_context = {
            **execution_context,
            'result_job_id': result['job_id'],
        }
        job.save(
            update_fields=[
                'status',
                'completed_at',
                'progress_percent',
                'rows_processed',
                'rows_affected',
                'rows_skipped',
                'rows_failed',
                'execution_context',
            ]
        )
        
        # Calculate average quality score
        avg_quality = result['summary'].get('average_quality_score', 95)
        
        # STEP 4: Notify completion with results
        notify_cleaning_completed(
            job_id=job.id,
            user_id=user_id,
            rows_affected=result['summary']['rows_affected'],
            quality_score=avg_quality,
        )
        
        logger.info(f"Auto-clean completed for source {source_id}, job {job.id}")
        return {
            'status': 'success',
            'job_id': job.id,
            'source_id': source_id,
            'rows_affected': result['summary']['rows_affected'],
        }
        
    except DataSource.DoesNotExist:
        logger.error(f"DataSource {source_id} not found for auto-cleaning")
        notify_cleaning_failed(None, user_id, 'DataSource not found')
        return {'status': 'error', 'message': f'DataSource {source_id} not found'}
        
    except Exception as e:
        logger.exception(f"Auto-clean failed for source {source_id}")
        # Notify user of failure but don't fail the upload
        notify_cleaning_failed(
            job.id if 'job' in locals() else None,
            user_id,
            str(e)
        )
        return {
            'status': 'error',
            'message': str(e),
        }


@shared_task(bind=True, max_retries=2)
def run_structural_detection_async(
    self,
    source_id,
    user_id,
    sheet_name='',
    force_llm=False,
    validation_config=None,
):
    """
    Async task for intelligent structural reconstruction.
    Runs the full pipeline: heuristic → LLM (if needed) → validation gates.
    """
    import os
    from django.contrib.auth.models import User
    from apps.ingestion.models import DataSource
    from apps.nettoyage.structure_models import CleaningRun, RawStructuralSnapshot
    from apps.nettoyage.structure_detection.orchestrator import StructureDetectionOrchestrator

    run = None
    try:
        source = DataSource.objects.get(id=source_id)
        user = User.objects.get(id=user_id)

        run = CleaningRun.objects.create(
            source=source,
            status='detecting',
            sheet_name=sheet_name,
            created_by=user,
        )

        file_path = None
        if source.file_path and os.path.exists(source.file_path):
            file_path = source.file_path
        elif source.file and hasattr(source.file, 'path') and os.path.exists(source.file.path):
            file_path = source.file.path

        if not file_path:
            run.status = 'failed'
            run.error_message = 'Fichier source introuvable'
            run.save(update_fields=['status', 'error_message'])
            return {'status': 'error', 'message': 'File not found'}

        orchestrator = StructureDetectionOrchestrator(validation_config or {})
        result = orchestrator.detect_and_reconstruct(
            file_path=file_path,
            sheet_name=sheet_name or None,
            source_id=source_id,
            force_llm=force_llm,
        )

        fp = result.get('structural_fingerprint', {})
        snapshot = RawStructuralSnapshot.objects.create(
            source=source,
            sheet_name=sheet_name,
            structural_fingerprint=fp,
            confidence_score=result.get('confidence_score', 0),
            detected_subtables=result.get('reconstruction_plan', {}).get('subtables', []),
            header_candidates=fp.get('header_candidates', []),
            merged_cells=fp.get('merged_cells', []),
            blank_zones=fp.get('blank_rows', []),
            column_types=fp.get('column_types', {}),
        )

        run.snapshot = snapshot
        run.method_used = result.get('method_used', 'heuristic')
        run.status = result.get('status', 'completed')
        run.confidence_score = result.get('confidence_score', 0)
        run.correction_examples_used = result.get('correction_examples_used', [])
        run.llm_model = result.get('llm_model', '')
        run.llm_tokens_used = result.get('llm_tokens_used', 0)
        run.llm_duration_ms = result.get('llm_duration_ms', 0)
        run.reconstruction_plan = result.get('reconstruction_plan') or {}
        run.validation_gates_passed = result.get('validation_report', {}).get('all_passed', True)
        run.validation_gates_detail = result.get('validation_report', {})
        run.rows_before = fp.get('total_rows', 0)
        run.columns_before = fp.get('total_cols', 0)
        run.subtables_detected = len(result.get('reconstruction_plan', {}).get('subtables', []))
        run.duration_ms = result.get('duration_ms', 0)
        run.error_message = result.get('error', '')
        run.completed_at = timezone.now()
        run.save()

        logger.info(f"Structural detection completed for source {source_id}, run {run.id}")
        return {
            'status': 'success',
            'run_id': run.id,
            'method': run.method_used,
            'confidence': float(run.confidence_score),
        }

    except Exception as e:
        logger.exception(f"Structural detection failed for source {source_id}")
        if run:
            run.status = 'failed'
            run.error_message = str(e)
            run.completed_at = timezone.now()
            run.save(update_fields=['status', 'error_message', 'completed_at'])
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
