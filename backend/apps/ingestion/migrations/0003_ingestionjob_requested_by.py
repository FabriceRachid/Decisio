from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingestion', '0002_ingestion_job'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ingestionjob',
            name='requested_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who requested this async ingestion job',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ingestion_jobs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
