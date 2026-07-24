"""
Unit tests for M1 (Ingestion) models
Tests DataSource, RawData, and IngestionJob models with actual field definitions
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from apps.ingestion.models import DataSource, RawData, IngestionJob


@pytest.mark.django_db
class TestDataSourceModel:
    """Tests for DataSource model with actual field definitions"""
    
    def test_create_datasource_minimal(self):
        """Test creating DataSource with minimal required fields"""
        user = User.objects.create_user(username='testuser1', email='test1@example.com')
        
        ds = DataSource.objects.create(
            name='Sales Data',
            source_type='csv',
            uploaded_by=user
        )
        
        assert ds.name == 'Sales Data'
        assert ds.source_type == 'csv'
        assert ds.status == 'pending'  # Default
        assert ds.delimiter == ','  # Default
        assert ds.encoding == 'utf-8'  # Default
        assert ds.has_header is True  # Default
        assert ds.retention_days == 90  # Default
        assert ds.is_archived is False  # Default
        assert ds.uploaded_by == user
    
    def test_datasource_with_file_info(self):
        """Test DataSource with file information"""
        user = User.objects.create_user(username='testuser2', email='test2@example.com')
        
        ds = DataSource.objects.create(
            name='Finance Data',
            source_type='excel',
            uploaded_by=user,
            file_path='/uploads/finance.xlsx',
            file_size_bytes=5242880,
            row_count=1000,
            column_count=15
        )
        
        assert ds.file_path == '/uploads/finance.xlsx'
        assert ds.file_size_bytes == 5242880
        assert ds.row_count == 1000
        assert ds.column_count == 15
    
    def test_datasource_status_choices(self):
        """Test DataSource status field validation"""
        user = User.objects.create_user(username='testuser3', email='test3@example.com')
        
        statuses = ['pending', 'processing', 'completed', 'failed']
        for status in statuses:
            ds = DataSource.objects.create(
                name=f'Data {status}',
                source_type='csv',
                uploaded_by=user,
                status=status
            )
            assert ds.status == status
    
    def test_datasource_source_type_choices(self):
        """Test DataSource source_type field validation"""
        user = User.objects.create_user(username='testuser4', email='test4@example.com')
        
        source_types = ['csv', 'excel', 'api', 'database', 'json']
        for source_type in source_types:
            ds = DataSource.objects.create(
                name=f'Source {source_type}',
                source_type=source_type,
                uploaded_by=user
            )
            assert ds.source_type == source_type
    
    def test_datasource_with_metadata(self):
        """Test DataSource with metadata and tags"""
        user = User.objects.create_user(username='testuser5', email='test5@example.com')
        
        metadata = {'department': 'Finance', 'quarter': 'Q1'}
        tags = ['finance', 'reporting', 'important']
        
        ds = DataSource.objects.create(
            name='Tagged Data',
            source_type='csv',
            uploaded_by=user,
            metadata=metadata,
            tags=tags,
            checksum_md5='abc123def456'
        )
        
        assert ds.metadata == metadata
        assert ds.tags == tags
        assert ds.checksum_md5 == 'abc123def456'
    
    def test_datasource_versioning(self):
        """Test DataSource versioning via parent_source"""
        user = User.objects.create_user(username='testuser6', email='test6@example.com')
        
        original = DataSource.objects.create(
            name='Original',
            source_type='csv',
            uploaded_by=user,
            schema_version=1
        )
        
        version = DataSource.objects.create(
            name='Original v2',
            source_type='csv',
            uploaded_by=user,
            parent_source=original,
            schema_version=2
        )
        
        assert version.parent_source == original
        assert original.versions.count() == 1
    
    def test_datasource_timestamps(self):
        """Test DataSource auto timestamps"""
        user = User.objects.create_user(username='testuser7', email='test7@example.com')
        
        ds = DataSource.objects.create(
            name='Timestamp Test',
            source_type='csv',
            uploaded_by=user
        )
        
        assert ds.created_at is not None
        assert ds.updated_at is not None
        assert ds.processed_at is None


@pytest.mark.django_db
class TestRawDataModel:
    """Tests for RawData model"""
    
    def test_create_raw_data(self):
        """Test creating RawData with required fields"""
        user = User.objects.create_user(username='rawuser1', email='raw1@example.com')
        
        ds = DataSource.objects.create(
            name='Source',
            source_type='csv',
            uploaded_by=user
        )
        
        row = RawData.objects.create(
            source=ds,
            row_number=1,
            data={'name': 'John', 'age': 30}
        )
        
        assert row.source == ds
        assert row.row_number == 1
        assert row.data['name'] == 'John'
        assert row.validation_status == 'valid'  # Default
    
    def test_raw_data_validation_status(self):
        """Test RawData validation_status field"""
        user = User.objects.create_user(username='rawuser2', email='raw2@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        statuses = ['valid', 'invalid', 'warning']
        for i, status in enumerate(statuses):
            row = RawData.objects.create(
                source=ds,
                row_number=i+10,
                data={'test': f'data{i}'},
                validation_status=status
            )
            assert row.validation_status == status
    
    def test_raw_data_with_hash(self):
        """Test RawData data_hash field"""
        user = User.objects.create_user(username='rawuser3', email='raw3@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        row = RawData.objects.create(
            source=ds,
            row_number=1,
            data={'id': 123},
            data_hash='abc123def456'
        )
        
        assert row.data_hash == 'abc123def456'
    
    def test_raw_data_with_messages(self):
        """Test RawData validation_messages"""
        user = User.objects.create_user(username='rawuser4', email='raw4@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        messages = ['Field X required', 'Invalid email']
        row = RawData.objects.create(
            source=ds,
            row_number=1,
            data={'test': 'data'},
            validation_status='invalid',
            validation_messages=messages
        )
        
        assert row.validation_messages == messages


@pytest.mark.django_db
class TestIngestionJobModel:
    """Tests for IngestionJob model"""
    
    def test_create_ingestion_job(self):
        """Test creating IngestionJob"""
        job = IngestionJob.objects.create(
            celery_task_id='task-abc-123',
            status='processing'
        )
        
        assert job.celery_task_id == 'task-abc-123'
        assert job.status == 'processing'
        assert job.progress_percent == 0  # Default
        assert job.created_at is not None
    
    def test_ingestion_job_statuses(self):
        """Test IngestionJob status field"""
        statuses = ['queued', 'processing', 'completed', 'failed', 'cancelled']
        for i, status in enumerate(statuses):
            job = IngestionJob.objects.create(
                celery_task_id=f'task-{i}',
                status=status
            )
            assert job.status == status
    
    def test_ingestion_job_progress(self):
        """Test IngestionJob progress tracking"""
        job = IngestionJob.objects.create(
            celery_task_id='task-progress',
            progress_percent=75,
            status='processing'
        )
        
        assert job.progress_percent == 75
    
    def test_ingestion_job_with_error(self):
        """Test IngestionJob error tracking"""
        job = IngestionJob.objects.create(
            celery_task_id='task-error',
            status='failed',
            error_message='File not found'
        )
        
        assert job.error_message == 'File not found'
        assert job.status == 'failed'
