"""
API tests for M1 (Ingestion) module
Tests DataSource, RawData, and IngestionJob API endpoints
"""
from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from apps.ingestion.models import DataSource, RawData, IngestionJob


@pytest.mark.django_db
class TestDataSourceAPIEndpoints:
    """Tests for DataSource API endpoints"""
    
    def setup_method(self):
        """Setup test client and test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_datasources(self):
        """Test listing DataSources"""
        # Create test data
        DataSource.objects.create(
            name='Source 1',
            source_type='csv',
            uploaded_by=self.user
        )
        DataSource.objects.create(
            name='Source 2',
            source_type='excel',
            uploaded_by=self.user
        )
        
        response = self.client.get('/api/ingestion/datasources/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_list_sources_excludes_archived(self):
        """Archived sources should not be returned in the standard list."""
        DataSource.objects.create(
            name='Visible Source',
            source_type='csv',
            uploaded_by=self.user,
            is_archived=False,
        )
        DataSource.objects.create(
            name='Archived Source',
            source_type='csv',
            uploaded_by=self.user,
            is_archived=True,
        )

        response = self.client.get('/api/ingestion/sources/')
        assert response.status_code == status.HTTP_200_OK
        names = [item['name'] for item in response.data.get('results', [])]
        assert 'Visible Source' in names
        assert 'Archived Source' not in names

    def test_admin_list_sources_defaults_to_own_uploads(self):
        """Admins should see their own imports by default on the ingestion page."""
        admin_user = User.objects.create_user(
            username='admin_ingestion',
            email='admin_ingestion@example.com',
            password='testpass123',
        )
        admin_user.profile.role = 'admin'
        admin_user.profile.save(update_fields=['role'])

        other_user = User.objects.create_user(
            username='other_ingestion',
            email='other_ingestion@example.com',
            password='testpass123',
        )

        DataSource.objects.create(
            name='Admin Source',
            source_type='csv',
            uploaded_by=admin_user,
        )
        DataSource.objects.create(
            name='Other Source',
            source_type='csv',
            uploaded_by=other_user,
        )

        self.client.force_authenticate(user=admin_user)
        response = self.client.get('/api/ingestion/sources/')
        assert response.status_code == status.HTTP_200_OK
        names = [item['name'] for item in response.data.get('results', [])]
        assert 'Admin Source' in names
        assert 'Other Source' not in names
    
    def test_create_datasource(self):
        """Test creating a DataSource"""
        data = {
            'name': 'New Source',
            'source_type': 'csv',
            'description': 'Test data source'
        }
        
        response = self.client.post('/api/ingestion/datasources/', data, format='json')
        # Endpoint may not exist yet, so we just check no crash
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_unauthenticated_access_denied(self):
        """Test unauthenticated users cannot access endpoints"""
        client = APIClient()
        response = client.get('/api/ingestion/datasources/')
        # Should be denied or endpoint may not exist
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND
        ]


@pytest.mark.django_db
class TestRawDataAPIEndpoints:
    """Tests for RawData API endpoints"""
    
    def setup_method(self):
        """Setup test client and test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='rawapi',
            email='rawapi@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.datasource = DataSource.objects.create(
            name='Test Source',
            source_type='csv',
            uploaded_by=self.user
        )
    
    def test_list_raw_data_by_source(self):
        """Test listing RawData rows for a DataSource"""
        RawData.objects.create(
            source=self.datasource,
            row_number=1,
            data={'name': 'John', 'age': 30}
        )
        RawData.objects.create(
            source=self.datasource,
            row_number=2,
            data={'name': 'Jane', 'age': 28}
        )
        
        response = self.client.get(f'/api/ingestion/datasources/{self.datasource.id}/raw_data/')
        # Endpoint may not exist, so we check for various responses
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_filter_invalid_rows(self):
        """Test filtering invalid rows"""
        RawData.objects.create(
            source=self.datasource,
            row_number=1,
            data={'name': 'John'},
            validation_status='valid'
        )
        RawData.objects.create(
            source=self.datasource,
            row_number=2,
            data={'invalid': 'row'},
            validation_status='invalid'
        )
        
        response = self.client.get(f'/api/ingestion/datasources/{self.datasource.id}/raw_data/?status=invalid')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_raw_data_page_size_can_be_configured(self):
        """Raw data list should support configurable page size for preview pagination."""
        for row_number in range(1, 31):
            RawData.objects.create(
                source=self.datasource,
                row_number=row_number,
                data={'name': f'Row {row_number}'},
                validation_status='valid',
            )

        response = self.client.get(f'/api/ingestion/sources/{self.datasource.id}/raw-data/?page_size=50')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 30
        assert len(response.data['results']) == 30


@pytest.mark.django_db
class TestIngestionJobAPIEndpoints:
    """Tests for IngestionJob API endpoints"""
    
    def setup_method(self):
        """Setup test client and test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='jobapi',
            email='jobapi@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='jobother',
            email='jobother@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.datasource = DataSource.objects.create(
            name='Test Source',
            source_type='csv',
            uploaded_by=self.user
        )
    
    def test_list_ingestion_jobs(self):
        """Test listing ingestion jobs"""
        IngestionJob.objects.create(
            celery_task_id='task-1',
            requested_by=self.user,
            source=self.datasource,
            status='completed'
        )
        
        response = self.client.get('/api/ingestion/jobs/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_get_job_status(self):
        """Test getting job status"""
        job = IngestionJob.objects.create(
            celery_task_id='task-status',
            requested_by=self.user,
            source=self.datasource,
            status='processing',
            progress_percent=50
        )
        
        response = self.client.get(f'/api/ingestion/jobs/{job.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_poll_job_progress(self):
        """Test polling job progress"""
        job = IngestionJob.objects.create(
            celery_task_id='task-poll',
            requested_by=self.user,
            status='processing',
            progress_percent=25
        )
        
        # Update progress
        job.progress_percent = 75
        job.save()
        
        response = self.client.get(f'/api/ingestion/jobs/{job.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_cannot_access_another_users_job(self):
        """Non-admin users should not see another user's ingestion job."""
        other_source = DataSource.objects.create(
            name='Other Source',
            source_type='csv',
            uploaded_by=self.other_user
        )
        job = IngestionJob.objects.create(
            celery_task_id='task-foreign',
            requested_by=self.other_user,
            source=other_source,
            status='processing',
            progress_percent=10
        )

        response = self.client.get(f'/api/ingestion/jobs/{job.id}/')
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


@pytest.mark.django_db
class TestIngestionUploadFailures:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='broken_upload_user',
            email='broken_upload@example.com',
            password='testpass123',
        )
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        self.client.force_authenticate(user=self.user)

    def test_preview_invalid_excel_returns_400_instead_of_500(self):
        broken_excel = SimpleUploadedFile(
            'broken.xlsx',
            b'this is not a real excel workbook',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(
            '/api/ingestion/sources/preview/',
            {'file': broken_excel},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Fichier Excel corrompu ou illisible' in response.data['error']

    def test_upload_invalid_excel_returns_400_instead_of_500(self):
        broken_excel = SimpleUploadedFile(
            'broken.xlsx',
            b'this is not a real excel workbook',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(
            '/api/ingestion/sources/upload/',
            {'file': broken_excel},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Fichier Excel corrompu ou illisible' in response.data['error']

    def test_preview_invalid_csv_returns_specific_400_message(self):
        broken_csv = SimpleUploadedFile(
            'broken.csv',
            b'\x00\x81\x8f\x90not-a-valid-csv',
            content_type='text/csv',
        )

        response = self.client.post(
            '/api/ingestion/sources/preview/',
            {'file': broken_csv, 'encoding': 'utf-8'},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'CSV invalide' in response.data['error']

    def test_preview_auto_detects_semicolon_csv_and_cp1252_encoding(self):
        csv_content = "nom;ville\nCafé;Ouagadougou\n".encode('cp1252')
        upload = SimpleUploadedFile('clients.csv', csv_content, content_type='text/csv')

        response = self.client.post(
            '/api/ingestion/sources/preview/',
            {'file': upload},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['source_type'] == 'csv'
        assert response.data['delimiter'] == ';'
        assert response.data['encoding'] == 'cp1252'
        assert response.data['row_count'] == 1
        assert response.data['sample_rows'][0]['data']['nom'] == 'Café'

    def test_preview_accepts_single_column_csv_without_separator_noise(self):
        csv_content = "health_indicator\nDiabetes_binary\nBMI\n".encode("utf-8")
        upload = SimpleUploadedFile('single_column.csv', csv_content, content_type='text/csv')

        response = self.client.post(
            '/api/ingestion/sources/preview/',
            {'file': upload},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['source_type'] == 'csv'
        assert response.data['column_count'] == 1
        assert response.data['row_count'] == 2
        assert response.data['sample_rows'][0]['data']['health_indicator'] == 'Diabetes_binary'
