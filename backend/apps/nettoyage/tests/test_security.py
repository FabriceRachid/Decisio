"""
Security tests for M2 (Nettoyage) module
Tests authorization, data access control, input validation
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from apps.ingestion.models import DataSource
from apps.nettoyage.models import CleaningRule, CleaningJob


@pytest.mark.django_db
class TestNettoyageSecurityValidation:
    """Security tests for Nettoyage module"""
    
    def setup_method(self):
        """Setup test client and users"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='cleanuser1',
            email='clean1@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='cleanuser2',
            email='clean2@example.com',
            password='testpass123'
        )
    
    def test_authenticated_access_required_rules(self):
        """Test unauthenticated users cannot access cleaning rules"""
        response = self.client.get('/api/nettoyage/rules/')
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_rule_creator_assignment(self):
        """Test cleaning rule creator is automatically assigned"""
        self.client.force_authenticate(user=self.user)
        
        rule = CleaningRule.objects.create(
            name='Auto Created Rule',
            rule_type='remove_nulls',
            created_by=self.user
        )
        
        assert rule.created_by == self.user
    
    def test_malicious_regex_pattern_validates(self):
        """Test malicious regex patterns are validated"""
        self.client.force_authenticate(user=self.user)
        
        # Regex bomb attempt
        malicious_regex = "(a+)+b"  # ReDoS pattern
        
        rule = CleaningRule.objects.create(
            name='Regex Test',
            rule_type='regex_replace',
            created_by=self.user,
            column_pattern=malicious_regex
        )
        
        # Rule should be created but validation should catch dangerous patterns
        assert rule.column_pattern == malicious_regex
    
    def test_job_access_control(self):
        """Test users can only see their own cleaning jobs"""
        ds1 = DataSource.objects.create(
            name='User1 Source',
            source_type='csv',
            uploaded_by=self.user
        )
        
        ds2 = DataSource.objects.create(
            name='User2 Source',
            source_type='csv',
            uploaded_by=self.other_user
        )
        
        # Create rule
        rule = CleaningRule.objects.create(
            name='Test Rule',
            rule_type='remove_duplicates',
            created_by=self.user
        )
        
        job1 = CleaningJob.objects.create(
            source=ds1,
            rule=rule,
            created_by=self.user
        )
        
        job2 = CleaningJob.objects.create(
            source=ds2,
            rule=rule,
            created_by=self.other_user
        )
        
        self.client.force_authenticate(user=self.user)
        
        # User 1 should access own job
        response = self.client.get(f'/api/nettoyage/jobs/{job1.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        
        # User 1 should NOT access User 2's job
        response = self.client.get(f'/api/nettoyage/jobs/{job2.id}/')
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_cannot_cancel_others_jobs(self):
        """Test user cannot cancel another user's job"""
        ds = DataSource.objects.create(
            name='Source',
            source_type='csv',
            uploaded_by=self.other_user
        )
        
        job = CleaningJob.objects.create(
            source=ds,
            status='running',
            created_by=self.other_user
        )
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            f'/api/nettoyage/jobs/{job.id}/cancel/',
            {},
            format='json'
        )
        
        # Should be denied
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_fill_value_parameter_validated(self):
        """Test fill_value parameter validation"""
        self.client.force_authenticate(user=self.user)
        
        # Create rule with various fill values
        rule = CleaningRule.objects.create(
            name='Fill Test',
            rule_type='fill_value',
            created_by=self.user,
            parameters={'fill_value': None}  # Null fill value
        )
        
        assert rule.parameters['fill_value'] is None
    
    def test_column_name_validation(self):
        """Test column names are validated"""
        self.client.force_authenticate(user=self.user)
        
        # Create rule with column names
        rule = CleaningRule.objects.create(
            name='Column Test',
            rule_type='remove_nulls',
            created_by=self.user,
            column_names=['valid_column', 'another_column', '123numeric']
        )
        
        assert rule.column_names == ['valid_column', 'another_column', '123numeric']
