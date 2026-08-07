"""
Migration for intelligent structural reconstruction models.
Note: pgvector extension must be installed separately via:
  python manage.py install_pgvector
Or manually: CREATE EXTENSION IF NOT EXISTS vector;
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('nettoyage', '0008_add_queued_status_choice'),
        ('ingestion', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        migrations.CreateModel(
            name='RawStructuralSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sheet_name', models.CharField(blank=True, default='', max_length=200)),
                ('structural_fingerprint', models.JSONField(help_text='Structural fingerprint: merged cells, blank zones, header candidates, column types')),
                ('confidence_score', models.DecimalField(decimal_places=4, default=0, help_text='Heuristic detection confidence 0-1', max_digits=5)),
                ('detected_subtables', models.JSONField(blank=True, default=list, help_text='List of detected sub-tables with their boundaries')),
                ('header_candidates', models.JSONField(blank=True, default=list, help_text='Candidate header row indices')),
                ('merged_cells', models.JSONField(blank=True, default=list, help_text='List of merged cell ranges')),
                ('blank_zones', models.JSONField(blank=True, default=list, help_text='Detected blank row/column separators')),
                ('column_types', models.JSONField(blank=True, default=dict, help_text='Per-column detected types')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='structural_snapshots', to='ingestion.datasource')),
            ],
            options={
                'verbose_name': 'Raw Structural Snapshot',
                'verbose_name_plural': 'Raw Structural Snapshots',
                'db_table': 'nettoyage_rawstructuralsnapshot',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CorrectionExample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('structural_before', models.JSONField(help_text='Structural fingerprint before correction')),
                ('structural_after', models.JSONField(help_text='Structural fingerprint after correction (human-validated)')),
                ('reconstruction_plan', models.JSONField(blank=True, default=dict, help_text='The reconstruction plan that was applied')),
                ('description', models.TextField(blank=True, default='', help_text='Human-readable description of the correction')),
                ('correction_type', models.CharField(blank=True, default='structural', help_text='Type: structural, header, merge, split, type_correction', max_length=50)),
                ('embedding', models.BinaryField(blank=True, help_text='pgvector embedding (all-MiniLM-L6-v2)', null=True)),
                ('is_validated', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='correction_examples', to=settings.AUTH_USER_MODEL)),
                ('snapshot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='corrections', to='nettoyage.rawstructuralsnapshot')),
                ('source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='correction_examples', to='ingestion.datasource')),
            ],
            options={
                'verbose_name': 'Correction Example',
                'verbose_name_plural': 'Correction Examples',
                'db_table': 'nettoyage_correctionexample',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CleaningRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method_used', models.CharField(choices=[('heuristic', 'Heuristic Only'), ('llm', 'LLM Assisted'), ('human_review', 'Human Review Required'), ('human_corrected', 'Human Corrected')], default='heuristic', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('detecting', 'Detecting Structure'), ('llm_calling', 'Calling LLM'), ('validating', 'Validating'), ('awaiting_review', 'Awaiting Human Review'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('confidence_score', models.DecimalField(decimal_places=4, default=0, help_text='Final confidence score after all steps', max_digits=5)),
                ('correction_examples_used', models.JSONField(blank=True, default=list, help_text='IDs of CorrectionExample used as few-shot examples')),
                ('llm_model', models.CharField(blank=True, default='', max_length=100)),
                ('llm_tokens_used', models.IntegerField(default=0)),
                ('llm_duration_ms', models.IntegerField(default=0)),
                ('reconstruction_plan', models.JSONField(blank=True, default=dict, help_text='Final reconstruction plan applied or proposed')),
                ('validation_gates_passed', models.BooleanField(default=True)),
                ('validation_gates_detail', models.JSONField(blank=True, default=dict, help_text='Per-gate results')),
                ('sheet_name', models.CharField(blank=True, default='', max_length=200)),
                ('rows_before', models.IntegerField(default=0)),
                ('rows_after', models.IntegerField(default=0)),
                ('columns_before', models.IntegerField(default=0)),
                ('columns_after', models.IntegerField(default=0)),
                ('subtables_detected', models.IntegerField(default=0)),
                ('duration_ms', models.IntegerField(default=0)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cleaning_runs', to=settings.AUTH_USER_MODEL)),
                ('snapshot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cleaning_runs', to='nettoyage.rawstructuralsnapshot')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cleaning_runs', to='ingestion.datasource')),
            ],
            options={
                'verbose_name': 'Cleaning Run',
                'verbose_name_plural': 'Cleaning Runs',
                'db_table': 'nettoyage_cleaningrun',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='rawstructuralsnapshot',
            index=models.Index(fields=['source', 'sheet_name'], name='nettoyage_ra_source__idx'),
        ),
        migrations.AddIndex(
            model_name='correctionexample',
            index=models.Index(fields=['correction_type'], name='nettoyage_co_correcti_idx'),
        ),
        migrations.AddIndex(
            model_name='correctionexample',
            index=models.Index(fields=['source'], name='nettoyage_co_source__idx'),
        ),
        migrations.AddIndex(
            model_name='cleaningrun',
            index=models.Index(fields=['source', 'status'], name='nettoyage_cl_source__idx'),
        ),
        migrations.AddIndex(
            model_name='cleaningrun',
            index=models.Index(fields=['method_used'], name='nettoyage_cl_method__idx'),
        ),
    ]
