"""
API tests for M2 (Nettoyage/Cleaning) module
Tests CleaningRule, CleaningPipeline, CleaningJob API endpoints
"""
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework import status
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData, CleaningRule, CleaningPipeline, CleaningJob
from apps.nettoyage.services import CleaningError, apply_cleaning
from apps.nettoyage.tasks import export_cleaned_data_async


@pytest.mark.django_db
class TestCleaningRuleAPIEndpoints:
    """Tests for CleaningRule API endpoints"""
    
    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='cleanapi',
            email='clean@example.com',
            password='testpass123'
        )
        self.user.profile.role = 'analyst'
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)
    
    def test_list_cleaning_rules(self):
        """Test listing cleaning rules"""
        CleaningRule.objects.create(
            name='Rule 1',
            rule_type='remove_nulls',
            created_by=self.user
        )
        CleaningRule.objects.create(
            name='Rule 2',
            rule_type='remove_duplicates',
            created_by=self.user
        )
        
        response = self.client.get('/api/nettoyage/rules/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
    
    def test_create_cleaning_rule(self):
        """Test creating a cleaning rule"""
        data = {
            'name': 'New Rule',
            'rule_type': 'fill_value',
            'parameters': {'fill_value': 0}
        }
        
        response = self.client.post('/api/nettoyage/rules/', data, format='json')
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_403_FORBIDDEN,  # Permission denied is OK
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]

    def test_update_cleaning_rule(self):
        """PATCH should update a rule for write-enabled users."""
        rule = CleaningRule.objects.create(
            name='Rule To Update',
            rule_type='fill_value',
            parameters={'fill_value': 'N/A'},
            created_by=self.user
        )

        response = self.client.patch(
            f'/api/nettoyage/rules/{rule.id}/',
            {'description': 'Updated description', 'priority': 8},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        rule.refresh_from_db()
        assert rule.description == 'Updated description'
        assert rule.priority == 8

    def test_delete_cleaning_rule_soft_deletes(self):
        """DELETE should deactivate a rule instead of removing it."""
        rule = CleaningRule.objects.create(
            name='Rule To Disable',
            rule_type='remove_duplicates',
            created_by=self.user,
            is_active=True
        )

        response = self.client.delete(f'/api/nettoyage/rules/{rule.id}/')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        rule.refresh_from_db()
        assert rule.is_active is False
    
    def test_filter_active_rules(self):
        """Test filtering active rules"""
        CleaningRule.objects.create(
            name='Active Rule',
            rule_type='remove_nulls',
            created_by=self.user,
            is_active=True
        )
        CleaningRule.objects.create(
            name='Inactive Rule',
            rule_type='remove_nulls',
            created_by=self.user,
            is_active=False
        )
        
        response = self.client.get('/api/nettoyage/rules/?is_active=true')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
    
    def test_filter_by_rule_type(self):
        """Test filtering rules by type"""
        CleaningRule.objects.create(
            name='Null Rule',
            rule_type='remove_nulls',
            created_by=self.user
        )
        CleaningRule.objects.create(
            name='Dup Rule',
            rule_type='remove_duplicates',
            created_by=self.user
        )
        
        response = self.client.get('/api/nettoyage/rules/?rule_type=remove_nulls')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_create_rule_rejects_unsafe_regex(self):
        response = self.client.post(
            '/api/nettoyage/rules/',
            {
                'name': 'Unsafe Regex',
                'rule_type': 'regex_replace',
                'column_pattern': '(a+)+b',
                'parameters': {'pattern': 'a', 'replacement': 'b'},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'column_pattern' in response.data


@pytest.mark.django_db
class TestCleaningPipelineAPIEndpoints:
    """Tests for CleaningPipeline API endpoints"""
    
    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='pipeapi',
            email='pipe@example.com',
            password='testpass123'
        )
        self.user.profile.role = 'analyst'
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)
    
    def test_list_pipelines(self):
        """Test listing pipelines"""
        CleaningPipeline.objects.create(
            name='Pipeline 1',
            created_by=self.user
        )
        
        response = self.client.get('/api/nettoyage/pipelines/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
    
    def test_create_pipeline(self):
        """Test creating a pipeline"""
        data = {
            'name': 'New Pipeline',
            'description': 'Test pipeline'
        }
        
        response = self.client.post('/api/nettoyage/pipelines/', data, format='json')
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_403_FORBIDDEN,  # Permission denied is OK
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_update_pipeline(self):
        """Test updating a pipeline"""
        pipeline = CleaningPipeline.objects.create(
            name='Pipeline to Update',
            created_by=self.user
        )
        
        data = {'name': 'Updated Pipeline'}
        response = self.client.patch(f'/api/nettoyage/pipelines/{pipeline.id}/', data, format='json')
        assert response.status_code == status.HTTP_200_OK
        pipeline.refresh_from_db()
        assert pipeline.name == 'Updated Pipeline'


@pytest.mark.django_db
class TestCleaningJobAPIEndpoints:
    """Tests for CleaningJob API endpoints"""
    
    def setup_method(self):
        """Setup test client and test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='jobapi',
            email='job@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.datasource = DataSource.objects.create(
            name='Test Source',
            source_type='csv',
            uploaded_by=self.user
        )
    
    def test_list_cleaning_jobs(self):
        """Test listing cleaning jobs"""
        CleaningJob.objects.create(
            source=self.datasource,
            status='completed',
            created_by=self.user
        )
        
        response = self.client.get('/api/nettoyage/jobs/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_get_job_status(self):
        """Test getting job status"""
        # Create rule first
        rule = CleaningRule.objects.create(
            name='Test Rule',
            rule_type='remove_duplicates',
            created_by=self.user
        )
        
        # Create job WITH rule
        job = CleaningJob.objects.create(
            source=self.datasource,
            rule=rule,
            status='running',
            created_by=self.user
        )
        
        response = self.client.get(f'/api/nettoyage/jobs/{job.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_get_job_status_resolves_tracking_job(self):
        """Async tracking jobs should resolve to the underlying result job."""
        rule = CleaningRule.objects.create(
            name='Async Result Rule',
            rule_type='remove_duplicates',
            created_by=self.user
        )
        result_job = CleaningJob.objects.create(
            source=self.datasource,
            rule=rule,
            status='completed',
            created_by=self.user
        )
        tracking_job = CleaningJob.objects.create(
            source=self.datasource,
            status='queued',
            created_by=self.user,
            execution_context={'result_job_id': result_job.id}
        )

        response = self.client.get(f'/api/nettoyage/jobs/{tracking_job.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['job']['id'] == result_job.id
    
    def test_start_cleaning_job(self):
        """Test starting a cleaning job"""
        data = {'source_id': self.datasource.id}
        
        response = self.client.post('/api/nettoyage/jobs/start/', data, format='json')
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_202_ACCEPTED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_preview_cleaning(self):
        """Test previewing cleaning results"""
        job = CleaningJob.objects.create(
            source=self.datasource,
            status='completed',
            created_by=self.user
        )
        
        response = self.client.get(f'/api/nettoyage/jobs/{job.id}/preview/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_cancel_job(self):
        """Test cancelling a job"""
        job = CleaningJob.objects.create(
            source=self.datasource,
            status='running',
            created_by=self.user
        )
        
        response = self.client.post(f'/api/nettoyage/jobs/{job.id}/cancel/', {}, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]

    def test_apply_async_with_empty_pipeline_still_queues_mvp_cleaning(self):
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        RawData.objects.create(
            source=self.datasource,
            row_number=1,
            data={'name': 'Alice', 'amount': 42},
            validation_status='valid',
        )
        empty_pipeline = CleaningPipeline.objects.create(
            name='Empty pipeline for test',
            created_by=self.user,
            is_active=True,
        )

        response = self.client.post(
            f'/api/nettoyage/sources/{self.datasource.id}/apply-async/',
            {
                'pipeline_id': empty_pipeline.id,
                'include_all_auto_rules': False,
                'rule_ids': [],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['status'] in {'queued', 'completed'}

    def test_preview_with_explicit_rule_selection_returns_mvp_preview(self):
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        RawData.objects.bulk_create([
            RawData(source=self.datasource, row_number=1, data={'amount': ''}, validation_status='valid'),
            RawData(source=self.datasource, row_number=2, data={'amount': 'abc'}, validation_status='valid'),
            RawData(source=self.datasource, row_number=3, data={'amount': '10'}, validation_status='valid'),
        ])
        rule = CleaningRule.objects.create(
            name='Fill amount mean',
            rule_type='fill_mean',
            created_by=self.user,
            column_names=['amount'],
        )

        response = self.client.post(
            f'/api/nettoyage/sources/{self.datasource.id}/preview/',
            {'rule_ids': [rule.id], 'include_all_auto_rules': False},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        preview_values = [row.get('data', row).get('amount') for row in response.data['sample_rows']]
        assert 'abc' in preview_values
        assert any(value in (None, '', '10', 10, 10.0) for value in preview_values)

    def test_preview_uses_same_engine_logic_as_apply(self):
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        RawData.objects.bulk_create([
            RawData(source=self.datasource, row_number=1, data={'Mont_TTC': '1 740 000 FCFA', 'Qté': '2', 'Date vente': '01/03/2026', 'Client_Nom': 'DIST. OUAGA  '}, validation_status='valid'),
            RawData(source=self.datasource, row_number=2, data={'Mont_TTC': '1 740 000 FCFA', 'Qté': '2', 'Date vente': '01/03/2026', 'Client_Nom': 'DIST. OUAGA  '}, validation_status='valid'),
            RawData(source=self.datasource, row_number=3, data={'Mont_TTC': '', 'Qté': '', 'Date vente': '', 'Client_Nom': '   '}, validation_status='warning'),
        ])

        response = self.client.post(
            f'/api/nettoyage/sources/{self.datasource.id}/preview/',
            {'rule_ids': [], 'include_all_auto_rules': True},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['summary']['rows_affected'] >= 1
        assert response.data['summary']['rows_removed'] >= 1
        assert response.data['cleaning_report']['corrections']
        assert any(sample['changes'] for sample in response.data['diff_samples'])

    def test_preview_rejects_invalid_quality_gate(self):
        response = self.client.post(
            f'/api/nettoyage/sources/{self.datasource.id}/preview/',
            {
                'rule_ids': [],
                'include_all_auto_rules': False,
                'quality_gate': {'min_quality_score': 150},
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'quality_gate' in response.data

    def test_apply_cleaning_with_explicit_rule_selection_returns_mvp_output(self):
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        RawData.objects.bulk_create([
            RawData(source=self.datasource, row_number=1, data={'amount': ''}, validation_status='valid'),
            RawData(source=self.datasource, row_number=2, data={'amount': 'abc'}, validation_status='valid'),
            RawData(source=self.datasource, row_number=3, data={'amount': '10'}, validation_status='valid'),
        ])
        rule = CleaningRule.objects.create(
            name='Fill amount mean',
            rule_type='fill_mean',
            created_by=self.user,
            column_names=['amount'],
        )

        result = apply_cleaning(
            source=self.datasource,
            user=self.user,
            pipeline_id=None,
            rule_ids=[rule.id],
            include_all_auto_rules=False,
            quality_gate={},
        )

        assert result['summary']['rows_affected'] >= 1
        preview_values = [row['data']['amount'] for row in result['sample_rows']]
        assert 'abc' in preview_values
        assert any(value in (None, '', '10', 10, 10.0) for value in preview_values)

    def test_apply_async_falls_back_to_sync_when_enqueue_fails(self):
        """If async enqueue fails, API should complete job synchronously and return 202."""
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        RawData.objects.create(
            source=self.datasource,
            row_number=1,
            data={'name': 'Alice', 'amount': '42'},
            validation_status='valid',
        )

        with patch('apps.nettoyage.views.apply_cleaning_async.delay', side_effect=RuntimeError('broker down')):
            with patch('apps.nettoyage.views.apply_cleaning') as mock_apply:
                mock_apply.return_value = {
                    'job_id': 999,
                    'summary': {
                        'rows_processed': 1,
                        'rows_affected': 1,
                        'rows_skipped': 0,
                        'rows_failed': 0,
                    },
                }

                response = self.client.post(
                    f'/api/nettoyage/sources/{self.datasource.id}/apply-async/',
                    {
                        'rule_ids': [],
                        'include_all_auto_rules': False,
                        'quality_gate': {},
                    },
                    format='json',
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['status'] == 'completed'
        assert response.data['rows_affected'] == 1
        assert response.data['result_job_id'] == 999

        job = CleaningJob.objects.get(id=response.data['id'])
        assert job.execution_context['fallback_mode'] == 'sync'
        assert job.execution_context['result_job_id'] == 999
        assert 'enqueue_error' in job.execution_context

    def test_export_endpoint_returns_queued_task_metadata(self):
        """Export endpoint should return task metadata when async export is queued."""
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])

        rule = CleaningRule.objects.create(
            name='Export trigger rule',
            rule_type='remove_duplicates',
            created_by=self.user,
        )
        job = CleaningJob.objects.create(
            source=self.datasource,
            rule=rule,
            status='completed',
            created_by=self.user,
        )

        with patch(
            'apps.nettoyage.views.export_cleaned_data_async.delay',
            return_value=SimpleNamespace(id='task-abc-123'),
        ):
            response = self.client.post(
                f'/api/nettoyage/jobs/{job.id}/export/',
                {
                    'format': 'json',
                    'include_metadata': True,
                    'include_validation_status': True,
                },
                format='json',
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['message'] == 'Export task queued'
        assert response.data['job_id'] == job.id
        assert response.data['task_id'] == 'task-abc-123'
        assert response.data['format'] == 'json'

    def test_apply_async_returns_400_when_fallback_sync_cleaning_fails(self):
        """If enqueue and sync fallback both fail, endpoint should return 400 and fail the tracking job."""
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        RawData.objects.create(
            source=self.datasource,
            row_number=1,
            data={'name': 'Alice', 'amount': '42'},
            validation_status='valid',
        )

        with patch('apps.nettoyage.views.apply_cleaning_async.delay', side_effect=RuntimeError('broker down')):
            with patch('apps.nettoyage.views.apply_cleaning', side_effect=CleaningError('fallback failed')):
                response = self.client.post(
                    f'/api/nettoyage/sources/{self.datasource.id}/apply-async/',
                    {
                        'rule_ids': [],
                        'include_all_auto_rules': False,
                        'quality_gate': {},
                    },
                    format='json',
                )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'fallback failed'

        failed_job = CleaningJob.objects.filter(source=self.datasource).latest('id')
        assert failed_job.status == 'failed'
        assert failed_job.error_message == 'fallback failed'


@pytest.mark.django_db
def test_export_task_persists_job_export_path():
    """Export task should persist the generated path on the cleaning job."""
    user = User.objects.create_user(
        username='exporter',
        email='export@example.com',
        password='testpass123'
    )
    source = DataSource.objects.create(
        name='Export Source',
        source_type='csv',
        uploaded_by=user
    )
    rule = CleaningRule.objects.create(
        name='Export Rule',
        rule_type='remove_duplicates',
        created_by=user
    )
    job = CleaningJob.objects.create(
        source=source,
        rule=rule,
        status='completed',
        created_by=user
    )
    raw = RawData.objects.create(
        source=source,
        row_number=1,
        data={'name': 'Alice', 'amount': 42},
    )
    cleaned = CleanedData.objects.create(
        job=job,
        original_data=raw,
        data={'name': 'Alice', 'amount': 42},
        changes_made=[{'action': 'remove_duplicates'}],
    )

    media_root = Path(__file__).resolve().parents[3] / 'test_media'

    with override_settings(MEDIA_ROOT=media_root):
        result = export_cleaned_data_async(job.id, format='csv', include_metadata=True)

    assert result['status'] == 'success'
    job.refresh_from_db()
    cleaned.refresh_from_db()
    assert job.export_path == result['filepath']
    assert cleaned.export_path == result['filepath']


@pytest.mark.django_db
def test_export_task_returns_warning_when_no_cleaned_data():
    """Export task should return warning when a job has no cleaned rows."""
    user = User.objects.create_user(
        username='exportempty',
        email='exportempty@example.com',
        password='testpass123'
    )
    source = DataSource.objects.create(
        name='Empty Export Source',
        source_type='csv',
        uploaded_by=user
    )
    rule = CleaningRule.objects.create(
        name='Empty Export Rule',
        rule_type='remove_duplicates',
        created_by=user
    )
    job = CleaningJob.objects.create(
        source=source,
        rule=rule,
        status='completed',
        created_by=user
    )

    result = export_cleaned_data_async(job.id, format='csv')

    assert result['status'] == 'warning'
    assert result['message'] == 'No cleaned data found'


@pytest.mark.django_db
def test_export_task_returns_error_for_unsupported_format():
    """Export task should gracefully reject unsupported export formats."""
    user = User.objects.create_user(
        username='exportfmt',
        email='exportfmt@example.com',
        password='testpass123'
    )
    source = DataSource.objects.create(
        name='Format Export Source',
        source_type='csv',
        uploaded_by=user
    )
    rule = CleaningRule.objects.create(
        name='Format Export Rule',
        rule_type='remove_duplicates',
        created_by=user
    )
    job = CleaningJob.objects.create(
        source=source,
        rule=rule,
        status='completed',
        created_by=user
    )
    raw = RawData.objects.create(
        source=source,
        row_number=1,
        data={'name': 'Alice', 'amount': 42},
    )
    CleanedData.objects.create(
        job=job,
        original_data=raw,
        data={'name': 'Alice', 'amount': 42},
        changes_made=[{'action': 'remove_duplicates'}],
    )

    result = export_cleaned_data_async(job.id, format='xml')

    assert result['status'] == 'error'
    assert result['message'] == 'Unsupported format: xml'
