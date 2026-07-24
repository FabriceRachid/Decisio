"""
Tests for KPI calculation services.
"""
import pytest
import numpy as np
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock
from apps.kpi.services import (
    KPICalculationService,
    KPIAnomalyDetectionService,
    KPIForecastingService,
    KPIAlertingService
)
from apps.kpi.models import KPI, KPICalculation, KPIAlert


@pytest.mark.django_db
class TestKPICalculationService:
    """Tests for KPICalculationService."""
    
    def test_calculate_kpi_initialization(self, test_user):
        """Test service initialization."""
        service = KPICalculationService(test_user, safe_mode=True)
        
        assert service.user == test_user
        assert service.safe_mode is True
        assert 'sum' in service.allowed_functions
    
    @patch('apps.kpi.services.connection')
    def test_evaluate_sql_formula(self, mock_connection, test_kpi, test_user):
        """Test SQL formula evaluation."""
        service = KPICalculationService(test_user)
        
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (Decimal('4850000'),)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        
        result = service._evaluate_sql_formula(
            test_kpi,
            date(2026, 1, 1),
            date(2026, 1, 31)
        )
        
        assert 'value' in result
        assert result['rows_processed'] == 0
    
    def test_evaluate_python_formula_basic(self, test_user):
        """Test basic Python formula evaluation."""
        service = KPICalculationService(test_user, safe_mode=True)
        
        kpi = Mock()
        kpi.formula = "sum([100, 200, 300])"
        kpi.source_table = None
        
        result = service._evaluate_python_formula(
            kpi,
            date(2026, 1, 1),
            date(2026, 1, 31)
        )
        
        assert result['value'] == 600.0
    
    def test_evaluate_python_formula_with_math(self, test_user):
        """Test Python formula with mathematical operations."""
        service = KPICalculationService(test_user, safe_mode=True)
        
        kpi = Mock()
        kpi.formula = "(1000000 - 950000) / 1000000 * 100"
        kpi.source_table = None
        
        result = service._evaluate_python_formula(
            kpi,
            date(2026, 1, 1),
            date(2026, 1, 31)
        )
        
        assert abs(result['value'] - 5.0) < 0.1
    
    def test_python_formula_blocks_dangerous_patterns(self, test_user):
        """Test that dangerous patterns are blocked."""
        service = KPICalculationService(test_user, safe_mode=True)
        
        kpi = Mock()
        kpi.formula = "import os; os.system('rm -rf /')"
        kpi.source_table = None
        
        with pytest.raises(ValueError, match="Dangerous pattern"):
            service._evaluate_python_formula(
                kpi,
                date(2026, 1, 1),
                date(2026, 1, 31)
            )
    
    def test_evaluate_excel_formula_sum(self, test_user):
        """Test Excel SUM formula."""
        service = KPICalculationService(test_user)
        
        kpi = Mock()
        kpi.aggregation_method = 'SUM'
        kpi.measure_column = 'amount'
        kpi.source_table = 'test_table'
        kpi.dimension_columns = []
        
        with patch.object(service, '_get_table_data') as mock_get_data:
            mock_get_data.return_value = [
                {'amount': 1000},
                {'amount': 2000},
                {'amount': 3000}
            ]
            
            result = service._evaluate_excel_formula(
                kpi,
                date(2026, 1, 1),
                date(2026, 1, 31)
            )
            
            assert result['value'] == 6000
            assert result['rows_processed'] == 3
    
    def test_evaluate_excel_formula_avg(self, test_user):
        """Test Excel AVG formula."""
        service = KPICalculationService(test_user)
        
        kpi = Mock()
        kpi.aggregation_method = 'AVG'
        kpi.measure_column = 'amount'
        kpi.source_table = 'test_table'
        kpi.dimension_columns = []
        
        with patch.object(service, '_get_table_data') as mock_get_data:
            mock_get_data.return_value = [
                {'amount': 100},
                {'amount': 200},
                {'amount': 300}
            ]
            
            result = service._evaluate_excel_formula(
                kpi,
                date(2026, 1, 1),
                date(2026, 1, 31)
            )
            
            assert result['value'] == 200
    
    def test_calculate_kpi_with_previous_value(self, test_kpi, test_user):
        """Test KPI calculation with previous value for variance."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        # Create previous calculation
        prev_period_end = period_start - timedelta(days=1)
        prev_period_start = prev_period_end - timedelta(days=30)
        
        KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=prev_period_start,
            period_end=prev_period_end,
            calculated_value=Decimal('5000000.0000'),
            status='on_target',
            executed_by=test_user
        )
        
        service = KPICalculationService(test_user)
        
        with patch.object(service, '_evaluate_sql_formula') as mock_eval:
            mock_eval.return_value = {
                'value': 4850000,
                'rows_processed': 1250,
                'breakdown': {}
            }
            
            result = service.calculate_kpi(test_kpi, period_start, period_end)
            
            assert result['success'] is True
            assert result['calculated_value'] == 4850000
            assert result['variance_percent'] is not None
    
    def test_batch_calculate_kpis(self, test_kpi, test_user):
        """Test batch KPI calculation."""
        service = KPICalculationService(test_user)
        
        kpis = [test_kpi]
        
        with patch.object(service, 'calculate_kpi') as mock_calc:
            mock_calc.return_value = {
                'success': True,
                'calculated_value': 4850000,
                'variance_percent': -3.0,
                'status': 'on_target',
                'data_quality_score': 92.5,
                'rows_processed': 1250,
                'execution_time_ms': 850,
                'breakdown': {}
            }
            
            results = service.batch_calculate_kpis(
                kpis,
                date(2026, 1, 1),
                date(2026, 1, 31)
            )
            
            assert test_kpi.code in results
            assert results[test_kpi.code] is True


@pytest.mark.django_db
class TestKPIAnomalyDetectionService:
    """Tests for KPIAnomalyDetectionService."""
    
    def test_anomaly_detection_initialization(self, test_user):
        """Test service initialization."""
        service = KPIAnomalyDetectionService(test_user)
        assert service.user == test_user
    
    def test_detect_anomalies_no_history(self, test_kpi, test_user):
        """Test anomaly detection with insufficient history."""
        service = KPIAnomalyDetectionService(test_user)
        
        result = service.detect_anomalies(test_kpi, lookback_periods=12)
        
        assert result['has_anomaly'] is False
        assert 'insufficient' in result['reason'].lower()
    
    def test_detect_anomalies_z_score(self, test_kpi, test_user):
        """Test Z-score anomaly detection."""
        period_end = date.today()
        
        # Create 12 historical calculations
        for i in range(12):
            period_start = period_end - timedelta(days=30)
            KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=Decimal('5000000.0000'),
                status='on_target',
                executed_by=test_user
            )
            period_end = period_start - timedelta(days=1)
        
        service = KPIAnomalyDetectionService(test_user)
        result = service.detect_anomalies(test_kpi, lookback_periods=12)
        
        assert 'z_score' in result
        assert 'mean' in result
        assert 'std_dev' in result
    
    def test_anomaly_detection_with_outlier(self, test_kpi, test_user):
        """Test anomaly detection identifies outliers."""
        period_end = date.today() - timedelta(days=30)
        
        # Create stable baseline history first.
        for i in range(11):
            period_start = period_end - timedelta(days=30)
            KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=Decimal('5000000.0000'),
                status='on_target',
                executed_by=test_user
            )
            period_end = period_start - timedelta(days=1)
        
        # Add the outlier as the latest value so anomaly detection checks it.
        latest_period_end = date.today()
        latest_period_start = latest_period_end - timedelta(days=30)
        KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=latest_period_start,
            period_end=latest_period_end,
            calculated_value=Decimal('2000000.0000'),  # Outlier!
            status='critical',
            executed_by=test_user
        )
        
        service = KPIAnomalyDetectionService(test_user)
        result = service.detect_anomalies(test_kpi, lookback_periods=12)
        
        # Z-score should be > 2.5
        assert result['z_score'] > 2.5 or result['has_anomaly'] is True


@pytest.mark.django_db
class TestKPIForecastingService:
    """Tests for KPIForecastingService."""
    
    def test_forecasting_service_initialization(self, test_user):
        """Test service initialization."""
        service = KPIForecastingService(test_user)
        assert service.user == test_user
    
    def test_forecast_insufficient_data(self, test_kpi, test_user):
        """Test forecasting with insufficient data."""
        service = KPIForecastingService(test_user)
        
        result = service.forecast_kpi(test_kpi, forecast_periods=3)
        
        assert result['success'] is False
        assert 'insufficient' in result['error'].lower()
    
    def test_forecast_linear_trend(self, test_kpi, test_user):
        """Test linear trend forecasting."""
        period_end = date.today()
        
        # Create 6 calculations with increasing values
        for i in range(6):
            value = Decimal(str(4000000 + (i * 100000)))  # Increasing trend
            period_start = period_end - timedelta(days=30)
            KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=value,
                status='on_target',
                executed_by=test_user
            )
            period_end = period_start - timedelta(days=1)
        
        service = KPIForecastingService(test_user)
        result = service.forecast_kpi(test_kpi, forecast_periods=3)
        
        assert result['success'] is True
        assert 'forecast_values' in result
        assert len(result['forecast_values']) == 3
        assert 'trend' in result
    
    def test_forecast_confidence_intervals(self, test_kpi, test_user):
        """Test forecast with confidence intervals."""
        period_end = date.today()
        
        # Create 6 calculations
        for i in range(6):
            period_start = period_end - timedelta(days=30)
            KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=Decimal('5000000.0000'),
                status='on_target',
                executed_by=test_user
            )
            period_end = period_start - timedelta(days=1)
        
        service = KPIForecastingService(test_user)
        result = service.forecast_kpi(test_kpi, forecast_periods=3)
        
        assert 'confidence_intervals' in result
        assert len(result['confidence_intervals']) == 3
        # Each CI should have [lower, upper]
        assert len(result['confidence_intervals'][0]) == 2


@pytest.mark.django_db
class TestKPIAlertingService:
    """Tests for KPIAlertingService."""
    
    def test_alerting_service_initialization(self, test_user):
        """Test service initialization."""
        service = KPIAlertingService(test_user)
        assert service.user == test_user
    
    def test_evaluate_alert_above_condition(self, test_kpi, test_user):
        """Test alert evaluation with 'above' condition."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calculation = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('5500000.0000'),
            status='on_target',
            executed_by=test_user
        )
        
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='High Revenue Alert',
            alert_type='threshold_breach',
            condition_type='above',
            threshold_value=Decimal('5000000.0000'),
            notification_channels=['email'],
            created_by=test_user
        )
        
        service = KPIAlertingService(test_user)
        should_trigger = service._check_alert_condition(alert, calculation)
        
        assert should_trigger is True
    
    def test_evaluate_alert_below_condition(self, test_kpi, test_user):
        """Test alert evaluation with 'below' condition."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calculation = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4000000.0000'),
            status='critical',
            executed_by=test_user
        )
        
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Low Revenue Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.0000'),
            notification_channels=['email'],
            created_by=test_user
        )
        
        service = KPIAlertingService(test_user)
        should_trigger = service._check_alert_condition(alert, calculation)
        
        assert should_trigger is True
    
    def test_evaluate_alert_changed_by_condition(self, test_kpi, test_user):
        """Test alert evaluation with 'changed_by' percentage condition."""
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calculation = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4500000.0000'),
            previous_value=Decimal('5000000.0000'),
            status='warning',
            executed_by=test_user
        )
        
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Large Change Alert',
            alert_type='threshold_breach',
            condition_type='changed_by',
            threshold_percent=Decimal('8.00'),  # 8%
            notification_channels=['email'],
            created_by=test_user
        )
        
        service = KPIAlertingService(test_user)
        should_trigger = service._check_alert_condition(alert, calculation)
        
        # Change is 10%, threshold is 8%, so should trigger
        assert should_trigger is True
    
    def test_alert_cooldown_prevention(self, test_kpi, test_user):
        """Test that cooldown prevents repeated alerts."""
        from datetime import datetime
        from django.utils import timezone
        
        period_end = date.today()
        period_start = period_end - timedelta(days=30)
        
        calculation = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=period_start,
            period_end=period_end,
            calculated_value=Decimal('4000000.0000'),
            status='critical',
            executed_by=test_user
        )
        
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Test Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000.0000'),
            notification_channels=['email'],
            cooldown_minutes=60,
            last_triggered_at=timezone.now(),
            created_by=test_user
        )
        
        service = KPIAlertingService(test_user)
        
        # Check condition (should be true)
        should_trigger_condition = service._check_alert_condition(alert, calculation)
        assert should_trigger_condition is True
        
        # But cooldown should prevent it
        with patch.object(service, '_send_alert_notifications') as mock_send:
            result = service.evaluate_alerts(calculation)
            # Cooldown prevents alert from being sent
            assert mock_send.call_count == 0
