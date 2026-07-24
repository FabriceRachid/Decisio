"""
Django signals for ingestion workflow.
Sends non-blocking notifications after successful file upload.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
from apps.ingestion.models import DataSource
from apps.authentication.notification_service import notify_ingestion_completed


logger = logging.getLogger(__name__)


@receiver(post_save, sender=DataSource)
def trigger_auto_cleaning_on_completion(sender, instance, created, update_fields, **kwargs):
    """
    When a DataSource upload completes, notify user.
    
    Signal is fired:
    - ONLY when status changes to 'completed'
    - ONLY once (not on every update)
    - User is notified via notification system
    """
    
    if instance.status != 'completed':
        return

    # Run on completed creation, or explicit status updates to completed.
    if not created and (update_fields is None or 'status' not in update_fields):
        return

    # Keep ingestion durable: post-upload side effects must not break source creation.
    try:
        notify_ingestion_completed(
            source_id=instance.id,
            user_id=instance.uploaded_by.id,
            source_name=instance.name,
            row_count=instance.row_count or 0,
        )
    except Exception:
        logger.exception(
            'Failed to create ingestion notification for source_id=%s',
            instance.id,
        )

    # Cleaning is intentionally started manually by the user from the UI.
