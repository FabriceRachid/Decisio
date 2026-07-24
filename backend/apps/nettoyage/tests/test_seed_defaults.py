import pytest

from apps.nettoyage.models import CleaningPipeline, CleaningRule


@pytest.mark.django_db
def test_default_cleaning_rules_and_pipeline_are_seeded():
    rules = CleaningRule.objects.filter(
        name__in=[
            'Retirer les lignes vides',
            'Uniformiser les valeurs texte',
            'Supprimer les doublons exacts',
        ],
        is_active=True,
        apply_to_all=True,
    )
    assert rules.count() == 3

    pipeline = CleaningPipeline.objects.get(name='Pipeline par defaut - Qualite de base')
    assert pipeline.is_active is True
    assert pipeline.apply_to_all is True
    assert pipeline.rules.filter(is_active=True).count() == 3
