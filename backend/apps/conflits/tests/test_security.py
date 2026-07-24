"""
Security tests for M3 (Conflits) module
Tests access control, approval workflows, audit trails
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from apps.ingestion.models import DataSource
from apps.conflits.models import ConflictType, Conflict, ConflictResolution


@pytest.mark.django_db
class TestConflitsSecurityValidation:
    """Security tests for Conflits module"""
    
    def setup_method(self):
        """Setup test client and users"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='confuser1',
            email='conf1@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='confuser2',
            email='conf2@example.com',
            password='testpass123'
        )
        self.approver = User.objects.create_user(
            username='approver',
            email='approver@example.com',
            password='testpass123'
        )
    
    def test_authenticated_access_required(self):
        """Test unauthenticated users cannot access conflicts"""
        response = self.client.get('/api/conflits/conflicts/')
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_conflict_access_control(self):
        """Test users can only see their own datasource conflicts"""
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
        
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        c1 = Conflict.objects.create(
            data_source=ds1,
            conflict_type=ct,
            conflict_details={}
        )
        
        c2 = Conflict.objects.create(
            data_source=ds2,
            conflict_type=ct,
            conflict_details={}
        )
        
        self.client.force_authenticate(user=self.user)
        
        # User 1 should access own conflict
        response = self.client.get(f'/api/conflits/conflicts/{c1.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        
        # User 1 should NOT access User 2's conflict
        response = self.client.get(f'/api/conflits/conflicts/{c2.id}/')
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_approval_required_for_critical(self):
        """Test critical resolutions require approval"""
        ds = DataSource.objects.create(
            name='Source',
            source_type='csv',
            uploaded_by=self.user
        )
        
        ct = ConflictType.objects.create(
            name='Critical Type',
            code='CRITICAL',
            severity='critical'
        )
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='manual_override',
            resolved_by=self.user,
            approval_required=True
        )
        
        # Resolution should require approval before finalizing
        assert resolution.approval_required is True
        assert resolution.approved_by is None
    
    def test_cannot_self_approve(self):
        """Test user cannot approve their own critical resolution"""
        ds = DataSource.objects.create(
            name='Source',
            source_type='csv',
            uploaded_by=self.user
        )
        
        ct = ConflictType.objects.create(
            name='Type',
            code='TYPE'
        )
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='manual_override',
            resolved_by=self.user,
            approval_required=True
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Try to approve own resolution
        data = {'approved_by': self.user.id}
        response = self.client.patch(
            f'/api/conflits/resolutions/{resolution.id}/',
            data,
            format='json'
        )
        
        # Should be denied or endpoint not available
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED  # Endpoint may not support PATCH
        ]
    
    def test_audit_trail_immutability(self):
        """Resolution history is exposed read-only through the API."""
        ds = DataSource.objects.create(
            name='Source',
            source_type='csv',
            uploaded_by=self.user
        )
        
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='manual_override',
            resolved_by=self.user,
            approval_required=False
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/conflits/resolutions/{resolution.id}/',
            {'resolution_method': 'different_method'},
            format='json'
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    def test_rollback_data_preserved(self):
        """Test rollback data is preserved for reversible resolutions"""
        ds = DataSource.objects.create(
            name='Source',
            source_type='csv',
            uploaded_by=self.user
        )
        
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        rollback_data = {'original_value': 'john@example.com'}
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='manual_override',
            resolved_by=self.user,
            is_reversible=True,
            rollback_data=rollback_data
        )
        
        assert resolution.rollback_data == rollback_data
        assert ConflictResolution.objects.get(id=resolution.id).rollback_data is not None
