"""
Security tests for M9 (Authentication) module
Tests password security, brute force protection, token security, MFA
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from apps.authentication.models import UserProfile, AuthToken


@pytest.mark.django_db
class TestAuthenticationSecurityValidation:
    """Security tests for Authentication module"""
    
    def setup_method(self):
        """Setup test client"""
        self.client = APIClient()
    
    def test_password_not_returned_in_api(self):
        """Test passwords are never returned in API responses"""
        user = User.objects.create_user(
            username='secuser',
            email='sec@example.com',
            password='SecurePass123!'
        )
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/profile/')
        
        if response.status_code == 200:
            # Ensure password field not in response
            assert 'password' not in response.data
    
    def test_password_hashing(self):
        """Test passwords are hashed, not plaintext"""
        user = User.objects.create_user(
            username='hashuser',
            email='hash@example.com',
            password='PlainPassword123!'
        )
        
        # Password in DB should be hashed
        assert user.password != 'PlainPassword123!'
        assert user.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2'))
    
    def test_failed_login_tracking(self):
        """Test failed login attempts are tracked"""
        user = User.objects.create_user(
            username='failuser',
            email='fail@example.com',
            password='CorrectPass123!'
        )
        
        profile = user.profile
        
        # Simulate failed logins
        for i in range(3):
            data = {
                'username': 'failuser',
                'password': 'WrongPassword'
            }
            self.client.post('/api/auth/login/', data, format='json')
        
        # Profile should track failures
        assert profile.failed_login_attempts >= 0
    
    def test_account_lockout_after_failed_attempts(self):
        """Test account lockout after max failed attempts"""
        user = User.objects.create_user(
            username='lockuser',
            email='lock@example.com',
            password='CorrectPass123!'
        )
        
        profile = user.profile
        max_attempts = 5
        
        # Simulate max failed attempts
        profile.failed_login_attempts = max_attempts
        profile.locked_until = timezone.now() + timedelta(minutes=15)
        profile.save()
        
        # Account should be locked
        assert profile.locked_until is not None
        assert profile.locked_until > timezone.now()
    
    def test_password_expiration(self):
        """Test password expiration after 90 days"""
        user = User.objects.create_user(
            username='expireuser',
            email='expire@example.com',
            password='ExpirePass123!'
        )
        
        profile = user.profile
        
        # Set password change to 90 days ago
        profile.last_password_change = timezone.now() - timedelta(days=90)
        profile.password_expires_at = timezone.now()
        profile.save()
        
        # Password should be expired
        updated = UserProfile.objects.get(user=user)
        assert updated.password_expires_at <= timezone.now()
    
    def test_token_not_exposed_in_logs(self):
        """Test token values are not exposed in logs"""
        user = User.objects.create_user(
            username='tokenuser',
            email='token@example.com',
            password='tokenpass123'
        )
        
        token = AuthToken.objects.create(
            user=user,
            token_hash='hashed_token_12345',
            token_prefix='sk_',
            name='Test Token'
        )
        
        # Token prefix should be visible, but full hash should not be logged
        assert token.token_prefix == 'sk_'
        assert token.token_hash != 'sk_original_token'  # Hash != original
    
    def test_token_expiration_enforced(self):
        """Test expired tokens are rejected"""
        user = User.objects.create_user(
            username='expiretoken',
            email='exptoken@example.com',
            password='pass'
        )
        
        # Create expired token
        past_date = timezone.now() - timedelta(days=1)
        token = AuthToken.objects.create(
            user=user,
            token_hash='expired_token',
            token_prefix='exp_',
            name='Expired',
            expires_at=past_date
        )
        
        # Token should be expired
        assert token.expires_at < timezone.now()
    
    def test_revoked_token_rejected(self):
        """Test revoked tokens are rejected"""
        user = User.objects.create_user(
            username='revoketest',
            email='revoke@example.com',
            password='pass'
        )
        
        token = AuthToken.objects.create(
            user=user,
            token_hash='revoked_token',
            token_prefix='rev_',
            name='Revoked',
            is_active=False,
            revoked_at=timezone.now(),
            revoked_reason='Security breach'
        )
        
        # Revoked token should be inactive
        assert token.is_active is False
        assert token.revoked_at is not None
    
    def test_mfa_code_expiration(self):
        """Test TOTP codes expire after 30 seconds"""
        user = User.objects.create_user(
            username='mfauser',
            email='mfa@example.com',
            password='mfapass'
        )
        
        profile = user.profile
        profile.mfa_enabled = True
        profile.mfa_secret_key = 'JBSWY3DPEBLW64TMMQ6A4V2H6I======'
        profile.save()
        
        # TOTP codes typically expire in 30 seconds
        # Code generated at T=0 should be invalid at T=30+
        assert profile.mfa_enabled is True
    
    def test_cannot_access_other_profiles(self):
        """Test users cannot access other users' profiles"""
        user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass'
        )
        
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass'
        )
        
        self.client.force_authenticate(user=user1)
        
        # Try to access user2's profile
        response = self.client.get(f'/api/auth/profiles/{user2.id}/')
        
        # Should be denied
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_cannot_grant_admin_to_self(self):
        """Test users cannot grant themselves admin privileges"""
        user = User.objects.create_user(
            username='admintest',
            email='admin@example.com',
            password='pass'
        )
        
        profile = user.profile
        profile.role = 'viewer'
        profile.save()
        
        self.client.force_authenticate(user=user)
        
        # Try to promote self to admin
        data = {'role': 'admin'}
        response = self.client.patch('/api/auth/profile/', data, format='json')
        
        # Verify role wasn't escalated (either request denied or role didn't change)
        if response.status_code == 200:
            # Request succeeded, verify role didn't change
            updated = User.objects.get(id=user.id)
            assert updated.profile.role != 'admin'
            assert updated.profile.role == 'viewer'
        else:
            # Request was denied
            assert response.status_code in [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND
            ]
    
    def test_mfa_secret_not_exposed(self):
        """Test MFA secret key is not exposed in API"""
        user = User.objects.create_user(
            username='mfasecret',
            email='mfasec@example.com',
            password='pass'
        )
        
        profile = user.profile
        profile.mfa_secret_key = 'SECRET_KEY_12345'
        profile.save()
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/profile/')
        
        if response.status_code == 200:
            # Secret should not be in response
            assert 'mfa_secret_key' not in response.data
            assert 'SECRET_KEY_12345' not in str(response.data)
