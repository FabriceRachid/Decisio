"""
Shared pytest fixtures and configuration for all tests.
"""
import pytest
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
from apps.kpi.models import KPI, KPICalculation, KPIAlert


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def analyst_user(db):
    """Create an analyst user."""
    user = User.objects.create_user(
        username='analyst',
        email='analyst@example.com',
        password='analystpass123'
    )
    user.profile.role = 'analyst'
    user.profile.save(update_fields=['role'])
    return user


@pytest.fixture
def test_kpi(db, test_user):
    """Create a test KPI."""
    return KPI.objects.create(
        name='Test Revenue KPI',
        code='TEST_REV',
        description='Test revenue KPI',
        formula='SELECT SUM(amount) FROM nettoyage_cleaneddata WHERE date BETWEEN \'{period_start}\' AND \'{period_end}\'',
        formula_type='sql',
        target_value=Decimal('5000000.0000'),
        operator='>=',
        unit='$',
        frequency='monthly',
        category='Financial',
        source_table='nettoyage_cleaneddata',
        measure_column='amount',
        owner=test_user,
        is_active=True,
        warning_threshold=Decimal('4500000.0000'),
        critical_threshold=Decimal('4000000.0000'),
        aggregation_method='SUM'
    )


@pytest.fixture
def test_kpi_calculation(db, test_kpi, test_user):
    """Create a test KPI calculation."""
    period_end = date.today()
    period_start = period_end - timedelta(days=30)
    
    return KPICalculation.objects.create(
        kpi=test_kpi,
        period_start=period_start,
        period_end=period_end,
        period_label='Test Period',
        calculated_value=Decimal('4850000.0000'),
        previous_value=Decimal('5000000.0000'),
        variance_absolute=Decimal('-150000.0000'),
        variance_percent=Decimal('-3.00'),
        target_variance=Decimal('-150000.0000'),
        status='on_target',
        breakdown={},
        calculation_method='automatic',
        data_quality_score=Decimal('92.50'),
        rows_processed=1250,
        execution_time_ms=850,
        executed_by=test_user
    )


@pytest.fixture
def test_kpi_alert(db, test_kpi, test_user):
    """Create a test KPI alert."""
    return KPIAlert.objects.create(
        kpi=test_kpi,
        alert_name='Test Revenue Alert',
        alert_type='threshold_breach',
        condition_type='below',
        threshold_value=Decimal('4500000.0000'),
        notification_channels=['email'],
        recipients=['test@example.com'],
        is_active=True,
        cooldown_minutes=60,
        created_by=test_user
    )


@pytest.fixture
def api_client():
    """Return Django REST framework test client."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Return authenticated API client."""
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def analyst_client(api_client, analyst_user):
    """Return authenticated API client for analyst actions."""
    api_client.force_authenticate(user=analyst_user)
    return api_client
