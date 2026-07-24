"""
Service layer for user notifications.
Handles creating notifications, progressing jobs, broadcasting updates.
"""

from django.contrib.auth.models import User
from apps.authentication.notification_models import UserNotification
from django.utils import timezone


def notify_user(
    user,
    notification_type,
    title,
    message,
    source_id=None,
    job_id=None,
    progress_percent=0,
    data=None,
    action_url=None
):
    """
    Create a notification for a user.
    Called when: upload completes, cleaning starts, cleaning progress, etc.
    
    Args:
        user: User instance
        notification_type: One of NOTIFICATION_TYPES
        title: Short title ("File Uploaded", "Cleaning Started", etc.)
        message: Detailed message
        source_id: DataSource ID for context
        job_id: CleaningJob ID for context
        progress_percent: 0-100 progress indicator
        data: Additional context dict
        action_url: Link to view results
    """
    notification = UserNotification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        source_id=source_id,
        job_id=job_id,
        progress_percent=progress_percent,
        data=data or {},
        action_url=action_url,
    )
    return notification


def notify_ingestion_completed(source_id, user_id, source_name, row_count):
    """Notify user that file upload completed"""
    user = User.objects.get(id=user_id)
    return notify_user(
        user=user,
        notification_type='ingestion_completed',
        title=f'✅ File Loaded: {source_name}',
        message=f'Your file has been successfully uploaded with {row_count} rows. Review the preview, then start cleaning when ready.',
        source_id=source_id,
        progress_percent=100,
        data={'row_count': row_count},
        action_url=f'/api/ingestion/sources/{source_id}/',
    )


def notify_cleaning_started(job_id, user_id, source_name):
    """Notify user that cleaning started"""
    user = User.objects.get(id=user_id)
    return notify_user(
        user=user,
        notification_type='cleaning_started',
        title=f'🔄 Cleaning Started: {source_name}',
        message='Your data is now being cleaned automatically. This typically takes a few seconds.',
        job_id=job_id,
        progress_percent=5,
        data={},
        action_url=f'/api/nettoyage/jobs/{job_id}/',
    )


def notify_cleaning_progress(job_id, user_id, progress_percent, rows_affected=0):
    """Update progress of cleaning job"""
    user = User.objects.get(id=user_id)
    return notify_user(
        user=user,
        notification_type='cleaning_progress',
        title='🔄 Cleaning in Progress',
        message=f'Cleaning is {progress_percent}% complete...',
        job_id=job_id,
        progress_percent=progress_percent,
        data={'rows_affected': rows_affected},
        action_url=f'/api/nettoyage/jobs/{job_id}/',
    )


def notify_cleaning_completed(job_id, user_id, rows_affected, quality_score):
    """Notify user that cleaning completed"""
    user = User.objects.get(id=user_id)
    return notify_user(
        user=user,
        notification_type='cleaning_completed',
        title='✅ Cleaning Completed',
        message=f'Data cleaning finished! {rows_affected} rows affected. Quality score: {quality_score:.1f}%',
        job_id=job_id,
        progress_percent=100,
        data={
            'rows_affected': rows_affected,
            'quality_score': quality_score,
        },
        action_url=f'/api/nettoyage/jobs/{job_id}/comparison/',
    )


def notify_cleaning_failed(job_id, user_id, error_message):
    """Notify user that cleaning failed"""
    user = User.objects.get(id=user_id)
    return notify_user(
        user=user,
        notification_type='cleaning_failed',
        title='❌ Cleaning Failed',
        message=f'An error occurred during cleaning: {error_message}',
        job_id=job_id,
        progress_percent=0,
        data={'error': error_message},
        action_url=f'/api/nettoyage/jobs/{job_id}/',
    )


def mark_notification_as_read(notification_id):
    """Mark a notification as read"""
    try:
        notification = UserNotification.objects.get(id=notification_id)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return notification
    except UserNotification.DoesNotExist:
        return None
