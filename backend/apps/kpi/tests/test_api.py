"""
Tests for KPI REST API endpoints.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from rest_framework import status
from rest_framework.test import APIClient
from django.urls import reverse
from apps.kpi.models import KPI, KPICalculation, KPIAlert


@pytest.mark.django_db
class TestKPIViewSet:
    """Tests for KPI API endpoints."""
    
    def test_list_kpis(self, authenticated_client, test_kpi):
        """Test listing KPIs."""
        response = authenticated_client.get('/api/kpi/kpis/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) >= 1
    
    def test_list_kpis_with_filters(self, authenticated_client, test_kpi):
        """Test listing KPIs with filters."""
        response = authenticated_client.get('/api/kpi/kpis/?category=Financial')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_create_kpi(self, analyst_client, test_user):
        """Test creating a KPI."""
        data = {
            'name': 'New KPI',
            'code': 'NEW_KPI',
            'formula': 'SELECT SUM(amount) FROM table',
            'formula_type': 'sql',
            'target_value': '1000000',
            'unit': '$',
            'frequency': 'monthly',
            'category': 'Financial'
        }
        
        response = analyst_client.post('/api/kpi/kpis/', data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New KPI'
        assert response.data['code'] == 'NEW_KPI'
    
    def test_retrieve_kpi(self, authenticated_client, test_kpi):
        """Test retrieving a single KPI."""
        response = authenticated_client.get(f'/api/kpi/kpis/{test_kpi.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == test_kpi.name
        assert response.data['code'] == test_kpi.code
    
    def test_update_kpi(self, analyst_client, test_kpi):
        """Test updating a KPI."""
        data = {
            'name': 'Updated KPI Name',
            'code': test_kpi.code,
            'formula': test_kpi.formula,
            'formula_type': test_kpi.formula_type,
            'target_value': '2000000',
            'unit': '$',
            'frequency': 'monthly'
        }
        
        response = analyst_client.put(
            f'/api/kpi/kpis/{test_kpi.id}/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated KPI Name'
    
    def test_delete_kpi(self, analyst_client, test_kpi):
        """Test deleting a KPI."""
        response = analyst_client.delete(f'/api/kpi/kpis/{test_kpi.id}/')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not KPI.objects.filter(id=test_kpi.id).exists()
    
    def test_calculate_kpi_now(self, analyst_client, test_kpi):
        """Test manual KPI calculation endpoint."""
        response = analyst_client.post(
            f'/api/kpi/kpis/{test_kpi.id}/calculate_now/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'success' in response.data or 'error' in response.data
    
    def test_kpi_history(self, authenticated_client, test_kpi, test_user):
        """Test KPI history endpoint."""
        # Create some history
        for i in range(3):
            period_end = date.today() - timedelta(days=i*30)
            period_start = period_end - timedelta(days=30)
            KPICalculation.objects.create(
                kpi=test_kpi,
                period_start=period_start,
                period_end=period_end,
                calculated_value=Decimal('5000000.0000'),
                status='on_target',
                executed_by=test_user
            )
        
        response = authenticated_client.get(f'/api/kpi/kpis/{test_kpi.id}/history/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'calculations' in response.data
    
    def test_kpi_anomaly_detection(self, authenticated_client, test_kpi):
        """Test anomaly detection endpoint."""
        response = authenticated_client.get(
            f'/api/kpi/kpis/{test_kpi.id}/anomaly_detection/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'has_anomaly' in response.data or 'error' in response.data
    
    def test_kpi_forecast(self, authenticated_client, test_kpi):
        """Test KPI forecast endpoint."""
        response = authenticated_client.get(
            f'/api/kpi/kpis/{test_kpi.id}/forecast/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'success' in response.data or 'error' in response.data
    
    def test_kpi_variance_analysis(self, authenticated_client, test_kpi):
        """Test variance analysis endpoint."""
        response = authenticated_client.get(
            f'/api/kpi/kpis/{test_kpi.id}/variance_analysis/'
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_batch_calculate_kpis(self, analyst_client, test_kpi):
        """Test batch KPI calculation."""
        data = {
            'kpi_ids': [test_kpi.id],
            'period_start': '2026-01-01',
            'period_end': '2026-01-31'
        }
        
        response = analyst_client.post(
            '/api/kpi/kpis/batch_calculate/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or 'status' in response.data


@pytest.mark.django_db
class TestKPICalculationViewSet:
    """Tests for KPI Calculation API endpoints."""
    
    def test_list_calculations(self, authenticated_client, test_kpi_calculation):
        """Test listing KPI calculations."""
        response = authenticated_client.get('/api/kpi/calculations/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_list_calculations_filter_by_kpi(self, authenticated_client, test_kpi_calculation):
        """Test filtering calculations by KPI."""
        response = authenticated_client.get(
            f'/api/kpi/calculations/?kpi_id={test_kpi_calculation.kpi.id}'
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_list_calculations_filter_by_status(self, authenticated_client, test_kpi_calculation):
        """Test filtering calculations by status."""
        response = authenticated_client.get(
            '/api/kpi/calculations/?status=on_target'
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_calculation(self, authenticated_client, test_kpi_calculation):
        """Test retrieving a single calculation."""
        response = authenticated_client.get(
            f'/api/kpi/calculations/{test_kpi_calculation.id}/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['calculated_value'] == str(test_kpi_calculation.calculated_value)


@pytest.mark.django_db
class TestKPIAlertViewSet:
    """Tests for KPI Alert API endpoints."""
    
    def test_list_alerts(self, authenticated_client, test_kpi_alert):
        """Test listing alerts."""
        response = authenticated_client.get('/api/kpi/alerts/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_create_alert(self, analyst_client, test_kpi):
        """Test creating an alert."""
        data = {
            'kpi': test_kpi.id,
            'alert_name': 'New Alert',
            'alert_type': 'threshold_breach',
            'condition_type': 'below',
            'threshold_value': '4500000',
            'notification_channels': ['email'],
            'recipients': ['test@example.com']
        }
        
        response = analyst_client.post('/api/kpi/alerts/', data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['alert_name'] == 'New Alert'
    
    def test_retrieve_alert(self, authenticated_client, test_kpi_alert):
        """Test retrieving an alert."""
        response = authenticated_client.get(f'/api/kpi/alerts/{test_kpi_alert.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['alert_name'] == test_kpi_alert.alert_name
    
    def test_update_alert(self, analyst_client, test_kpi_alert):
        """Test updating an alert."""
        data = {
            'alert_name': 'Updated Alert',
            'kpi': test_kpi_alert.kpi.id,
            'alert_type': test_kpi_alert.alert_type,
            'condition_type': test_kpi_alert.condition_type,
            'threshold_value': '4500000',
            'notification_channels': ['email'],
            'recipients': ['updated@example.com']
        }
        
        response = analyst_client.put(
            f'/api/kpi/alerts/{test_kpi_alert.id}/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_delete_alert(self, analyst_client, test_kpi_alert):
        """Test deleting an alert."""
        response = analyst_client.delete(f'/api/kpi/alerts/{test_kpi_alert.id}/')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_acknowledge_alert(self, analyst_client, test_kpi_alert):
        """Test acknowledging an alert."""
        data = {
            'notes': 'Alert acknowledged and issue resolved'
        }
        
        response = analyst_client.post(
            f'/api/kpi/alerts/{test_kpi_alert.id}/acknowledge/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_alerts_by_status(self, authenticated_client, test_kpi_alert):
        """Test filtering alerts by active status."""
        response = authenticated_client.get('/api/kpi/alerts/?is_active=true')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_triggered_recently(self, authenticated_client, test_kpi_alert):
        """Test getting recently triggered alerts."""
        response = authenticated_client.get('/api/kpi/alerts/triggered_recently/')
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestKPIDashboardAPI:
    """Tests for KPI Dashboard API."""
    
    def test_dashboard_endpoint(self, authenticated_client, test_kpi):
        """Test dashboard aggregation endpoint."""
        response = authenticated_client.get('/api/kpi/dashboard/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total_kpis' in response.data
        assert 'by_category' in response.data or 'success' in response.data


@pytest.mark.django_db
class TestKPIPermissions:
    """Tests for KPI API permissions."""
    
    def test_unauthenticated_access_denied(self, api_client):
        """Test that unauthenticated users can't access API."""
        response = api_client.get('/api/kpi/kpis/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authenticated_access_allowed(self, authenticated_client, test_kpi):
        """Test that authenticated users can access API."""
        response = authenticated_client.get('/api/kpi/kpis/')
        
        assert response.status_code == status.HTTP_200_OK
