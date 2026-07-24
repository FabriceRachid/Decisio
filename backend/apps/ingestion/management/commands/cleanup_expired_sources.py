"""
Django management command to cleanup expired data sources.
Can be run manually or scheduled with Celery Beat.

Usage:
    python manage.py cleanup_expired_sources
    python manage.py cleanup_expired_sources --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from pathlib import Path
import logging

from apps.ingestion.models import DataSource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete data sources that have exceeded their retention period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Override retention_days setting and delete sources older than N days',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        override_days = options['days']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('Starting cleanup of expired data sources...'))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: No data will be deleted'))
        
        now = timezone.now()
        
        # Build query for expired sources
        if override_days:
            # Delete sources older than N days
            cutoff_date = now - timedelta(days=override_days)
            expired_sources = DataSource.objects.filter(
                is_archived=False,
                created_at__lte=cutoff_date,
            )
            self.stdout.write(f"Finding sources created before {cutoff_date}...")
        else:
            # Delete sources based on individual retention_days
            from django.db.models import F
            expired_sources = DataSource.objects.filter(
                is_archived=False,
            ).exclude(
                retention_days__isnull=True,
            )
            # Filter using Python since we need to compare dates with retention_days
            expired_sources = [
                s for s in expired_sources
                if s.created_at + timedelta(days=s.retention_days) <= now
            ]
            expired_sources = DataSource.objects.filter(
                id__in=[s.id for s in expired_sources]
            )
        
        count = expired_sources.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No expired sources found.'))
            return
        
        self.stdout.write(f"Found {count} expired source(s) to delete")
        
        # Show summary
        for source in expired_sources[:5]:
            created_str = source.created_at.strftime('%Y-%m-%d %H:%M:%S')
            retention_str = f"(retention: {source.retention_days} days)" if source.retention_days else ""
            self.stdout.write(f"  - {source.name} (created: {created_str}) {retention_str}")
        
        if count > 5:
            self.stdout.write(f"  ... and {count - 5} more")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would delete {count} sources and their files'))
            return
        
        # Confirm deletion
        if not force:
            confirm = input(f'\nDelete {count} source(s) and their files? [y/N]: ')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Cancelled.'))
                return
        
        # Delete sources
        deleted_count = 0
        failed_count = 0
        
        for source in expired_sources:
            try:
                # Delete physical file
                if source.file_path:
                    file_path = Path(settings.MEDIA_ROOT) / source.file_path
                    if file_path.exists():
                        file_path.unlink()
                        self.stdout.write(f"Deleted file: {source.file_path}")
                
                # Delete source record (cascades to RawData)
                source_name = source.name
                source.delete()
                deleted_count += 1
                self.stdout.write(self.style.SUCCESS(f"Deleted source: {source_name}"))
                
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Error deleting source {source.id} ({source.name}): {str(e)}")
                )
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✓ Cleanup completed'))
        self.stdout.write(f'  Deleted: {deleted_count} sources')
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(f'  Failed: {failed_count} sources'))
