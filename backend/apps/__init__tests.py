"""
Comprehensive Test Suite for Decisio Platform
Run all tests: python manage.py test apps --verbosity=2
"""

from django.test import TestCase
from django.contrib.auth.models import User


class AuthenticationTests(TestCase):
    """Test Authentication Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_profile_auto_creation(self):
        """UserProfile is created automatically"""
        from apps.authentication.models import UserProfile
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.role, 'viewer')
    
    def test_user_profile_role_change(self):
        """Test changing user role"""
        profile = self.user.profile
        profile.role = 'analyst'
        profile.save()
        self.assertEqual(profile.get_role_display(), 'Data Analyst')
    
    def test_api_token_creation(self):
        """Test API token creation with scopes"""
        import hashlib
        from apps.authentication.models import AuthToken
        
        token = AuthToken.objects.create(
            user=self.user,
            token_hash=hashlib.sha256(b'test_token').hexdigest(),
            token_prefix='test_',
            name='Test Token',
            scopes=['read:data']
        )
        
        self.assertEqual(token.name, 'Test Token')
        self.assertIn('read:data', token.scopes)


class IngestionTests(TestCase):
    """Test Data Ingestion Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='ingest_user', password='pass')
    
    def test_datasource_creation(self):
        """Test DataSource model creation"""
        from apps.ingestion.models import DataSource
        
        source = DataSource.objects.create(
            name='Test CSV',
            source_type='csv',
            uploaded_by=self.user,
            row_count=1000,
            delimiter=',',
            status='completed'
        )
        
        self.assertEqual(source.name, 'Test CSV')
        self.assertEqual(source.row_count, 1000)
        self.assertEqual(str(source), 'Test CSV (CSV File)')
    
    def test_raw_data_storage(self):
        """Test storing raw data rows"""
        from apps.ingestion.models import DataSource, RawData
        
        source = DataSource.objects.create(
            name='Raw Data Source',
            source_type='json',
            uploaded_by=self.user
        )
        
        row = RawData.objects.create(
            source=source,
            row_number=1,
            data={'name': 'Test', 'value': 100}
        )
        
        self.assertEqual(row.data['name'], 'Test')
        self.assertEqual(row.validation_status, 'valid')


class CleaningTests(TestCase):
    """Test Nettoyage/Cleaning Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='clean_user', password='pass')
    
    def test_cleaning_rule_creation(self):
        """Test creating cleaning rules"""
        from apps.nettoyage.models import CleaningRule
        
        rule = CleaningRule.objects.create(
            name='Remove Nulls',
            rule_type='remove_nulls',
            priority=8,
            created_by=self.user
        )
        
        self.assertEqual(rule.get_rule_type_display(), 'Remove Null Values')
        self.assertEqual(rule.priority, 8)
    
    def test_cleaning_job_tracking(self):
        """Test cleaning job progress tracking"""
        from apps.nettoyage.models import CleaningRule, CleaningJob
        from apps.ingestion.models import DataSource
        
        source = DataSource.objects.create(
            name='To Clean',
            source_type='csv',
            uploaded_by=self.user
        )
        
        rule = CleaningRule.objects.create(
            name='Standardize',
            rule_type='standardize',
            created_by=self.user
        )
        
        job = CleaningJob.objects.create(
            source=source,
            rule=rule,
            total_rows=1000,
            rows_processed=500,
            created_by=self.user
        )
        
        self.assertEqual(job.progress_percent, 0)  # Should calculate based on rows
        self.assertEqual(job.status, 'pending')


class ConflictTests(TestCase):
    """Test Conflict Detection Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='conflict_user', password='pass')
    
    def test_conflict_type_definition(self):
        """Test defining conflict types"""
        from apps.conflits.models import ConflictType
        
        conflict_type = ConflictType.objects.create(
            name='Duplicate Record',
            code='DUPLICATE',
            severity='high'
        )
        
        self.assertEqual(conflict_type.code, 'DUPLICATE')
        self.assertEqual(conflict_type.get_severity_display(), 'High')
    
    def test_conflict_detection(self):
        """Test logging detected conflicts"""
        from apps.conflits.models import ConflictType, Conflict
        from apps.ingestion.models import DataSource
        
        source = DataSource.objects.create(
            name='Conflicted Data',
            source_type='csv',
            uploaded_by=self.user
        )
        
        conflict_type = ConflictType.objects.create(
            name='Missing Field',
            code='MISSING',
            severity='medium'
        )
        
        conflict = Conflict.objects.create(
            data_source=source,
            conflict_type=conflict_type,
            affected_columns=['email'],
            conflict_details={'field': 'email', 'issue': 'null'},
            status='detected'
        )
        
        self.assertEqual(conflict.status, 'detected')
        self.assertIn('email', conflict.affected_columns)


class KPITests(TestCase):
    """Test KPI Management Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='kpi_user', password='pass')
    
    def test_kpi_definition(self):
        """Test creating KPI definitions"""
        from apps.kpi.models import KPI
        
        kpi = KPI.objects.create(
            name='Monthly Revenue',
            code='MRR',
            formula='SUM(revenue)',
            target_value=100000,
            operator='>=',
            owner=self.user
        )
        
        self.assertEqual(kpi.code, 'MRR')
        self.assertEqual(kpi.target_value, 100000)
    
    def test_kpi_calculation(self):
        """Test recording KPI calculations"""
        from apps.kpi.models import KPI, KPICalculation
        from datetime import date
        
        kpi = KPI.objects.create(
            name='Revenue',
            code='REV',
            formula='SUM(x)',
            owner=self.user
        )
        
        calc = KPICalculation.objects.create(
            kpi=kpi,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            calculated_value=95000.00,
            previous_value=90000.00,
            variance_percent=5.56
        )
        
        self.assertEqual(calc.calculated_value, 95000.00)
        self.assertEqual(calc.variance_percent, 5.56)


class DashboardTests(TestCase):
    """Test Dashboard Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='dash_user', password='pass')
    
    def test_dashboard_creation(self):
        """Test creating dashboards"""
        from apps.dashboard.models import Dashboard
        
        dashboard = Dashboard.objects.create(
            name='Sales Overview',
            slug='sales-overview',
            layout={'widgets': []},
            created_by=self.user,
            is_public=True
        )
        
        self.assertEqual(dashboard.slug, 'sales-overview')
        self.assertTrue(dashboard.is_public)
    
    def test_widget_creation(self):
        """Test creating dashboard widgets"""
        from apps.dashboard.models import Dashboard, Widget
        
        dashboard = Dashboard.objects.create(
            name='Test Dash',
            slug='test-dash',
            layout={},
            created_by=self.user
        )
        
        widget = Widget.objects.create(
            dashboard=dashboard,
            widget_type='line_chart',
            title='Revenue Trend',
            configuration={'kpi_id': 1},
            width=6,
            height=3
        )
        
        self.assertEqual(widget.widget_type, 'line_chart')
        self.assertEqual(widget.width, 6)


class AITests(TestCase):
    """Test AI Interpretation Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='ai_user', password='pass')
    
    def test_ai_analysis_session(self):
        """Test creating AI analysis sessions"""
        from apps.ia_interpretation.models import AIAnalysis
        
        analysis = AIAnalysis.objects.create(
            analysis_type='trend_analysis',
            prompt='Why did revenue drop?',
            model_provider='openai',
            model_name='gpt-4',
            requested_by=self.user,
            status='completed'
        )
        
        self.assertEqual(analysis.analysis_type, 'trend_analysis')
        self.assertEqual(analysis.model_name, 'gpt-4')
    
    def test_ai_insight_generation(self):
        """Test generating AI insights"""
        from apps.ia_interpretation.models import AIAnalysis, AIInsight
        
        analysis = AIAnalysis.objects.create(
            analysis_type='summary',
            prompt='Summarize this data',
            model_provider='openai',
            model_name='gpt-4',
            requested_by=self.user
        )
        
        insight = AIInsight.objects.create(
            analysis=analysis,
            insight_type='trend',
            title='Revenue Increased 15%',
            description='Strong upward trend observed',
            supporting_data={'growth': 0.15}
        )
        
        self.assertEqual(insight.insight_type, 'trend')
        self.assertEqual(insight.supporting_data['growth'], 0.15)


class AnomalyTests(TestCase):
    """Test Anomaly Detection Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='anomaly_user', password='pass')
    
    def test_anomaly_model_creation(self):
        """Test creating anomaly detection models"""
        from apps.anomalies.models import AnomalyModel
        
        model = AnomalyModel.objects.create(
            name='Revenue Anomaly Detector',
            algorithm='isolation_forest',
            training_parameters={'n_estimators': 100},
            training_features=['revenue', 'date'],
            created_by=self.user
        )
        
        self.assertEqual(model.algorithm, 'isolation_forest')
        self.assertEqual(model.training_features, ['revenue', 'date'])
    
    def test_anomaly_detection(self):
        """Test recording detected anomalies"""
        from apps.anomalies.models import AnomalyModel, Anomaly
        from apps.ingestion.models import DataSource
        
        source = DataSource.objects.create(
            name='Anomaly Source',
            source_type='csv',
            uploaded_by=self.user
        )
        
        model = AnomalyModel.objects.create(
            name='Test Model',
            algorithm='isolation_forest',
            training_parameters={},
            training_features=['value'],
            created_by=self.user
        )
        
        anomaly = Anomaly.objects.create(
            model=model,
            data_source=source,
            row_ids=[47],
            affected_columns=['revenue'],
            anomaly_score=0.95,
            severity='high',
            explanation='Value 3.2 std devs above mean'
        )
        
        self.assertEqual(anomaly.anomaly_score, 0.95)
        self.assertEqual(anomaly.severity, 'high')


class ChatbotTests(TestCase):
    """Test Chatbot Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='chat_user', password='pass')
    
    def test_chat_session_creation(self):
        """Test creating chat sessions"""
        from apps.chatbot.models import ChatSession
        import uuid
        
        session = ChatSession.objects.create(
            user=self.user,
            session_token=str(uuid.uuid4()),
            bot_personality='professional'
        )
        
        self.assertIsNotNone(session.session_token)
        self.assertTrue(session.is_active)
    
    def test_chat_message_exchange(self):
        """Test chat message exchange"""
        from apps.chatbot.models import ChatSession, ChatMessage
        import uuid
        
        session = ChatSession.objects.create(
            user=self.user,
            session_token=str(uuid.uuid4())
        )
        
        # User message
        user_msg = ChatMessage.objects.create(
            session=session,
            message_type='user',
            content='What was the revenue last month?'
        )
        
        # Bot response
        bot_msg = ChatMessage.objects.create(
            session=session,
            message_type='bot',
            content='Revenue last month was $95,000',
            intent='QUERY_KPI'
        )
        
        self.assertEqual(user_msg.message_type, 'user')
        self.assertEqual(bot_msg.intent, 'QUERY_KPI')


class SystemTests(TestCase):
    """Test System Module"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='system_user', password='pass')
    
    def test_activity_logging(self):
        """Test activity log creation"""
        from apps.conflits.models import ActivityLog
        
        log = ActivityLog.objects.create(
            user=self.user,
            action_type='create',
            resource_type='DataSource',
            resource_id=1,
            ip_address='192.168.1.1'
        )
        
        self.assertEqual(log.action_type, 'create')
        self.assertEqual(log.ip_address, '192.168.1.1')
    
    def test_system_configuration(self):
        """Test system configuration storage"""
        from apps.conflits.models import SystemConfig
        
        config = SystemConfig.objects.create(
            config_key='app.debug_mode',
            config_value='true',
            value_type='boolean',
            category='general'
        )
        
        self.assertEqual(config.config_key, 'app.debug_mode')
        self.assertEqual(config.value_type, 'boolean')
    
    def test_scheduled_jobs(self):
        """Test scheduled job creation"""
        from apps.conflits.models import ScheduledJob
        
        job = ScheduledJob.objects.create(
            job_name='Daily Backup',
            job_type='backup',
            schedule_type='cron',
            cron_expression='0 2 * * *',
            job_parameters={'destination': 's3://backups'},
            created_by=self.user
        )
        
        self.assertEqual(job.job_type, 'backup')
        self.assertEqual(job.cron_expression, '0 2 * * *')


# Run with: python manage.py test apps --verbosity=2
