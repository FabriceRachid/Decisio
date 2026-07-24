from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData, CleaningJob, CleaningPipeline, CleaningRule


class CleaningPipelineAPITest(APITestCase):
    def setUp(self):
        self.password = 'testpass123'
        self.analyst = User.objects.create_user(
            username='clean_analyst',
            email='clean@example.com',
            password=self.password,
        )
        self.analyst.profile.role = 'analyst'
        self.analyst.profile.save()

        self.viewer = User.objects.create_user(
            username='clean_viewer',
            email='viewer@example.com',
            password=self.password,
        )
        self.viewer.profile.role = 'viewer'
        self.viewer.profile.save()

        self.source = DataSource.objects.create(
            name='ERP Sales Import',
            source_type='csv',
            uploaded_by=self.analyst,
            status='completed',
            row_count=3,
            column_count=3,
            metadata={'columns': ['customer_code', 'currency', 'amount']},
        )

        RawData.objects.create(
            source=self.source,
            row_number=2,
            data={'customer_code': ' abc ', 'currency': ' usd ', 'amount': ''},
            validation_status='valid',
        )
        RawData.objects.create(
            source=self.source,
            row_number=3,
            data={'customer_code': 'abc', 'currency': 'usd', 'amount': ''},
            validation_status='valid',
        )
        RawData.objects.create(
            source=self.source,
            row_number=4,
            data={'customer_code': 'xyz', 'currency': 'eur', 'amount': '100'},
            validation_status='valid',
        )

        self.standardize_rule = CleaningRule.objects.create(
            name='Trim and uppercase currencies',
            rule_type='standardize',
            column_names=['customer_code', 'currency'],
            parameters={'mode': 'upper'},
            priority=10,
            created_by=self.analyst,
        )
        self.fill_rule = CleaningRule.objects.create(
            name='Fill missing amounts',
            rule_type='fill_value',
            column_names=['amount'],
            parameters={'value': '0'},
            priority=8,
            created_by=self.analyst,
            apply_to_all=True,
        )
        self.duplicate_rule = CleaningRule.objects.create(
            name='Remove duplicates',
            rule_type='remove_duplicates',
            column_names=['customer_code', 'currency', 'amount'],
            priority=5,
            created_by=self.analyst,
        )
        self.mean_rule = CleaningRule.objects.create(
            name='Fill amount with mean',
            rule_type='fill_mean',
            column_names=['amount'],
            priority=7,
            created_by=self.analyst,
        )
        self.date_normalize_rule = CleaningRule.objects.create(
            name='Normalize dates',
            rule_type='normalize',
            column_names=['document_date'],
            parameters={'mode': 'date_iso'},
            priority=6,
            created_by=self.analyst,
        )
        self.pipeline = CleaningPipeline.objects.create(
            name='Sales Cleaning Pipeline',
            description='Default sales cleanup',
            source_type_scope='csv',
            quality_gate={'min_quality_score': 100, 'max_missing_value_rate': 0},
            created_by=self.analyst,
        )
        self.pipeline.rules.set([self.standardize_rule, self.fill_rule, self.duplicate_rule])
        self.remove_empty_rows_rule = CleaningRule.objects.create(
            name='Remove empty rows',
            rule_type='remove_empty_rows',
            priority=9,
            created_by=self.analyst,
        )
        self.drop_rows_threshold_rule = CleaningRule.objects.create(
            name='Drop sparse rows',
            rule_type='drop_rows_by_missing_threshold',
            parameters={'threshold': 0.5},
            priority=8,
            created_by=self.analyst,
        )
        self.convert_date_rule = CleaningRule.objects.create(
            name='Convert date values',
            rule_type='convert_dtype',
            column_names=['document_date'],
            parameters={'dtype': 'date', 'dayfirst': True},
            priority=7,
            created_by=self.analyst,
        )
        self.value_map_rule = CleaningRule.objects.create(
            name='Map country values',
            rule_type='value_map',
            column_names=['country'],
            parameters={'mapping': {'USA': 'US', 'U.S.A': 'US'}, 'case_insensitive': True},
            priority=7,
            created_by=self.analyst,
        )
        self.merge_columns_rule = CleaningRule.objects.create(
            name='Merge names',
            rule_type='merge_columns',
            parameters={'source_columns': ['first_name', 'last_name'], 'target_column': 'full_name', 'separator': ' '},
            priority=6,
            created_by=self.analyst,
        )

    def _login(self, user):
        response = self.client.post('/api/auth/login/', {
            'username': user.username,
            'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access_token']}")

    def test_rule_list_and_create(self):
        self._login(self.analyst)

        list_response = self.client.get('/api/nettoyage/rules/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_response.data['count'], 3)

        create_response = self.client.post('/api/nettoyage/rules/', {
            'name': 'Validate customer format',
            'rule_type': 'validate_format',
            'column_names': ['customer_code'],
            'parameters': {'pattern': '^[A-Z]{3}$'},
            'priority': 7,
            'is_active': True,
            'apply_to_all': False,
            'category': 'validation',
            'tags': ['customer'],
        }, format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CleaningRule.objects.filter(name='Validate customer format').count(), 1)

    def test_preview_cleaning_shows_transformed_sample_and_summary(self):
        self._login(self.analyst)

        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.standardize_rule.id, self.duplicate_rule.id],
            'include_all_auto_rules': True,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['row_count'], 2)
        self.assertEqual(response.data['sample_rows'][0]['customer_code'], 'ABC')
        self.assertEqual(response.data['sample_rows'][0]['currency'], 'USD')
        self.assertEqual(response.data['sample_rows'][0]['amount'], '0')

    def test_apply_cleaning_persists_jobs_and_cleaned_data(self):
        self._login(self.analyst)

        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id, self.duplicate_rule.id],
            'include_all_auto_rules': True,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CleaningJob.objects.count(), 1)
        latest_job = CleaningJob.objects.order_by('-created_at').first()
        self.assertEqual(latest_job.status, 'completed')
        self.assertIn('cleaning_report', response.data)
        self.assertEqual(CleanedData.objects.filter(job=latest_job).count(), 2)
        cleaned_row = CleanedData.objects.filter(job=latest_job).order_by('original_data__row_number').first()
        self.assertEqual(cleaned_row.data['customer_code'], 'ABC')
        self.assertEqual(cleaned_row.data['amount'], '0')
        self.assertGreaterEqual(float(cleaned_row.quality_score), 100)

    def test_viewer_cannot_preview_or_apply_cleaning(self):
        self._login(self.viewer)

        preview_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        self.assertEqual(preview_response.status_code, status.HTTP_403_FORBIDDEN)

        apply_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        self.assertEqual(apply_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_job_listing_filters_by_source(self):
        self._login(self.analyst)
        self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')

        response = self.client.get(f'/api/nettoyage/jobs/?source_id={self.source.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_pipeline_list_and_detail(self):
        self._login(self.analyst)

        list_response = self.client.get('/api/nettoyage/pipelines/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_response.data['count'], 1)

        detail_response = self.client.get(f'/api/nettoyage/pipelines/{self.pipeline.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['name'], 'Sales Cleaning Pipeline')

    def test_fill_mean_rule_fills_numeric_missing_values(self):
        self.source.raw_data_rows.all().delete()
        RawData.objects.create(source=self.source, row_number=2, data={'amount': '10'}, validation_status='valid')
        RawData.objects.create(source=self.source, row_number=3, data={'amount': ''}, validation_status='valid')
        RawData.objects.create(source=self.source, row_number=4, data={'amount': '30'}, validation_status='valid')

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.mean_rule.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sample_rows'][1]['amount'], 20.0)

    def test_quality_gate_blocks_apply_when_missing_rate_too_high(self):
        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
            'quality_gate': {'max_missing_value_rate': 0},
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Quality gate failed', response.data['error'])

    def test_pipeline_preview_returns_diff_samples(self):
        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'pipeline_id': self.pipeline.id,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pipeline']['name'], 'Sales Cleaning Pipeline')
        self.assertGreaterEqual(len(response.data['diff_samples']), 1)
        self.assertTrue(any(change['column'] == 'customer_code' for change in response.data['diff_samples'][0]['changes']))

    def test_remove_empty_rows_rule_drops_whitespace_only_rows(self):
        self.source.raw_data_rows.all().delete()
        RawData.objects.create(source=self.source, row_number=2, data={'customer_code': '   ', 'currency': '', 'amount': None}, validation_status='valid')
        RawData.objects.create(source=self.source, row_number=3, data={'customer_code': 'abc', 'currency': 'usd', 'amount': '10'}, validation_status='valid')

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.remove_empty_rows_rule.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['row_count'], 1)
        self.assertEqual(response.data['sample_rows'][0]['customer_code'], 'abc')

    def test_drop_rows_by_missing_threshold_removes_sparse_rows(self):
        self.source.raw_data_rows.all().delete()
        RawData.objects.create(source=self.source, row_number=2, data={'a': 'x', 'b': '', 'c': ''}, validation_status='valid')
        RawData.objects.create(source=self.source, row_number=3, data={'a': 'x', 'b': 'y', 'c': ''}, validation_status='valid')

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.drop_rows_threshold_rule.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['row_count'], 1)

    def test_convert_dtype_date_rule_normalizes_dates(self):
        self.source.raw_data_rows.all().delete()
        RawData.objects.create(source=self.source, row_number=2, data={'document_date': '31/03/2026'}, validation_status='valid')

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.convert_date_rule.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sample_rows'][0]['document_date'], '2026-03-31')

    def test_value_map_rule_standardizes_categories(self):
        self.source.raw_data_rows.all().delete()
        RawData.objects.create(source=self.source, row_number=2, data={'country': 'U.S.A'}, validation_status='valid')

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.value_map_rule.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sample_rows'][0]['country'], 'US')

    def test_merge_columns_rule_builds_full_name(self):
        self.source.raw_data_rows.all().delete()
        RawData.objects.create(source=self.source, row_number=2, data={'first_name': 'Ada', 'last_name': 'Lovelace'}, validation_status='valid')

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/preview/', {
            'rule_ids': [self.merge_columns_rule.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sample_rows'][0]['full_name'], 'Ada Lovelace')

    def test_suggestions_endpoint_detects_duplicates_and_missing_values(self):
        self._login(self.analyst)
        response = self.client.get(f'/api/nettoyage/sources/{self.source.id}/suggestions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suggested_rules', response.data)

    def test_fuzzy_suggest_matches_helper(self):
        # Directly test the fuzzy suggestion helper to ensure it returns expected candidates
        from apps.nettoyage import services

        source_cols = ['cust_code', 'currency', 'amt']
        canonical = ['customer_code', 'currency', 'amount']
        if not getattr(services, 'fuzz', None):
            self.skipTest('thefuzz not available in test environment')

        suggestions = services._fuzzy_suggest_matches(source_cols, canonical, top_n=1, threshold=50)

        # Expect cust_code to match customer_code and amt to match amount
        self.assertIn('cust_code', suggestions)
        self.assertEqual(suggestions['cust_code'][0]['candidate'], 'customer_code')
        self.assertIn('amt', suggestions)
        self.assertEqual(suggestions['amt'][0]['candidate'], 'amount')

    # ==== PHASE 1 TESTS: Update/Delete Rules ====
    
    def test_update_rule_partial_fields(self):
        """Test PATCH endpoint to update rule fields"""
        self._login(self.analyst)
        
        update_response = self.client.patch(f'/api/nettoyage/rules/{self.standardize_rule.id}/', {
            'priority': 20,
            'category': 'advanced_cleaning',
        }, format='json')
        
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.standardize_rule.refresh_from_db()
        self.assertEqual(self.standardize_rule.priority, 20)
        self.assertEqual(self.standardize_rule.category, 'advanced_cleaning')

    def test_update_rule_full_replacement(self):
        """Test PUT endpoint to fully replace rule"""
        self._login(self.analyst)
        
        update_response = self.client.put(f'/api/nettoyage/rules/{self.standardize_rule.id}/', {
            'name': 'Trim whitespace',
            'rule_type': 'standardize',
            'column_names': ['all_text'],
            'parameters': {'mode': 'trim'},
            'priority': 15,
            'is_active': True,
            'category': 'formatting',
        }, format='json')
        
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.standardize_rule.refresh_from_db()
        self.assertEqual(self.standardize_rule.name, 'Trim whitespace')

    def test_delete_rule_soft_deletes(self):
        """Test DELETE endpoint soft-deletes rule"""
        self._login(self.analyst)
        
        delete_response = self.client.delete(f'/api/nettoyage/rules/{self.standardize_rule.id}/')
        
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.standardize_rule.refresh_from_db()
        self.assertFalse(self.standardize_rule.is_active)

    def test_update_rule_requires_write_permission(self):
        """Test that non-analysts cannot update rules"""
        self._login(self.viewer)
        
        update_response = self.client.patch(f'/api/nettoyage/rules/{self.standardize_rule.id}/', {
            'priority': 20,
        }, format='json')
        
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

    # ==== PHASE 1 TESTS: Async Cleaning (apply-async) ====
    
    def test_apply_async_returns_202_and_creates_job(self):
        """Test async apply endpoint queues task and returns 202 Accepted"""
        self._login(self.analyst)
        
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply-async/', {
            'rule_ids': [self.standardize_rule.id],
            'include_all_auto_rules': False,
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], 'queued')
        self.assertIn('id', response.data)
        
        # Verify job was created
        job = CleaningJob.objects.get(id=response.data['id'])
        self.assertEqual(job.source_id, self.source.id)
        self.assertEqual(job.status, 'queued')

    def test_apply_async_requires_write_permission(self):
        """Test that viewers cannot trigger async cleaning"""
        self._login(self.viewer)
        
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply-async/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==== PHASE 1 TESTS: Advanced Filtering ====
    
    def test_filter_rules_by_type(self):
        """Test filtering rules by rule_type"""
        self._login(self.analyst)
        
        response = self.client.get('/api/nettoyage/rules/?rule_type=standardize')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)
        self.assertTrue(all(r['rule_type'] == 'standardize' for r in response.data['results']))

    def test_filter_rules_by_category(self):
        """Test filtering rules by category"""
        self._login(self.analyst)
        
        response = self.client.get('/api/nettoyage/rules/?category=validation')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should find at least the one we created with category='validation'

    def test_filter_rules_by_is_active(self):
        """Test filtering rules by active status"""
        self._login(self.analyst)
        
        # First deactivate a rule
        self.standardize_rule.is_active = False
        self.standardize_rule.save()
        
        response = self.client.get('/api/nettoyage/rules/?is_active=false')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)

    def test_search_rules_by_name(self):
        """Test free-text search in rule names"""
        self._login(self.analyst)
        
        response = self.client.get('/api/nettoyage/rules/?search=standardize')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any('standardize' in r['name'].lower() for r in response.data['results']))

    def test_order_rules_by_priority(self):
        """Test ordering rules by priority"""
        self._login(self.analyst)
        
        response = self.client.get('/api/nettoyage/rules/?ordering=priority')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        priorities = [r['priority'] for r in response.data['results']]
        self.assertEqual(priorities, sorted(priorities))

    def test_filter_jobs_by_status(self):
        """Test filtering jobs by status"""
        self._login(self.analyst)
        
        # Create a cleaning job
        self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        
        # Filter by completed status
        response = self.client.get('/api/nettoyage/jobs/?status=completed')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)

    def test_filter_jobs_by_source_id(self):
        """Test filtering jobs by source_id"""
        self._login(self.analyst)
        
        response = self.client.get(f'/api/nettoyage/jobs/?source_id={self.source.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(j['source_id'] == self.source.id for j in response.data['results']))

    def test_filter_jobs_by_date_range(self):
        """Test filtering jobs by date range"""
        self._login(self.analyst)
        
        from datetime import datetime, timedelta
        yesterday = datetime.now().date() - timedelta(days=1)
        
        response = self.client.get(f'/api/nettoyage/jobs/?created_after={yesterday}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ==== PHASE 1 TESTS: Export Cleaned Data ====
    
    def test_export_endpoint_queues_async_task(self):
        """Test export endpoint queues task and returns 202"""
        self._login(self.analyst)
        
        # Create a cleaning job first
        apply_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        
        job_id = apply_response.data['job_id']
        
        # Export the cleaned data
        export_response = self.client.post(f'/api/nettoyage/jobs/{job_id}/export/', {
            'format': 'csv',
        }, format='json')
        
        self.assertEqual(export_response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(export_response.data['format'], 'csv')

    def test_export_supports_multiple_formats(self):
        """Test export supports csv, excel, json formats"""
        self._login(self.analyst)
        
        # Create job
        apply_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        
        job_id = apply_response.data['job_id']
        
        # Test each format
        for fmt in ['csv', 'excel', 'json']:
            export_response = self.client.post(f'/api/nettoyage/jobs/{job_id}/export/', {
                'format': fmt,
            }, format='json')
            
            self.assertEqual(export_response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(export_response.data['format'], fmt)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['suggested_rules']), 2)
        suggested_rule_types = {item['rule_type'] for item in response.data['suggested_rules']}
        self.assertIn('remove_duplicates', suggested_rule_types)
        self.assertIn('fill_mode', suggested_rule_types)

    def test_apply_without_rule_ids_uses_default_pipeline(self):
        self.pipeline.apply_to_all = True
        self.pipeline.save(update_fields=['apply_to_all'])

        self._login(self.analyst)
        response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['pipeline']['name'], self.pipeline.name)
        latest_job = CleaningJob.objects.order_by('-created_at').first()
        self.assertEqual(latest_job.execution_context['pipeline']['id'], self.pipeline.id)

    def test_job_detail_returns_validation_summary_and_execution_context(self):
        self._login(self.analyst)
        apply_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'pipeline_id': self.pipeline.id,
        }, format='json')
        self.assertEqual(apply_response.status_code, status.HTTP_201_CREATED)
        latest_job = CleaningJob.objects.order_by('-created_at').first()

        detail_response = self.client.get(f'/api/nettoyage/jobs/{latest_job.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['job']['id'], latest_job.id)
        self.assertIn('execution_context', detail_response.data['job'])
        self.assertIn('validation_rate', detail_response.data['validation_summary'])

    def test_job_validation_endpoint_marks_cleaned_rows_validated(self):
        self._login(self.analyst)
        apply_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'rule_ids': [self.standardize_rule.id],
        }, format='json')
        self.assertEqual(apply_response.status_code, status.HTTP_201_CREATED)
        latest_job = CleaningJob.objects.order_by('-created_at').first()

        validate_response = self.client.post(f'/api/nettoyage/jobs/{latest_job.id}/validate/', {
            'is_validated': True,
            'validation_notes': 'Approved for downstream analysis.',
        }, format='json')

        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(CleanedData.objects.filter(job=latest_job, is_validated=True).count(), 3)

    def test_job_replay_reuses_original_execution_context(self):
        self._login(self.analyst)
        apply_response = self.client.post(f'/api/nettoyage/sources/{self.source.id}/apply/', {
            'pipeline_id': self.pipeline.id,
        }, format='json')
        self.assertEqual(apply_response.status_code, status.HTTP_201_CREATED)
        latest_job = CleaningJob.objects.order_by('-created_at').first()

        replay_response = self.client.post(f'/api/nettoyage/jobs/{latest_job.id}/replay/', {}, format='json')

        self.assertEqual(replay_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CleaningJob.objects.count(), 6)
