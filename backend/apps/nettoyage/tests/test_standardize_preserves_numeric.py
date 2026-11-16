import pytest
from django.contrib.auth.models import User

import pandas as pd

from apps.nettoyage.models import CleaningRule
from apps.nettoyage.services import _apply_rules, _standardize_value


def test_standardize_preserves_numeric_values():
    assert _standardize_value(14122.61, 'trim') == 14122.61
    assert _standardize_value(500, 'trim') == 500
    assert _standardize_value(3.5, 'upper') == 3.5
    assert _standardize_value('  Sweden ', 'trim') == 'Sweden'
    assert _standardize_value(None, 'trim') is None
    assert _standardize_value('', 'trim') == ''


@pytest.mark.django_db
def test_standardize_rule_with_empty_column_names_keeps_numeric_typed():
    """Regression: a standardize rule auto-generated with empty column_names
    applies to every column; it must not stringify numeric measures."""
    user = User.objects.create_user(username='std_owner', password='x')
    rule = CleaningRule.objects.create(
        name='Uniformiser les valeurs',
        rule_type='standardize',
        column_names=[],
        parameters={'mode': 'trim'},
        created_by=user,
    )
    dataframe = pd.DataFrame({
        '_row_number': [1, 2],
        'cost': [14122.61, 92807.78],
        'country': ['  Sweden ', ' France'],
    })
    result = _apply_rules(dataframe=dataframe, rules=[rule], quality_gate={})
    out = result['dataframe']
    assert pd.api.types.is_numeric_dtype(out['cost']), f"cost became {out['cost'].dtype}"
    assert out['cost'].tolist() == [14122.61, 92807.78]
    assert out['country'].tolist() == ['Sweden', 'France']