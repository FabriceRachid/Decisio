"""
Unit tests for M3 (Conflits) models
Tests ConflictType, Conflict, and ConflictResolution models
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from apps.ingestion.models import DataSource
from apps.conflits.models import ConflictType, Conflict, ConflictResolution


@pytest.mark.django_db
class TestConflictTypeModel:
    """Tests for ConflictType model"""
    
    def test_create_conflict_type_minimal(self):
        """Test creating ConflictType with minimal fields"""
        ct = ConflictType.objects.create(
            name='Duplicate Record',
            code='DUP_REC'
        )
        
        assert ct.name == 'Duplicate Record'
        assert ct.code == 'DUP_REC'
        assert ct.severity == 'medium'  # Default
        assert ct.auto_resolve is False  # Default
    
    def test_conflict_type_severity_choices(self):
        """Test ConflictType severity field"""
        severities = ['low', 'medium', 'high', 'critical']
        for i, severity in enumerate(severities):
            ct = ConflictType.objects.create(
                name=f'Type {i}',
                code=f'CODE{i}',
                severity=severity
            )
            assert ct.severity == severity
    
    def test_conflict_type_with_resolution_strategy(self):
        """Test ConflictType with resolution strategy"""
        ct = ConflictType.objects.create(
            name='Missing Data',
            code='MISS_DATA',
            auto_resolve=True,
            resolution_strategy='fill_mean'
        )
        
        assert ct.auto_resolve is True
        assert ct.resolution_strategy == 'fill_mean'
    
    def test_conflict_type_with_ui_config(self):
        """Test ConflictType with UI configuration"""
        ct = ConflictType.objects.create(
            name='Data Inconsistency',
            code='DATA_INCON',
            icon='warning',
            color_code='#FF6B6B',
            documentation_url='https://docs.example.com/conflicts'
        )
        
        assert ct.icon == 'warning'
        assert ct.color_code == '#FF6B6B'
        assert ct.documentation_url == 'https://docs.example.com/conflicts'


@pytest.mark.django_db
class TestConflictModel:
    """Tests for Conflict model"""
    
    def test_create_conflict_minimal(self):
        """Test creating Conflict with minimal fields"""
        user = User.objects.create_user(username='confuser1', email='conf1@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={'issue': 'duplicate records'}
        )
        
        assert conflict.data_source == ds
        assert conflict.conflict_type == ct
        assert conflict.status == 'detected'  # Default
        assert conflict.priority == 5  # Default
        assert conflict.detected_by == 'system'  # Default
    
    def test_conflict_status_choices(self):
        """Test Conflict status field"""
        user = User.objects.create_user(username='confuser2', email='conf2@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        statuses = ['detected', 'investigating', 'resolving', 'resolved', 'ignored']
        for i, status in enumerate(statuses):
            conflict = Conflict.objects.create(
                data_source=ds,
                conflict_type=ct,
                conflict_details={},
                status=status
            )
            assert conflict.status == status
    
    def test_conflict_with_assignment(self):
        """Test Conflict with assignment and acknowledgment"""
        user = User.objects.create_user(username='confuser3', email='conf3@example.com')
        assignee = User.objects.create_user(username='assignee', email='assign@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={},
            assigned_to=assignee,
            acknowledged_by=user,
            acknowledged_at=timezone.now()
        )
        
        assert conflict.assigned_to == assignee
        assert conflict.acknowledged_by == user
        assert conflict.acknowledged_at is not None
    
    def test_conflict_with_details(self):
        """Test Conflict with detailed information"""
        user = User.objects.create_user(username='confuser4', email='conf4@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        affected_columns = ['id', 'email']
        affected_row_ids = [1, 2, 3]
        details = {'issue': 'duplicate entries', 'count': 3}
        
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            affected_table='customers',
            affected_columns=affected_columns,
            affected_row_ids=affected_row_ids,
            conflict_details=details,
            description='Found 3 duplicate customer records',
            impact_score=Decimal('45.5'),
            priority=8
        )
        
        assert conflict.affected_table == 'customers'
        assert conflict.affected_columns == affected_columns
        assert conflict.affected_row_ids == affected_row_ids
        assert conflict.impact_score == Decimal('45.5')
        assert conflict.priority == 8


@pytest.mark.django_db
class TestConflictResolutionModel:
    """Tests for ConflictResolution model"""
    
    def test_create_conflict_resolution(self):
        """Test creating ConflictResolution"""
        user = User.objects.create_user(username='resuser1', email='res1@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='manual_override',
            chosen_value={'id': '123'},
            resolved_by=user
        )
        
        assert resolution.conflict == conflict
        assert resolution.resolution_method == 'manual_override'
        assert resolution.chosen_value == {'id': '123'}
        assert resolution.resolved_by == user
        assert resolution.is_reversible is True  # Default
    
    def test_conflict_resolution_methods(self):
        """Test ConflictResolution resolution_method field"""
        user = User.objects.create_user(username='resuser2', email='res2@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        
        methods = [
            'manual_override', 'auto_merge', 'default_value',
            'user_selected', 'majority_vote', 'latest_value', 'discard'
        ]
        
        for i, method in enumerate(methods):
            conflict = Conflict.objects.create(
                data_source=ds,
                conflict_type=ct,
                conflict_details={}
            )
            resolution = ConflictResolution.objects.create(
                conflict=conflict,
                resolution_method=method,
                resolved_by=user
            )
            assert resolution.resolution_method == method
    
    def test_conflict_resolution_with_variants(self):
        """Test ConflictResolution with alternative values"""
        user = User.objects.create_user(username='resuser3', email='res3@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        alternatives = [
            {'value': 'John', 'votes': 5},
            {'value': 'Jon', 'votes': 2},
            {'value': 'Jean', 'votes': 1}
        ]
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='majority_vote',
            alternative_values=alternatives,
            chosen_value='John',
            confidence_score=Decimal('71.4'),
            resolved_by=user
        )
        
        assert resolution.alternative_values == alternatives
        assert resolution.confidence_score == Decimal('71.4')
    
    def test_conflict_resolution_with_review(self):
        """Test ConflictResolution with review and approval"""
        user = User.objects.create_user(username='resuser4', email='res4@example.com')
        reviewer = User.objects.create_user(username='reviewer', email='review@example.com')
        approver = User.objects.create_user(username='approver', email='approve@example.com')
        
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        ct = ConflictType.objects.create(name='Type', code='TYPE')
        conflict = Conflict.objects.create(
            data_source=ds,
            conflict_type=ct,
            conflict_details={}
        )
        
        resolution = ConflictResolution.objects.create(
            conflict=conflict,
            resolution_method='manual_override',
            resolved_by=user,
            approval_required=True,
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
            approved_by=approver,
            approved_at=timezone.now()
        )
        
        assert resolution.approval_required is True
        assert resolution.reviewed_by == reviewer
        assert resolution.approved_by == approver
