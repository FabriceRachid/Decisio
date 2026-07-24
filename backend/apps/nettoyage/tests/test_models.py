"""
Unit tests for M2 (Nettoyage/Cleaning) models
Tests CleaningRule, CleaningPipeline, CleaningJob, and CleanedData models
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleaningRule, CleaningPipeline, CleaningJob, CleanedData


@pytest.mark.django_db
class TestCleaningRuleModel:
    """Tests for CleaningRule model"""
    
    def test_create_cleaning_rule_minimal(self):
        """Test creating CleaningRule with minimal fields"""
        user = User.objects.create_user(username='ruleuser1', email='rule1@example.com')
        
        rule = CleaningRule.objects.create(
            name='Remove Nulls',
            rule_type='remove_nulls',
            created_by=user
        )
        
        assert rule.name == 'Remove Nulls'
        assert rule.rule_type == 'remove_nulls'
        assert rule.created_by == user
        assert rule.priority == 5  # Default
        assert rule.is_active is True  # Default
        assert rule.apply_to_all is False  # Default
        assert rule.version == 1  # Default
    
    def test_cleaning_rule_types(self):
        """Test CleaningRule rule_type choices"""
        user = User.objects.create_user(username='ruleuser2', email='rule2@example.com')
        
        rule_types = [
            'remove_nulls', 'remove_empty_rows', 'drop_rows_by_missing_threshold',
            'drop_columns_by_missing_threshold', 'fill_mean', 'fill_median', 'fill_mode',
            'fill_value', 'standardize', 'regex_replace', 'remove_duplicates', 'normalize',
            'convert_dtype', 'value_map', 'rename_columns', 'split_column', 'merge_columns',
            'validate_format'
        ]
        
        for i, rule_type in enumerate(rule_types):
            rule = CleaningRule.objects.create(
                name=f'Rule {i}',
                rule_type=rule_type,
                created_by=user
            )
            assert rule.rule_type == rule_type
    
    def test_cleaning_rule_with_parameters(self):
        """Test CleaningRule with parameters"""
        user = User.objects.create_user(username='ruleuser3', email='rule3@example.com')
        
        parameters = {'fill_value': 0, 'column': 'age'}
        column_names = ['age', 'income']
        
        rule = CleaningRule.objects.create(
            name='Fill Missing Age',
            rule_type='fill_value',
            created_by=user,
            parameters=parameters,
            column_names=column_names,
            column_pattern='age.*'
        )
        
        assert rule.parameters == parameters
        assert rule.column_names == column_names
        assert rule.column_pattern == 'age.*'
    
    def test_cleaning_rule_priority(self):
        """Test CleaningRule priority field"""
        user = User.objects.create_user(username='ruleuser4', email='rule4@example.com')
        
        rule1 = CleaningRule.objects.create(
            name='High Priority',
            rule_type='remove_nulls',
            created_by=user,
            priority=1
        )
        
        rule2 = CleaningRule.objects.create(
            name='Low Priority',
            rule_type='remove_nulls',
            created_by=user,
            priority=10
        )
        
        assert rule1.priority == 1
        assert rule2.priority == 10
    
    def test_cleaning_rule_with_tags(self):
        """Test CleaningRule with tags and category"""
        user = User.objects.create_user(username='ruleuser5', email='rule5@example.com')
        
        tags = ['missing_values', 'finance', 'critical']
        rule = CleaningRule.objects.create(
            name='Financial Cleaning',
            rule_type='remove_nulls',
            created_by=user,
            tags=tags,
            category='data_quality'
        )
        
        assert rule.tags == tags
        assert rule.category == 'data_quality'


@pytest.mark.django_db
class TestCleaningPipelineModel:
    """Tests for CleaningPipeline model"""
    
    def test_create_cleaning_pipeline(self):
        """Test creating CleaningPipeline"""
        user = User.objects.create_user(username='pipeuser1', email='pipe1@example.com')
        
        pipeline = CleaningPipeline.objects.create(
            name='Standard Cleaning',
            created_by=user
        )
        
        assert pipeline.name == 'Standard Cleaning'
        assert pipeline.created_by == user
        assert pipeline.is_active is True  # Default
        assert pipeline.apply_to_all is False  # Default
    
    def test_cleaning_pipeline_with_rules(self):
        """Test CleaningPipeline with rules"""
        user = User.objects.create_user(username='pipeuser2', email='pipe2@example.com')
        
        rule1 = CleaningRule.objects.create(
            name='Rule 1',
            rule_type='remove_nulls',
            created_by=user
        )
        rule2 = CleaningRule.objects.create(
            name='Rule 2',
            rule_type='remove_duplicates',
            created_by=user
        )
        
        pipeline = CleaningPipeline.objects.create(
            name='Multi-step Cleaning',
            created_by=user
        )
        pipeline.rules.add(rule1, rule2)
        
        assert pipeline.rules.count() == 2
        assert rule1 in pipeline.rules.all()
        assert rule2 in pipeline.rules.all()
    
    def test_cleaning_pipeline_source_type_scope(self):
        """Test CleaningPipeline source_type_scope"""
        user = User.objects.create_user(username='pipeuser3', email='pipe3@example.com')
        
        pipeline = CleaningPipeline.objects.create(
            name='CSV Cleaning',
            created_by=user,
            source_type_scope='csv'
        )
        
        assert pipeline.source_type_scope == 'csv'


@pytest.mark.django_db
class TestCleaningJobModel:
    """Tests for CleaningJob model"""
    
    def test_create_cleaning_job(self):
        """Test creating CleaningJob"""
        user = User.objects.create_user(username='jobuser1', email='job1@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        job = CleaningJob.objects.create(
            source=ds,
            status='pending',
            created_by=user
        )
        
        assert job.source == ds
        assert job.status == 'pending'
        assert job.created_by == user
        assert job.rows_processed == 0  # Default
        assert job.progress_percent == Decimal('0')  # Default
        assert job.batch_size == 1000  # Default
        assert job.max_retries == 3  # Default
    
    def test_cleaning_job_statuses(self):
        """Test CleaningJob status field"""
        user = User.objects.create_user(username='jobuser2', email='job2@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        for i, status in enumerate(statuses):
            job = CleaningJob.objects.create(
                source=ds,
                status=status,
                created_by=user
            )
            assert job.status == status
    
    def test_cleaning_job_progress_tracking(self):
        """Test CleaningJob progress tracking"""
        user = User.objects.create_user(username='jobuser3', email='job3@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        job = CleaningJob.objects.create(
            source=ds,
            total_rows=1000,
            rows_processed=500,
            rows_affected=100,
            rows_skipped=50,
            rows_failed=0,
            progress_percent=Decimal('50.0'),
            created_by=user
        )
        
        assert job.total_rows == 1000
        assert job.rows_processed == 500
        assert job.rows_affected == 100
        assert job.progress_percent == Decimal('50.0')
    
    def test_cleaning_job_with_error(self):
        """Test CleaningJob error handling"""
        user = User.objects.create_user(username='jobuser4', email='job4@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        
        job = CleaningJob.objects.create(
            source=ds,
            status='failed',
            error_message='Connection timeout',
            retry_count=2,
            created_by=user
        )
        
        assert job.error_message == 'Connection timeout'
        assert job.retry_count == 2


@pytest.mark.django_db
class TestCleanedDataModel:
    """Tests for CleanedData model"""
    
    def test_create_cleaned_data(self):
        """Test creating CleanedData"""
        user = User.objects.create_user(username='cleanuser1', email='clean1@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        job = CleaningJob.objects.create(source=ds, created_by=user)
        
        cleaned = CleanedData.objects.create(
            job=job,
            data={'name': 'John', 'age': 30}
        )
        
        assert cleaned.job == job
        assert cleaned.data['name'] == 'John'
        assert cleaned.is_validated is False  # Default
    
    def test_cleaned_data_with_changes(self):
        """Test CleanedData with changes tracking"""
        user = User.objects.create_user(username='cleanuser2', email='clean2@example.com')
        ds = DataSource.objects.create(name='Source', source_type='csv', uploaded_by=user)
        job = CleaningJob.objects.create(source=ds, created_by=user)
        
        changes = [
            {'column': 'age', 'before': None, 'after': 30},
            {'column': 'email', 'before': 'INVALID', 'after': 'john@example.com'}
        ]
        
        cleaned = CleanedData.objects.create(
            job=job,
            data={'cleaned': 'data'},
            changes_made=changes,
            quality_score=Decimal('85.5')
        )
        
        assert cleaned.changes_made == changes
        assert cleaned.quality_score == Decimal('85.5')
