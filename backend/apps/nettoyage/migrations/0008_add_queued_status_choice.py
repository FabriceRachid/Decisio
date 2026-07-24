from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nettoyage', '0007_seed_default_cleaning_rules'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cleaningjob',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('queued', 'Queued'),
                    ('running', 'Running'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
