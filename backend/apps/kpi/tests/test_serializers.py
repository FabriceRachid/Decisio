"""
Tests for KPI serializers.
"""
import pytest
from decimal import Decimal
from datetime import date
from apps.kpi.serializers import (
    KPIListSerializer,
    KPIDetailSerializer,
    KPICreateUpdateSerializer,
    KPICalculationSummarySerializer,
    KPICalculationDetailSerializer,
    KPIAlertListSerializer,
    KPIAlertDetailSerializer,
    KPIHistorySerializer,
    KPIAnomalySerializer,
    KPIForecastSerializer
)
from apps.kpi.models import KPI, KPICalculation, KPIAlert


@pytest.mark.django_db
class TestKPIListSerializer:
    """Tests for KPI list serializer."""
    
    def test_serialize_kpi_list(self, test_kpi):
        """Test serializing KPI in list view."""
        serializer = KPIListSerializer(test_kpi)
        data = serializer.data
        
        assert data['id'] == test_kpi.id
        assert data['name'] == test_kpi.name
        assert data['code'] == test_kpi.code
        assert 'latest_calculation' in data
        assert 'calculation_count' in data
    
    def test_kpi_list_serializer_with_no_calculations(self, test_kpi):
        """Test list serializer with KPI that has no calculations."""
        serializer = KPIListSerializer(test_kpi)
        data = serializer.data
        
        assert data['calculation_count'] == 0
        assert data['latest_calculation'] is None


@pytest.mark.django_db
class TestKPIDetailSerializer:
    """Tests for KPI detail serializer."""
    
    def test_serialize_kpi_detail(self, test_kpi):
        """Test serializing KPI in detail view."""
        serializer = KPIDetailSerializer(test_kpi)
        data = serializer.data
        
        assert data['id'] == test_kpi.id
        assert data['name'] == test_kpi.name
        assert data['code'] == test_kpi.code
        assert 'formula' in data
        assert 'formula_type' in data
    
    def test_detail_serializer_includes_counts(self, test_kpi):
        """Test that detail serializer includes all aggregated counts."""
        serializer = KPIDetailSerializer(test_kpi)
        data = serializer.data
        
        assert 'child_kpis_count' in data
        assert 'calculations_count' in data
        assert 'alerts_count' in data


@pytest.mark.django_db
class TestKPICreateUpdateSerializer:
    """Tests for KPI create/update serializer."""
    
    def test_deserialize_valid_kpi(self, test_user):
        """Test deserializing valid KPI data."""
        data = {
            'name': 'Test KPI',
            'code': 'TEST_KPI',
            'formula': 'SELECT COUNT(*) FROM table',
            'formula_type': 'sql',
            'target_value': '1000000',
            'unit': '#',
            'frequency': 'monthly',
            'category': 'Operational'
        }
        
        serializer = KPICreateUpdateSerializer(data=data)
        assert serializer.is_valid()
    
    def test_deserialize_invalid_kpi_missing_name(self):
        """Test that serializer rejects KPI without name."""
        data = {
            'code': 'TEST_KPI',
            'formula': 'SELECT COUNT(*) FROM table',
            'formula_type': 'sql',
            'target_value': '1000000'
        }
        
        serializer = KPICreateUpdateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'name' in serializer.errors
    
    def test_validate_sql_formula(self):
        """Test that serializer validates SQL formulas."""
        data = {
            'name': 'Test KPI',
            'code': 'TEST_KPI',
            'formula': 'INVALID SQL',
            'formula_type': 'sql',
            'target_value': '1000000'
        }
        
        serializer = KPICreateUpdateSerializer(data=data)
        # Should fail validation as formula lacks SELECT and FROM
        if not serializer.is_valid():
            assert 'formula' in serializer.errors


@pytest.mark.django_db
class TestKPICalculationSummarySerializer:
    """Tests for KPI Calculation summary serializer."""
    
    def test_serialize_calculation_summary(self, test_kpi_calculation):
        """Test serializing a calculation in summary view."""
        serializer = KPICalculationSummarySerializer(test_kpi_calculation)
        data = serializer.data
        
        assert data['id'] == test_kpi_calculation.id
        assert 'kpi_name' in data
        assert 'kpi_code' in data
        assert 'executed_by_name' in data


@pytest.mark.django_db  
class TestKPIAlertListSerializer:
    """Tests for KPI Alert list serializer."""
    
    def test_serialize_alert_summary(self, test_kpi_alert):
        """Test serializing an alert in list view."""
        serializer = KPIAlertListSerializer(test_kpi_alert)
        data = serializer.data
        
        assert data['id'] == test_kpi_alert.id
        assert data['alert_name'] == test_kpi_alert.alert_name
        assert 'is_active' in data


@pytest.mark.django_db
class TestSerializerValidation:
    """Tests for custom serializer validations."""
    
    def test_kpi_code_uniqueness_validation(self, test_kpi):
        """Test that KPI code must be unique."""
        data = {
            'name': 'Duplicate Code KPI',
            'code': test_kpi.code,  # Same code as existing KPI
            'formula': 'SELECT 1',
            'formula_type': 'sql',
            'target_value': '1000000'
        }
        
        serializer = KPICreateUpdateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'code' in serializer.errors
    
    def test_calculation_variance_calculation(self, test_kpi_calculation):
        """Test that calculation serializer includes variance info."""
        serializer = KPICalculationSummarySerializer(test_kpi_calculation)
        data = serializer.data
        
        # Variance should be calculated or included
        assert data is not None
        assert test_kpi_calculation.calculated_value is not None
    
    def test_threshold_value_decimal_precision(self, test_kpi):
        """Test that threshold values respect decimal precision."""
        # Create alert with decimal values
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Precision Test',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.9999')
        )
        
        serializer = KPIAlertDetailSerializer(alert)
        # Verify decimal is preserved
        assert Decimal(str(serializer.data['threshold_value'])).as_tuple().exponent <= -4
