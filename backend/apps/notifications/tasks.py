"""
Celery tasks for scheduled reporting and KPI alert delivery.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def send_kpi_alert_notification(self, alert_id: int, calculation_data: dict):
    """Send KPI alert notification via email/webhook."""
    try:
        from apps.kpi.models import KPIAlert
        from apps.notifications.services import NotificationService

        alert = KPIAlert.objects.select_related('kpi').get(id=alert_id)
        user = alert.kpi.owner or User.objects.first()

        if not user:
            logger.warning(f"No user found for alert {alert_id}")
            return

        notif_service = NotificationService(user)
        message = (
            f"Alerte KPI: {alert.alert_name}\n"
            f"KPI: {alert.kpi.name} ({alert.kpi.code})\n"
            f"Valeur: {calculation_data.get('value', 'N/A')}\n"
            f"Seuil: {alert.condition_type} {alert.threshold_value}\n"
        )

        sent = 0
        for channel in alert.notification_channels:
            if channel == 'email' and alert.recipients:
                notif_service.send_email_notification(
                    recipients=alert.recipients,
                    subject=f"⚠️ Alerte KPI: {alert.alert_name}",
                    message=message,
                )
                sent += 1
            elif channel == 'webhook' and alert.webhook_url:
                notif_service.send_webhook_notification(
                    url=alert.webhook_url,
                    payload={
                        'alert_name': alert.alert_name,
                        'kpi_code': alert.kpi.code,
                        'kpi_name': alert.kpi.name,
                        'value': calculation_data.get('value'),
                        'condition': alert.condition_type,
                        'threshold': alert.threshold_value,
                        'timestamp': timezone.now().isoformat(),
                    },
                )
                sent += 1

        logger.info(f"Alert {alert_id}: {sent} notifications sent")
        return {'sent': sent}

    except Exception as exc:
        logger.error(f"Failed to send alert notification {alert_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True)
def generate_scheduled_report(self, report_config_id: int):
    """Generate and send a scheduled report."""
    try:
        from apps.conflits.models import ScheduledJob
        from apps.kpi.models import KPIAlert
        from apps.notifications.services import NotificationService
        from apps.notifications.pdf_report import generate_kpi_report_pdf

        config = ScheduledJob.objects.get(id=report_config_id)

        if config.is_running:
            logger.info(f"Report {report_config_id} already running, skipping")
            return

        config.is_running = True
        config.save(update_fields=['is_running'])

        try:
            user = config.created_by or User.objects.first()
            if not user:
                logger.error("No user found for report")
                return

            # Gather KPI context from active alerts
            alerts = KPIAlert.objects.filter(is_active=True).select_related('kpi')[:20]
            kpi_context = []
            for alert in alerts:
                kpi_context.append({
                    'name': alert.kpi.name if alert.kpi else 'N/A',
                    'measure': alert.kpi.code if alert.kpi else 'N/A',
                    'value': alert.threshold_value or 0,
                    'status': alert.condition_type or 'unknown',
                })

            # Generate PDF
            pdf_bytes = generate_kpi_report_pdf(
                user=user,
                kpi_context=kpi_context,
                title=f"Rapport automatique - {timezone.now().strftime('%d/%m/%Y')}",
            )

            if pdf_bytes:
                # Save to file
                import os
                from django.conf import settings
                report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
                os.makedirs(report_dir, exist_ok=True)
                filename = f"report_{user.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                filepath = os.path.join(report_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(pdf_bytes)

                # Send email notification
                notif_service = NotificationService(user)
                notif_service.send_email_notification(
                    recipients=[user.email] if user.email else [],
                    subject=f"📊 Rapport DécisioBI - {timezone.now().strftime('%d/%m/%Y')}",
                    message=f"Votre rapport automatique est prêt. Fichier: {filename}",
                )

                logger.info(f"Report generated: {filepath}")

        finally:
            config.is_running = False
            config.last_run_at = timezone.now()
            if config.interval_minutes:
                config.next_run_at = timezone.now() + timedelta(minutes=config.interval_minutes)
            config.save(update_fields=['is_running', 'last_run_at', 'next_run_at'])

    except Exception as exc:
        logger.error(f"Failed to generate report {report_config_id}: {exc}")
        raise


@shared_task
def check_and_run_scheduled_reports():
    """Periodic task: check for reports that need to run."""
    try:
        from apps.conflits.models import ScheduledJob

        now = timezone.now()
        due_jobs = ScheduledJob.objects.filter(
            job_type='report_generation',
            is_active=True,
            is_running=False,
        ).filter(
            next_run_at__lte=now
        ) | ScheduledJob.objects.filter(
            job_type='report_generation',
            is_active=True,
            is_running=False,
            next_run_at__isnull=True,
        )

        for job in due_jobs:
            generate_scheduled_report.delay(job.id)
            logger.info(f"Scheduled report triggered: {job.id}")

    except Exception as exc:
        logger.error(f"Failed to check scheduled reports: {exc}")
