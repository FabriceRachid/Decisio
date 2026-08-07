"""
Management command to install the pgvector extension.
Run: python manage.py install_pgvector
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Install the pgvector extension for PostgreSQL'

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute('CREATE EXTENSION IF NOT EXISTS vector;')
            self.stdout.write(self.style.SUCCESS('pgvector extension installed successfully'))
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f'Could not install pgvector: {e}\n'
                    f'Make sure the pgvector extension is available on your PostgreSQL server.\n'
                    f'For Ubuntu/Debian: sudo apt install postgresql-16-pgvector\n'
                    f'For macOS: brew install pgvector\n'
                    f'For Windows: https://github.com/pgvector/pgvector#windows\n'
                    f'The system will use fallback similarity search without pgvector.'
                )
            )
