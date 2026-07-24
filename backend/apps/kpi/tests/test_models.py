"""
Tests for KPI models.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth.models import User
from apps.kpi.models import KPI, KPICalculation, KPIAlert


@pytest.mark.django_db
class TestKPIModel:
    """Tests for KPI model."""
    
    def test_create_kpi_with_sql_formula(self, test_user):
        """Test creating KPI with SQL formula."""
        kpi = KPI.objects.create(
            name='Revenue KPI',
            code='REV_001',
            formula='SELECT SUM(amount) FROM table WHERE date > %s',
            formula_type='sql',
            target_value=Decimal('1000000.0000'),
            unit='$',
            frequency='monthly',
            owner=test_user
        )
        
        assert kpi.name == 'Revenue KPI'
        assert kpi.code == 'REV_001'
        assert kpi.formula_type == 'sql'
        assert kpi.is_active is True
        assert str(kpi) == 'Revenue KPI (REV_001)'
    
    def test_create_kpi_with_python_formula(self, test_user):
        """Test creating KPI with Python formula."""
        kpi = KPI.objects.create(
            name='Growth Rate KPI',
            code='GROWTH',
            formula='(current - previous) / previous * 100',
            formula_type='python',
            owner=test_user
        )
        
        assert kpi.formula_type == 'python'
        assert 'current' in kpi.formula
    
    def test_create_kpi_with_excel_formula(self, test_user):
        """Test creating KPI with Excel formula."""
        kpi = KPI.objects.create(
            name='Total Sales',
            code='TOTAL_SALES',
            formula_type='excel',
            aggregation_method='SUM',
            source_table='nettoyage_cleaneddata',
            measure_column='amount',
            owner=test_user
        )
        
        assert kpi.formula_type == 'excel'
        assert kpi.aggregation_method == 'SUM'
        assert kpi.measure_column == 'amount'
    
    def test_kpi_with_hierarchical_relationship(self, test_user):
        """Test KPI hierarchical relationships."""
        parent_kpi = KPI.objects.create(
            name='Total Revenue',
            code='TOTAL_REV',
            owner=test_user
        )
        
        child_kpi = KPI.objects.create(
            name='Q1 Revenue',
            code='Q1_REV',
            parent_kpi=parent_kpi,
            owner=test_user
        )
        
        assert child_kpi.parent_kpi == parent_kpi
        assert parent_kpi.child_kpis.count() == 1
        assert parent_kpi.child_kpis.first() == child_kpi
    
    def test_kpi_with_tags(self, test_user):
        """Test KPI tags."""
        kpi = KPI.objects.create(
            name='Financial KPI',
            code='FIN_001',
            tags=['financial', 'critical', 'monthly'],
            owner=test_user
        )
        
        assert 'financial' in kpi.tags
        assert len(kpi.tags) == 3
    
    def test_kpi_uniqueness_constraints(self, test_user):
        """Test KPI unique constraints."""
        KPI.objects.create(name='KPI1', code='CODE1', owner=test_user)
        
        with pytest.raises(Exception):
            KPI.objects.create(name='KPI1', code='CODE1', owner=test_user)
    
    def test_kpi_with_dimensions(self, test_user):
        """Test KPI with dimensional breakdown."""
        kpi = KPI.objects.create(
            name='Regional Sales',
            code='REG_SALES',
            dimension_columns=['region', 'product'],
            owner=test_user
        )
        
        assert 'region' in kpi.dimension_columns
        assert 'product' in kpi.dimension_columns


@pytest.mark.django_db
class TestKPICalculationModel:
    """Tests for KPICalculation model."""
    
    def test_create_kpi_calculation(self, test_kpi, test_user):
        """Test creating KPI calculation."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calc = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            period_label='January 2026',
            calculated_value=Decimal('4850000.0000'),
            status='on_target',
            executed_by=test_user
        )
        
        assert calc.calculated_value == Decimal('4850000.0000')
        assert calc.status == 'on_target'
        assert calc.period_label == 'January 2026'
    
    def test_kpi_calculation_variance(self, test_kpi, test_user):
        """Test KPI calculation variance tracking."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calc = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4850000.0000'),
            previous_value=Decimal('5000000.0000'),
            variance_absolute=Decimal('-150000.0000'),
            variance_percent=Decimal('-3.00'),
            executed_by=test_user
        )
        
        assert calc.variance_absolute == Decimal('-150000.0000')
        assert calc.variance_percent == Decimal('-3.00')
    
    def test_kpi_calculation_with_breakdown(self, test_kpi, test_user):
        """Test KPI calculation with dimensional breakdown."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        breakdown = {
            'region': {'US': 2000000, 'EU': 1500000, 'APAC': 1350000},
            'product': {'A': 3000000, 'B': 1850000}
        }
        
        calc = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4850000.0000'),
            breakdown=breakdown,
            executed_by=test_user
        )
        
        assert calc.breakdown['region']['US'] == 2000000
        assert calc.breakdown['product']['A'] == 3000000
    
    def test_kpi_calculation_anomaly_detection(self, test_kpi, test_user):
        """Test KPI calculation anomaly flag."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calc = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4850000.0000'),
            anomaly_detected=True,
            executed_by=test_user
        )
        
        assert calc.anomaly_detected is True
    
    def test_kpi_calculation_unique_constraint(self, test_kpi, test_user):
        """Test unique constraint on period."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4850000.0000'),
            executed_by=test_user
        )
        
        with pytest.raises(Exception):
            KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=Decimal('5000000.0000'),
                executed_by=test_user
            )
    
    def test_kpi_calculation_data_quality_score(self, test_kpi, test_user):
        """Test KPI calculation data quality score."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calc = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4850000.0000'),
            data_quality_score=Decimal('92.50'),
            rows_processed=1250,
            executed_by=test_user
        )
        
        assert calc.data_quality_score == Decimal('92.50')
        assert calc.rows_processed == 1250


@pytest.mark.django_db
class TestKPIAlertModel:
    """Tests for KPIAlert model."""
    
    def test_create_kpi_alert(self, test_kpi, test_user):
        """Test creating KPI alert."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Revenue Below Threshold',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.0000'),
            notification_channels=['email'],
            recipients=['alert@example.com'],
            created_by=test_user
        )
        
        assert alert.alert_name == 'Revenue Below Threshold'
        assert alert.condition_type == 'below'
        assert alert.is_active is True
    
    def test_kpi_alert_anomaly_type(self, test_kpi, test_user):
        """Test anomaly detection alert type."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Anomaly Detection',
            alert_type='anomaly',
            notification_channels=['email', 'webhook'],
            webhook_url='https://example.com/webhook',
            created_by=test_user
        )
        
        assert alert.alert_type == 'anomaly'
        assert alert.webhook_url == 'https://example.com/webhook'
    
    def test_kpi_alert_percentage_condition(self, test_kpi, test_user):
        """Test percentage change condition."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Large Change Alert',
            alert_type='threshold_breach',
            condition_type='changed_by',
            threshold_percent=Decimal('10.00'),
            created_by=test_user
        )
        
        assert alert.condition_type == 'changed_by'
        assert alert.threshold_percent == Decimal('10.00')
    
    def test_kpi_alert_trigger_tracking(self, test_kpi, test_user):
        """Test alert trigger tracking."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Test Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.0000'),
            created_by=test_user
        )
        
        assert alert.is_triggered is False
        assert alert.trigger_count == 0
        
        # Simulate trigger
        alert.is_triggered = True
        alert.trigger_count = 1
        alert.save()
        
        alert.refresh_from_db()
        assert alert.is_triggered is True
        assert alert.trigger_count == 1
    
    def test_kpi_alert_cooldown(self, test_kpi, test_user):
        """Test alert cooldown period."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Test Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.0000'),
            cooldown_minutes=120,
            created_by=test_user
        )
        
        assert alert.cooldown_minutes == 120
    
    def test_kpi_alert_acknowledgment(self, test_kpi, test_user):
        """Test alert acknowledgment."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Test Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.0000'),
            created_by=test_user
        )
        
        assert alert.acknowledged_by is None
        assert alert.acknowledged_at is None
        
        alert.acknowledged_by = test_user
        alert.resolution_notes = 'Reviewed and addressed'
        alert.save()
        
        alert.refresh_from_db()
        assert alert.acknowledged_by == test_user
        assert 'Reviewed' in alert.resolution_notes
