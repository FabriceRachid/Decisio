"""
API tests for M3 (Conflits) module.
These tests assert real endpoint behavior for detection, assignment, resolution,
and access scoping instead of permissive status-code checks.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from apps.conflits.models import ActivityLog, Conflict, ConflictResolution, ConflictType
from apps.ingestion.models import DataSource, RawData


@pytest.mark.django_db
class TestConflictTypeAPIEndpoints:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='confapi',
            email='conf@example.com',
            password='testpass123',
        )
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        self.client.force_authenticate(user=self.user)

    def test_list_conflict_types(self):
        ConflictType.objects.create(name='Type 1', code='TYPE1')
        ConflictType.objects.create(name='Type 2', code='TYPE2')

        response = self.client.get('/api/conflits/types/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert {item['code'] for item in response.data['results']} == {'TYPE1', 'TYPE2'}

    def test_get_conflict_type_detail(self):
        conflict_type = ConflictType.objects.create(name='Test Type', code='TEST')

        response = self.client.get(f'/api/conflits/types/{conflict_type.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == conflict_type.id
        assert response.data['code'] == 'TEST'


@pytest.mark.django_db
class TestConflictAPIEndpoints:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='confuser',
            email='confuser@example.com',
            password='testpass123',
        )
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        self.client.force_authenticate(user=self.user)

        self.datasource = DataSource.objects.create(
            name='Test Source',
            source_type='csv',
            uploaded_by=self.user,
        )
        self.conflict_type = ConflictType.objects.create(
            name='Duplicate Records',
            code='DUPLICATE_RECORDS',
            severity='high',
        )

    def test_list_conflicts(self):
        Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={'issue': 'duplicate'},
            description='Found duplicate rows',
        )

        response = self.client.get('/api/conflits/conflicts/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['conflict_type_code'] == 'DUPLICATE_RECORDS'

    def test_get_conflict_detail(self):
        conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={'issue': 'test'},
            affected_columns=['email'],
        )

        response = self.client.get(f'/api/conflits/conflicts/{conflict.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == conflict.id
        assert response.data['affected_columns'] == ['email']

    def test_acknowledge_conflict(self):
        conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={},
        )

        response = self.client.post(
            f'/api/conflits/conflicts/{conflict.id}/acknowledge/',
            {},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        conflict.refresh_from_db()
        assert conflict.acknowledged_by == self.user
        assert conflict.status == 'investigating'

    def test_assign_conflict(self):
        assignee = User.objects.create_user(
            username='assignee',
            email='assign@example.com',
            password='pass',
        )
        assignee.profile.role = 'analyst'
        assignee.profile.save(update_fields=['role'])

        conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={},
        )

        response = self.client.post(
            f'/api/conflits/conflicts/{conflict.id}/assign/',
            {'assigned_to_id': assignee.id},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        conflict.refresh_from_db()
        assert conflict.assigned_to == assignee

    def test_filter_by_status(self):
        Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={},
            status='detected',
        )
        Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={},
            status='resolved',
        )

        response = self.client.get('/api/conflits/conflicts/?status=detected')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['status'] == 'detected'

    def test_detect_endpoint_creates_duplicate_conflict_and_audit_log(self):
        RawData.objects.bulk_create([
            RawData(
                source=self.datasource,
                row_number=1,
                data={'email': 'a@example.com', 'amount': '10'},
                validation_status='valid',
            ),
            RawData(
                source=self.datasource,
                row_number=2,
                data={'email': 'a@example.com', 'amount': '10'},
                validation_status='valid',
            ),
        ])

        response = self.client.post(
            '/api/conflits/detect/',
            {'source_id': self.datasource.id, 'check_types': ['DUPLICATE_RECORDS']},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_conflicts'] == 1
        assert response.data['by_type']['DUPLICATE_RECORDS'] == 1
        assert len(response.data['conflicts']) == 1
        assert response.data['conflicts'][0]['conflict_type_code'] == 'DUPLICATE_RECORDS'
        assert ActivityLog.objects.filter(
            resource_type='ConflictDetection',
            resource_id=self.datasource.id,
        ).exists()

    def test_detect_endpoint_is_idempotent_for_same_source_signature(self):
        RawData.objects.bulk_create([
            RawData(
                source=self.datasource,
                row_number=1,
                data={'email': 'dup@example.com', 'amount': '10'},
                validation_status='valid',
            ),
            RawData(
                source=self.datasource,
                row_number=2,
                data={'email': 'dup@example.com', 'amount': '10'},
                validation_status='valid',
            ),
        ])

        first = self.client.post(
            '/api/conflits/detect/',
            {'source_id': self.datasource.id, 'check_types': ['DUPLICATE_RECORDS']},
            format='json',
        )
        second = self.client.post(
            '/api/conflits/detect/',
            {'source_id': self.datasource.id, 'check_types': ['DUPLICATE_RECORDS']},
            format='json',
        )

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert Conflict.objects.filter(
            data_source=self.datasource,
            conflict_type__code='DUPLICATE_RECORDS',
        ).count() == 1

    def test_detect_endpoint_creates_business_key_conflict(self):
        RawData.objects.bulk_create([
            RawData(
                source=self.datasource,
                row_number=1,
                data={
                    'id_commande': 'CMD-1',
                    'client': 'Client A',
                    'date': '2026-05-20',
                    'montant_total': '100',
                    'status': 'draft',
                },
                validation_status='valid',
            ),
            RawData(
                source=self.datasource,
                row_number=2,
                data={
                    'id_commande': 'CMD-1',
                    'client': 'Client A',
                    'date': '2026-05-20',
                    'montant_total': '100',
                    'status': 'approved',
                },
                validation_status='valid',
            ),
        ])

        response = self.client.post(
            '/api/conflits/detect/',
            {'source_id': self.datasource.id, 'check_types': ['DUPLICATE_RECORDS']},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_conflicts'] == 1
        assert response.data['by_type']['BUSINESS_CONFLICT'] == 1
        assert response.data['conflicts'][0]['conflict_type_code'] == 'BUSINESS_CONFLICT'

    def test_resolve_conflict_creates_resolution_and_updates_status(self):
        conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={'issue': 'test'},
        )

        response = self.client.post(
            f'/api/conflits/conflicts/{conflict.id}/resolve/',
            {
                'resolution_method': 'manual_override',
                'chosen_value': {'winner': 'row_1'},
                'resolution_notes': 'Keep first row',
                'requires_approval': False,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        conflict.refresh_from_db()
        resolution = ConflictResolution.objects.get(conflict=conflict)
        assert conflict.status == 'resolved'
        assert resolution.chosen_value == {'winner': 'row_1'}
        assert resolution.rollback_data['previous_status'] == 'detected'

    def test_critical_resolution_can_stay_pending_approval(self):
        critical_type = ConflictType.objects.create(
            name='Critical Conflict',
            code='CRITICAL_CONFLICT',
            severity='critical',
        )
        conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=critical_type,
            conflict_details={'issue': 'critical'},
        )

        response = self.client.post(
            f'/api/conflits/conflicts/{conflict.id}/resolve/',
            {
                'resolution_method': 'manual_override',
                'chosen_value': {'winner': 'row_2'},
                'resolution_notes': 'Needs manager review',
                'requires_approval': True,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        conflict.refresh_from_db()
        assert conflict.status == 'resolving'
        assert ConflictResolution.objects.filter(
            conflict=conflict,
            approval_required=True,
        ).count() == 1

    def test_bulk_action_cannot_update_inaccessible_conflicts(self):
        other_user = User.objects.create_user(
            username='otherconfuser',
            email='otherconfuser@example.com',
            password='testpass123',
        )
        other_user.profile.role = 'analyst'
        other_user.profile.save(update_fields=['role'])

        other_source = DataSource.objects.create(
            name='Other Source',
            source_type='csv',
            uploaded_by=other_user,
        )

        own_conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={},
            status='detected',
        )
        other_conflict = Conflict.objects.create(
            data_source=other_source,
            conflict_type=self.conflict_type,
            conflict_details={},
            status='detected',
        )

        response = self.client.post(
            '/api/conflits/conflicts/bulk_action/',
            {
                'conflict_ids': [own_conflict.id, other_conflict.id],
                'action': 'change_status',
                'new_status': 'ignored',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestConflictResolutionAPIEndpoints:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='resuser',
            email='res@example.com',
            password='testpass123',
        )
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        self.client.force_authenticate(user=self.user)

        self.datasource = DataSource.objects.create(
            name='Test Source',
            source_type='csv',
            uploaded_by=self.user,
        )
        self.conflict_type = ConflictType.objects.create(name='Type', code='TYPE')
        self.conflict = Conflict.objects.create(
            data_source=self.datasource,
            conflict_type=self.conflict_type,
            conflict_details={},
        )

    def test_create_resolution_endpoint_is_read_only(self):
        response = self.client.post(
            '/api/conflits/resolutions/',
            {
                'conflict_id': self.conflict.id,
                'resolution_method': 'manual_override',
                'chosen_value': {'id': '123'},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_get_resolution_detail(self):
        resolution = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_method='manual_override',
            resolved_by=self.user,
        )

        response = self.client.get(f'/api/conflits/resolutions/{resolution.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == resolution.id
        assert response.data['resolved_by_username'] == self.user.username

    def test_review_resolution_endpoint_is_read_only(self):
        resolution = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_method='manual_override',
            resolved_by=self.user,
            approval_required=True,
        )

        response = self.client.patch(
            f'/api/conflits/resolutions/{resolution.id}/',
            {'reviewed_by': self.user.id},
            format='json',
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
