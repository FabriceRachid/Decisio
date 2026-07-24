import pytest
from django.contrib.auth.models import User

from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData, CleaningRule
from apps.nettoyage.services import apply_cleaning


@pytest.mark.django_db
def test_apply_cleaning_persists_unified_engine_job_and_report():
    user = User.objects.create_user(username='apply_engine', email='apply_engine@example.com')
    source = DataSource.objects.create(
        name='ApplyEngine.csv',
        source_type='csv',
        uploaded_by=user,
    )
    RawData.objects.bulk_create(
        [
            RawData(source=source, row_number=1, data={'Client_Nom': 'CLIENT A  ', 'Mont_TTC': '1000 FCFA'}, validation_status='valid'),
            RawData(source=source, row_number=2, data={'Client_Nom': '   ', 'Mont_TTC': ''}, validation_status='warning'),
        ]
    )
    rule = CleaningRule.objects.create(
        name='Auto standardize',
        rule_type='standardize',
        created_by=user,
        column_names=['Client_Nom'],
        parameters={'mode': 'trim'},
        apply_to_all=True,
    )

    result = apply_cleaning(
        source=source,
        user=user,
        pipeline_id=None,
        rule_ids=[rule.id],
        include_all_auto_rules=True,
        quality_gate={},
    )

    assert result['job_id']
    assert 'cleaning_report' in result
    assert result['summary']['rows_processed'] == 1
    assert result['summary']['rows_affected'] >= 1

    cleaned_rows = CleanedData.objects.filter(job_id=result['job_id']).order_by('original_data__row_number')
    assert cleaned_rows.count() == 1
    assert cleaned_rows.first().data['Client_Nom'] == 'Client A'
    assert cleaned_rows.first().changes_made
