# Generated migration for IngestionJob model
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingestion', '0001_initial'),  # Adjust to match your latest migration
    ]

    operations = [
        migrations.CreateModel(
            name='IngestionJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('celery_task_id', models.CharField(help_text='Celery task ID for tracking', max_length=200, unique=True)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='queued', max_length=20)),
                ('progress_percent', models.IntegerField(default=0, help_text='0-100 completion percentage')),
                ('error_message', models.TextField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ingestion_job', to='ingestion.datasource')),
            ],
            options={
                'verbose_name': 'Ingestion Job',
                'verbose_name_plural': 'Ingestion Jobs',
                'db_table': 'ingestion_ingestionjob',
                'ordering': ['-created_at'],
            },
        ),
    ]
