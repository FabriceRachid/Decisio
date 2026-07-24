from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('ingestion_completed', 'File Upload Completed'), ('cleaning_started', 'Cleaning Started'), ('cleaning_progress', 'Cleaning Progress'), ('cleaning_completed', 'Cleaning Completed'), ('cleaning_failed', 'Cleaning Failed'), ('export_completed', 'Export Completed'), ('error', 'Error Occurred')], max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('source_id', models.IntegerField(blank=True, help_text='DataSource ID (M1)', null=True)),
                ('job_id', models.IntegerField(blank=True, help_text='CleaningJob ID (M2)', null=True)),
                ('progress_percent', models.IntegerField(default=0, help_text='0-100 progress')),
                ('data', models.JSONField(blank=True, default=dict, help_text='Additional context (rows_affected, quality_score, etc.)')),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('action_url', models.CharField(blank=True, help_text='Link to view results', max_length=500, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'auth_usernotification',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='usernotification',
            index=models.Index(fields=['user', '-created_at'], name='auth_userno_user_id_8f52ec_idx'),
        ),
        migrations.AddIndex(
            model_name='usernotification',
            index=models.Index(fields=['user', 'is_read'], name='auth_userno_user_id_7eb61c_idx'),
        ),
    ]
