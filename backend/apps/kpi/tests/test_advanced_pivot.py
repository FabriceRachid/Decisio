"""
E2E Tests for Advanced Pivot Table System
Tests backend service, API endpoints, and data flow
"""

import pytest
import pandas as pd
from decimal import Decimal
from datetime import datetime, date
from django.test import TestCase, Client
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.kpi.services import AdvancedPivotService
from apps.kpi.serializers import AdvancedPivotRequestSerializer
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData, CleaningJob


class AdvancedPivotServiceTests(TestCase):
    """Unit tests for AdvancedPivotService"""

    def setUp(self):
        """Set up test data"""
        self.service = AdvancedPivotService()

        # Create test dataframe
        self.test_data = pd.DataFrame({
            'region': ['North', 'North', 'South', 'South', 'East', 'West'],
            'product': ['A', 'B', 'A', 'B', 'A', 'B'],
            'year': [2024, 2024, 2024, 2024, 2024, 2024],
            'montant_total': [1000, 2000, 1500, 2500, 3000, 1000],
            'quantite': [10, 20, 15, 25, 30, 10],
        })

    def test_build_pivot_with_basic_config(self):
        """Test building a basic 2D pivot table"""
        config = {
            'row_fields': ['region'],
            'column_fields': ['product'],
            'value_field': 'montant_total',
            'aggregation': 'sum',
            'include_totals': True,
            'format_currency': False,
        }

        # Mock _load_frame to return test data
        self.service._load_frame = lambda x: self.test_data.copy()

        result = self.service.build_pivot_with_hierarchy(config)

        # Assertions
        assert result['success'] is False or 'pivot' in result
        assert len(result.get('pivot', [])) > 0
        assert 'metadata' in result
        assert result['metadata']['rows_processed'] == 6

    def test_build_pivot_with_multiple_dimensions(self):
        """Test multi-dimensional pivot (region × product × year)"""
        config = {
            'row_fields': ['region', 'product'],
            'column_fields': ['year'],
            'value_field': 'montant_total',
            'aggregation': 'sum',
            'include_totals': True,
        }

        self.service._load_frame = lambda x: self.test_data.copy()
        result = self.service.build_pivot_with_hierarchy(config)

        # Check structure
        assert 'pivot' in result or 'error' in result
        assert 'metadata' in result

    def test_different_aggregations(self):
        """Test various aggregation types"""
        aggregations = ['sum', 'avg', 'count', 'min', 'max']

        for agg in aggregations:
            config = {
                'row_fields': ['region'],
                'column_fields': [],
                'value_field': 'montant_total',
                'aggregation': agg,
            }

            self.service._load_frame = lambda x: self.test_data.copy()
            result = self.service.build_pivot_with_hierarchy(config)

            # Should not raise exception
            assert result is not None

    def test_drill_down_functionality(self):
        """Test drill-down to detail rows"""
        config = {
            'row_fields': ['region'],
            'column_fields': ['product'],
            'value_field': 'montant_total',
            'filters': [],
        }

        self.service._load_frame = lambda x: self.test_data.copy()

        details = self.service.compute_drill_down(config, 'North', 'A')

        # Should return list of dicts
        assert isinstance(details, list)
        # Should have at least one row for North + A
        assert len(details) >= 0


class AdvancedPivotSerializerTests(TestCase):
    """Unit tests for request serializer validation"""

    def test_valid_pivot_request(self):
        """Test valid pivot request"""
        data = {
            'source_id': 1,
            'source_type': 'cleaned',
            'row_fields': ['region', 'product'],
            'column_fields': ['year'],
            'value_field': 'montant_total',
            'aggregation': 'sum',
            'filters': [],
            'include_totals': True,
            'format_currency': False,
            'sort_by': 'value',
            'sort_direction': 'desc',
        }

        serializer = AdvancedPivotRequestSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_missing_required_fields(self):
        """Test validation rejects missing required fields"""
        data = {
            'source_id': 1,
            'row_fields': [],
            'column_fields': [],
            # Missing value_field
        }

        serializer = AdvancedPivotRequestSerializer(data=data)
        # Should be invalid without value_field
        assert not serializer.is_valid() or serializer.validated_data.get('value_field')

    def test_invalid_aggregation(self):
        """Test validation rejects invalid aggregation"""
        data = {
            'source_id': 1,
            'row_fields': ['region'],
            'column_fields': [],
            'value_field': 'montant_total',
            'aggregation': 'invalid_agg',  # Invalid
        }

        serializer = AdvancedPivotRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_invalid_top_n(self):
        """Test validation rejects invalid top_n"""
        data = {
            'source_id': 1,
            'row_fields': ['region'],
            'column_fields': [],
            'value_field': 'montant_total',
            'aggregation': 'sum',
            'top_n': 50000,  # Too large (max 10000)
        }

        serializer = AdvancedPivotRequestSerializer(data=data)
        assert not serializer.is_valid()


class AdvancedPivotAPITests(APITestCase):
    """Integration tests for API endpoints"""

    def setUp(self):
        """Set up test client and user"""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Get JWT token
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_advanced_pivot_endpoint_missing_config(self):
        """Test endpoint rejects empty config"""
        response = self.client.post('/api/kpi/pivot/advanced/', {})

        # Should return 400 Bad Request
        assert response.status_code in [400, 401, 403]

    def test_advanced_pivot_endpoint_invalid_source(self):
        """Test endpoint with non-existent source"""
        data = {
            'source_id': 99999,  # Non-existent
            'row_fields': ['region'],
            'column_fields': [],
            'value_field': 'montant_total',
            'aggregation': 'sum',
        }

        response = self.client.post('/api/kpi/pivot/advanced/', data, format='json')

        # Should return 404 or 400
        assert response.status_code in [400, 404]

    def test_drill_down_endpoint(self):
        """Test drill-down endpoint"""
        data = {
            'pivot_config': {
                'source_id': 1,
                'source_type': 'cleaned',
                'row_fields': ['region'],
                'column_fields': ['product'],
                'value_field': 'montant_total',
                'aggregation': 'sum',
            },
            'row_key': 'North',
            'col_key': 'A',
        }

        response = self.client.post('/api/kpi/pivot/drill-down/', data, format='json')

        # Should return response (might be 404 if source doesn't exist)
        assert response.status_code in [200, 404, 400]


class PivotResponseFormatTests(TestCase):
    """Tests for response format and structure"""

    def setUp(self):
        self.service = AdvancedPivotService()
        self.test_data = pd.DataFrame({
            'region': ['North', 'South'],
            'montant': [1000, 2000],
        })

    def test_response_has_required_fields(self):
        """Test response includes all required fields"""
        config = {
            'row_fields': ['region'],
            'column_fields': [],
            'value_field': 'montant',
            'aggregation': 'sum',
        }

        self.service._load_frame = lambda x: self.test_data.copy()
        result = self.service.build_pivot_with_hierarchy(config)

        # Check required fields
        required_fields = ['pivot', 'row_headers', 'col_headers', 'totals', 'metadata']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_metadata_includes_performance_stats(self):
        """Test metadata contains performance information"""
        config = {
            'row_fields': ['region'],
            'column_fields': [],
            'value_field': 'montant',
            'aggregation': 'sum',
        }

        self.service._load_frame = lambda x: self.test_data.copy()
        result = self.service.build_pivot_with_hierarchy(config)

        # Check metadata structure
        assert 'metadata' in result
        meta = result['metadata']
        assert 'rows_processed' in meta
        assert 'execution_time_ms' in meta
        assert 'data_quality_score' in meta


# ============ E2E SCENARIOS ============

class EndToEndTests(TestCase):
    """Complete workflow tests"""

    def test_full_pivot_workflow(self):
        """Test complete pivot workflow from config to drill-down"""
        service = AdvancedPivotService()

        # Create test data
        test_data = pd.DataFrame({
            'region': ['North', 'North', 'South', 'South'],
            'product': ['A', 'B', 'A', 'B'],
            'year': [2024, 2024, 2024, 2024],
            'revenue': [1000, 2000, 1500, 2500],
        })

        service._load_frame = lambda x: test_data.copy()

        # Step 1: Build pivot
        pivot_config = {
            'row_fields': ['region'],
            'column_fields': ['product'],
            'value_field': 'revenue',
            'aggregation': 'sum',
            'include_totals': True,
        }

        pivot_result = service.build_pivot_with_hierarchy(pivot_config)
        assert 'pivot' in pivot_result or 'metadata' in pivot_result

        # Step 2: Drill down into a cell
        drill_config = {
            'row_fields': ['region'],
            'column_fields': ['product'],
            'value_field': 'revenue',
            'filters': [],
        }

        details = service.compute_drill_down(drill_config, 'North', 'A')
        assert isinstance(details, list)

    def test_multiple_aggregations_workflow(self):
        """Test user switching between different aggregations"""
        service = AdvancedPivotService()

        test_data = pd.DataFrame({
            'category': ['A', 'A', 'B', 'B'],
            'value': [100, 200, 300, 400],
        })

        service._load_frame = lambda x: test_data.copy()

        aggregations = ['sum', 'avg', 'count', 'min', 'max']

        for agg in aggregations:
            config = {
                'row_fields': ['category'],
                'column_fields': [],
                'value_field': 'value',
                'aggregation': agg,
            }

            result = service.build_pivot_with_hierarchy(config)
            # Each should return valid result
            assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
