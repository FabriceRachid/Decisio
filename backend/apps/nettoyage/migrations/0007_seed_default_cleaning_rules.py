from django.db import migrations


SYSTEM_USERNAME = 'system_cleaning'
DEFAULT_PIPELINE_NAME = 'Pipeline par defaut - Qualite de base'


def seed_default_cleaning_rules(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    CleaningRule = apps.get_model('nettoyage', 'CleaningRule')
    CleaningPipeline = apps.get_model('nettoyage', 'CleaningPipeline')

    system_user, created = User.objects.get_or_create(
        username=SYSTEM_USERNAME,
        defaults={
            'email': 'system-cleaning@local.invalid',
            'is_active': True,
            'is_staff': True,
            'first_name': 'Systeme',
            'last_name': 'Nettoyage',
        },
    )
    if created:
        system_user.password = '!'
        system_user.save(update_fields=['password'])

    rules_config = [
        {
            'name': 'Retirer les lignes vides',
            'description': 'Supprime les lignes vides ou composees uniquement d espaces.',
            'rule_type': 'remove_empty_rows',
            'priority': 10,
            'apply_to_all': True,
            'category': 'qualite_de_base',
            'parameters': {},
        },
        {
            'name': 'Uniformiser les valeurs texte',
            'description': 'Supprime les espaces inutiles autour des valeurs texte pour fiabiliser les comparaisons.',
            'rule_type': 'standardize',
            'priority': 9,
            'apply_to_all': True,
            'category': 'qualite_de_base',
            'parameters': {'mode': 'trim'},
        },
        {
            'name': 'Supprimer les doublons exacts',
            'description': 'Retire les lignes dupliquees a l identique dans le fichier importe.',
            'rule_type': 'remove_duplicates',
            'priority': 8,
            'apply_to_all': True,
            'category': 'qualite_de_base',
            'parameters': {},
        },
    ]

    created_rules = []
    for config in rules_config:
        rule, _ = CleaningRule.objects.update_or_create(
            name=config['name'],
            defaults={
                **config,
                'created_by': system_user,
                'is_active': True,
                'column_names': [],
                'tags': ['default', 'system', 'production'],
            },
        )
        created_rules.append(rule)

    pipeline, _ = CleaningPipeline.objects.update_or_create(
        name=DEFAULT_PIPELINE_NAME,
        defaults={
            'description': 'Pipeline de nettoyage par defaut applique aux imports quand aucune configuration specifique n est fournie.',
            'source_type_scope': '',
            'quality_gate': {},
            'is_active': True,
            'apply_to_all': True,
            'created_by': system_user,
        },
    )
    pipeline.rules.set(created_rules)


def noop_reverse(apps, schema_editor):
    # Intentionally keep seeded rules/pipeline in place; they are part of the baseline product configuration.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('nettoyage', '0006_cleaningjob_export_path'),
    ]

    operations = [
        migrations.RunPython(seed_default_cleaning_rules, noop_reverse),
    ]
