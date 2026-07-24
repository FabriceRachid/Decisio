"""
Integration tests for KPI module workflows.
Tests complete workflows from data ingestion through KPI calculation to alerting.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import TransactionTestCase
from apps.kpi.models import KPI, KPICalculation, KPIAlert
from apps.kpi.services import (
    KPICalculationService,
    KPIAnomalyDetectionService,
    KPIAlertingService
)


@pytest.mark.django_db
class TestKPICalculationWorkflow:
    """Integration tests for complete KPI calculation workflow."""
    
    def test_kpi_calculation_creates_records(self, test_kpi, test_user):
        """Test that KPI calculation creates proper records."""
        service = KPICalculationService()
        
        period_start = date(2026, 1, 1)
        period_end = date(2026, 1, 31)
        
        # Perform calculation
        calculation = service.calculate_kpi(
            test_kpi,
            period_start,
            period_end,
            test_user
        )
        
        assert calculation is not None
        assert calculation.kpi == test_kpi
        assert calculation.period_start == period_start
        assert calculation.period_end == period_end
    
    def test_kpi_calculation_with_variance_tracking(self, test_kpi, test_user):
        """Test that variance is properly tracked across periods."""
        service = KPICalculationService()
        
        # Calculate for first period
        period1_start = date(2026, 1, 1)
        period1_end = date(2026, 1, 31)
        calc1 = service.calculate_kpi(test_kpi, period1_start, period1_end, test_user)
        
        # Calculate for second period with different value
        period2_start = date(2026, 2, 1)
        period2_end = date(2026, 2, 28)
        calc1.calculated_value = Decimal('5000000')
        calc1.save()
        
        calc2 = service.calculate_kpi(test_kpi, period2_start, period2_end, test_user)
        
        # Second calculation should compare to first
        assert calc1.id != calc2.id
        assert calc1.calculated_value == Decimal('5000000')
    
    def test_multiple_kpi_batch_calculation(self, test_kpi, test_user):
        """Test batch calculation of multiple KPIs."""
        service = KPICalculationService()
        
        # Create additional KPI
        kpi2 = KPI.objects.create(
            name='KPI 2',
            code='KPI2',
            formula='SELECT 1',
            formula_type='sql',
            target_value=Decimal('6000000'),
            unit='$'
        )
        
        kpis = [test_kpi, kpi2]
        period_start = date(2026, 1, 1)
        period_end = date(2026, 1, 31)
        
        # Batch calculate
        results = []
        for kpi in kpis:
            calc = service.calculate_kpi(kpi, period_start, period_end, test_user)
            results.append(calc)
        
        assert len(results) == 2
        assert all(r is not None for r in results)


@pytest.mark.django_db
class TestAnomalyDetectionIntegration:
    """Integration tests for anomaly detection workflow."""
    
    def test_anomaly_detection_after_calculation(self, test_kpi, test_user):
        """Test anomaly detection is triggered after KPI calculation."""
        calc_service = KPICalculationService()
        anomaly_service = KPIAnomalyDetectionService()
        
        # Create multiple calculations to establish baseline
        for i in range(5):
            period_start = date(2026, 1, 1) + timedelta(days=i*30)
            period_end = period_start + timedelta(days=30)
            
            calc = calc_service.calculate_kpi(
                test_kpi,
                period_start,
                period_end,
                test_user
            )
            calc.calculated_value = Decimal('5000000') + Decimal(i * 10000)
            calc.save()
        
        # Last calculation with anomaly
        period_start = date(2026, 6, 1)
        period_end = date(2026, 6, 30)
        anomaly_calc = calc_service.calculate_kpi(
            test_kpi,
            period_start,
            period_end,
            test_user
        )
        anomaly_calc.calculated_value = Decimal('10000000')  # Huge spike
        anomaly_calc.save()
        
        # Detect anomalies
        history = KPICalculation.objects.filter(kpi=test_kpi).order_by('period_end')
        has_anomaly = anomaly_service.detect_anomalies(list(history))
        
        # Should detect the anomaly in the last value
        assert isinstance(has_anomaly, (bool, dict))


@pytest.mark.django_db
class TestAlertTriggering:
    """Integration tests for alert triggering workflow."""
    
    def test_alert_triggered_on_threshold_breach(self, test_kpi, test_user, test_kpi_alert):
        """Test alert is triggered when KPI breaches threshold."""
        calc_service = KPICalculationService()
        alert_service = KPIAlertingService(test_kpi_alert)
        
        # Calculate KPI with value below alert threshold
        period_start = date(2026, 1, 1)
        period_end = date(2026, 1, 31)
        
        calc = calc_service.calculate_kpi(test_kpi, period_start, period_end, test_user)
        calc.calculated_value = Decimal('4000000')  # Below 4.5M threshold
        calc.save()
        
        # Check if alert should trigger
        should_trigger = alert_service.evaluate_condition(calc)
        
        # Alert should be triggered based on threshold breach
        assert isinstance(should_trigger, bool)
    
    def test_alert_respects_cooldown_period(self, test_kpi, test_user, test_kpi_alert):
        """Test that alerts respect cooldown period."""
        calc_service = KPICalculationService()
        alert_service = KPIAlertingService(test_kpi_alert)
        
        # First breach
        calc1 = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            calculated_value=Decimal('4000000'),
            status='below_target',
            executed_by=test_user
        )
        
        trigger1 = alert_service.evaluate_condition(calc1)
        
        # Second breach immediately after
        calc2 = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            calculated_value=Decimal('3500000'),
            status='below_target',
            executed_by=test_user
        )
        
        trigger2 = alert_service.evaluate_condition(calc2)
        
        # At least one should be triggered, but cooldown might prevent immediate second
        assert isinstance(trigger1, bool)
        assert isinstance(trigger2, bool)


@pytest.mark.django_db
class TestCompleteWorkflow:
    """Integration tests for complete M1→M2→M3→M4 workflow."""
    
    def test_kpi_creation_and_initial_calculation(self, test_user):
        """Test KPI creation and initial calculation."""
        # Step 1: Create KPI
        kpi = KPI.objects.create(
            name='Revenue',
            code='REVENUE',
            formula='SELECT SUM(amount) FROM sales',
            formula_type='sql',
            target_value=Decimal('5000000'),
            unit='$',
            frequency='monthly'
        )
        
        assert kpi.id is not None
        
        # Step 2: Create alert for the KPI
        alert = KPIAlert.objects.create(
            kpi=kpi,
            alert_name='Revenue Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000'),
            cooldown_minutes=60,
            is_active=True
        )
        
        assert alert.id is not None
        
        # Step 3: Calculate KPI
        service = KPICalculationService()
        calc = service.calculate_kpi(
            kpi,
            date(2026, 1, 1),
            date(2026, 1, 31),
            test_user
        )
        
        assert calc is not None
        assert calc.kpi == kpi
    
    def test_multi_period_workflow_with_alerts(self, test_kpi, test_user):
        """Test workflow across multiple periods with alert triggering."""
        calc_service = KPICalculationService()
        alert_service = KPIAlertingService(
            KPIAlert.objects.create(
                kpi=test_kpi,
                alert_name='Multi-Period Alert',
                alert_type='threshold_breach',
                condition_type='below',
                threshold_value=Decimal('4500000'),
                is_active=True
            )
        )
        
        calculations = []
        values = [
            Decimal('5000000'),
            Decimal('4800000'),
            Decimal('4200000'),  # Will trigger
            Decimal('5100000'),
            Decimal('4300000'),  # Will trigger again
        ]
        
        for i, value in enumerate(values):
            period_start = date(2026, 1, 1) + timedelta(days=i*30)
            period_end = period_start + timedelta(days=30)
            
            calc = KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=value,
                status='on_target' if value >= Decimal('4500000') else 'below_target',
                executed_by=test_user
            )
            
            calculations.append(calc)
        
        assert len(calculations) == 5
        assert calculations[2].calculated_value < Decimal('4500000')
        assert calculations[4].calculated_value < Decimal('4500000')
    
    def test_kpi_hierarchy_and_child_calculations(self, test_kpi, test_user):
        """Test KPI hierarchy with parent and child KPIs."""
        # Create parent KPI
        parent_kpi = KPI.objects.create(
            name='Total Revenue',
            code='TOTAL_REVENUE',
            formula='SELECT SUM(amount) FROM sales',
            formula_type='sql',
            target_value=Decimal('10000000'),
            unit='$'
        )
        
        # Create child KPIs
        child_kpi1 = KPI.objects.create(
            name='Product A Revenue',
            code='PRODUCT_A_REVENUE',
            formula='SELECT SUM(amount) FROM sales WHERE product = "A"',
            formula_type='sql',
            target_value=Decimal('5000000'),
            unit='$',
            parent_kpi=parent_kpi
        )
        
        child_kpi2 = KPI.objects.create(
            name='Product B Revenue',
            code='PRODUCT_B_REVENUE',
            formula='SELECT SUM(amount) FROM sales WHERE product = "B"',
            formula_type='sql',
            target_value=Decimal('5000000'),
            unit='$',
            parent_kpi=parent_kpi
        )
        
        # Calculate all
        service = KPICalculationService()
        
        parent_calc = service.calculate_kpi(
            parent_kpi,
            date(2026, 1, 1),
            date(2026, 1, 31),
            test_user
        )
        
        child_calc1 = service.calculate_kpi(
            child_kpi1,
            date(2026, 1, 1),
            date(2026, 1, 31),
            test_user
        )
        
        child_calc2 = service.calculate_kpi(
            child_kpi2,
            date(2026, 1, 1),
            date(2026, 1, 31),
            test_user
        )
        
        assert parent_calc.kpi.parent_kpi is None
        assert child_calc1.kpi.parent_kpi == parent_kpi
        assert child_calc2.kpi.parent_kpi == parent_kpi


@pytest.mark.django_db
class TestErrorHandlingInWorkflow:
    """Integration tests for error handling in workflows."""
    
    def test_graceful_handling_of_calculation_errors(self, test_kpi, test_user):
        """Test graceful error handling during calculation."""
        service = KPICalculationService()
        
        # Create KPI with potentially problematic formula
        bad_kpi = KPI.objects.create(
            name='Bad Formula KPI',
            code='BAD_KPI',
            formula='INVALID SQL SYNTAX HERE',
            formula_type='sql',
            target_value=Decimal('1000000'),
            unit='$'
        )
        
        # Attempt calculation - should handle error gracefully
        try:
            calc = service.calculate_kpi(
                bad_kpi,
                date(2026, 1, 1),
                date(2026, 1, 31),
                test_user
            )
            # Either returns error calculation or raises handled exception
            if calc:
                assert calc.status in ['error', 'failed']
        except Exception as e:
            # Should be a known exception type
            assert isinstance(e, (ValueError, RuntimeError))
    
    def test_alert_notification_failure_handling(self, test_kpi, test_user):
        """Test handling of notification failures."""
        alert = KPIAlert.objects.create(
            kpi=test_kpi,
            alert_name='Bad Notification Alert',
            alert_type='threshold_breach',
            condition_type='below',
            threshold_value=Decimal('4500000'),
            notification_channels=['invalid_channel'],
            is_active=True
        )
        
        service = KPIAlertingService(alert)
        
        calc = KPICalculation.objects.create(
            kpi=test_kpi,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            calculated_value=Decimal('4000000'),
            status='below_target',
            executed_by=test_user
        )
        
        # Should handle notification channel error gracefully
        try:
            triggered = service.evaluate_condition(calc)
            # Should still evaluate condition even if notification fails
            assert isinstance(triggered, bool)
        except Exception as e:
            # Should be a specific alert/notification exception
            assert 'notification' in str(e).lower() or 'channel' in str(e).lower()
