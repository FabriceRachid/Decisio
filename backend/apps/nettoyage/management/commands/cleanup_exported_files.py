"""
Management command to clean up old exported cleaned data files.

Usage:
    python manage.py cleanup_exported_files
    python manage.py cleanup_exported_files --days=30
    python manage.py cleanup_exported_files --dry-run
    python manage.py cleanup_exported_files --days=7 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from pathlib import Path
from datetime import timedelta
import os

from apps.nettoyage.models import CleaningJob


class Command(BaseCommand):
    help = "Clean up exported cleaned data files older than N days."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete files older than this many days (default: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning up exported files older than {days} days "
                f"(before {cutoff_date.strftime('%Y-%m-%d')})"
            )
        )
        
        # Get export directory from settings
        from django.conf import settings
        export_dir = Path(settings.MEDIA_ROOT) / 'nettoyage_exports'
        
        if not export_dir.exists():
            self.stdout.write(
                self.style.WARNING(f"Export directory does not exist: {export_dir}")
            )
            return
        
        deleted_count = 0
        freed_space = 0
        
        # Find all exported files older than cutoff
        for file_path in export_dir.glob('**/*'):
            if not file_path.is_file():
                continue
            
            file_mod_time = timezone.datetime.fromtimestamp(
                file_path.stat().st_mtime,
                tz=timezone.utc
            )
            
            if file_mod_time < cutoff_date:
                file_size = file_path.stat().st_size
                freed_space += file_size
                
                if dry_run:
                    self.stdout.write(
                        f"  Would delete: {file_path.name} "
                        f"({file_size / 1024:.2f} KB, modified: {file_mod_time.strftime('%Y-%m-%d')})"
                    )
                else:
                    try:
                        file_path.unlink()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Deleted: {file_path.name} "
                                f"({file_size / 1024:.2f} KB)"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  Failed to delete {file_path.name}: {str(e)}"
                            )
                        )
                        continue
                
                deleted_count += 1
        
        # Summary
        freed_mb = freed_space / (1024 * 1024)
        summary = (
            f"\n{'[DRY RUN] ' if dry_run else ''}"
            f"Total files: {deleted_count} | Freed space: {freed_mb:.2f} MB"
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
        
        self.stdout.write("")
