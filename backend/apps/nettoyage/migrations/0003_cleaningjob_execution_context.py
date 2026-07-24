from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nettoyage', '0002_cleaningpipeline'),
    ]

    operations = [
        migrations.AddField(
            model_name='cleaningjob',
            name='execution_context',
            field=models.JSONField(blank=True, default=dict, help_text='Resolved pipeline, rules, and quality gate used for execution'),
        ),
    ]
