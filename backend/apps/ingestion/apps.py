from django.apps import AppConfig


class IngestionConfig(AppConfig):
    name = 'apps.ingestion'

    def ready(self):
        """Register signals when app is ready"""
        import apps.ingestion.signals  # noqa
