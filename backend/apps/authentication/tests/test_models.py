"""
Unit tests for M9 (Authentication) models
Tests UserProfile and AuthToken models
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from apps.authentication.models import UserProfile, AuthToken


@pytest.mark.django_db
class TestUserProfileModel:
    """Tests for UserProfile model"""
    
    def test_user_profile_auto_creation(self):
        """Test UserProfile is auto-created with User"""
        user = User.objects.create_user(
            username='testprofile',
            email='profile@example.com',
            password='testpass123'
        )
        
        # Profile should be auto-created via signal
        assert hasattr(user, 'profile')
        profile = user.profile
        assert profile.user == user
        assert profile.role == 'viewer'  # Direct user creation keeps the default role
    
    def test_user_profile_role_choices(self):
        """Test UserProfile role field"""
        roles = [('admin', 'admin'), ('analyst', 'analyst'), ('viewer', 'viewer')]
        
        for username, role in roles:
            user = User.objects.create_user(username=username, email=f'{username}@example.com')
            user.profile.role = role
            user.profile.save()
            
            profile = UserProfile.objects.get(user=user)
            assert profile.role == role
    
    def test_user_profile_with_info(self):
        """Test UserProfile with department and contact info"""
        user = User.objects.create_user(username='infouser', email='info@example.com')
        profile = user.profile
        
        profile.department = 'Finance'
        profile.phone_number = '+33612345678'
        profile.avatar_url = 'https://example.com/avatar.jpg'
        profile.save()
        
        updated_profile = UserProfile.objects.get(user=user)
        assert updated_profile.department == 'Finance'
        assert updated_profile.phone_number == '+33612345678'
        assert updated_profile.avatar_url == 'https://example.com/avatar.jpg'
    
    def test_user_profile_email_verification(self):
        """Test UserProfile email verification"""
        user = User.objects.create_user(username='emailuser', email='email@example.com')
        profile = user.profile
        
        assert profile.is_email_verified is False  # Default
        
        profile.is_email_verified = True
        profile.save()
        
        assert UserProfile.objects.get(user=user).is_email_verified is True
    
    def test_user_profile_login_tracking(self):
        """Test UserProfile login tracking"""
        user = User.objects.create_user(username='loginuser', email='login@example.com')
        profile = user.profile
        
        assert profile.last_login_ip is None  # Not set on creation
        
        profile.last_login_ip = '192.168.1.1'
        profile.save()
        
        assert UserProfile.objects.get(user=user).last_login_ip == '192.168.1.1'
    
    def test_user_profile_failed_login_tracking(self):
        """Test UserProfile failed login attempts"""
        user = User.objects.create_user(username='failuser', email='fail@example.com')
        profile = user.profile
        
        assert profile.failed_login_attempts == 0  # Default
        
        profile.failed_login_attempts = 3
        profile.save()
        
        assert UserProfile.objects.get(user=user).failed_login_attempts == 3
    
    def test_user_profile_lockout(self):
        """Test UserProfile account lockout"""
        user = User.objects.create_user(username='lockuser', email='lock@example.com')
        profile = user.profile
        
        assert profile.locked_until is None  # Not locked
        
        now = timezone.now()
        profile.locked_until = now + timedelta(minutes=15)
        profile.save()
        
        updated = UserProfile.objects.get(user=user)
        assert updated.locked_until is not None
    
    def test_user_profile_password_management(self):
        """Test UserProfile password tracking"""
        user = User.objects.create_user(username='passuser', email='pass@example.com')
        profile = user.profile
        
        now = timezone.now()
        profile.last_password_change = now
        profile.password_expires_at = now + timedelta(days=90)
        profile.save()
        
        updated = UserProfile.objects.get(user=user)
        assert updated.last_password_change is not None
        assert updated.password_expires_at is not None
    
    def test_user_profile_mfa(self):
        """Test UserProfile MFA settings"""
        user = User.objects.create_user(username='mfauser', email='mfa@example.com')
        profile = user.profile
        
        assert profile.mfa_enabled is False  # Default
        
        profile.mfa_enabled = True
        profile.mfa_secret_key = 'JBSWY3DPEBLW64TMMQ6A4V2H6I======'
        profile.save()
        
        updated = UserProfile.objects.get(user=user)
        assert updated.mfa_enabled is True
        assert updated.mfa_secret_key == 'JBSWY3DPEBLW64TMMQ6A4V2H6I======'
    
    def test_user_profile_preferences(self):
        """Test UserProfile timezone and language preferences"""
        user = User.objects.create_user(username='prefuser', email='pref@example.com')
        profile = user.profile
        
        profile.timezone = 'Europe/Paris'
        profile.language = 'fr'
        profile.save()
        
        updated = UserProfile.objects.get(user=user)
        assert updated.timezone == 'Europe/Paris'
        assert updated.language == 'fr'


@pytest.mark.django_db
class TestAuthTokenModel:
    """Tests for AuthToken model"""
    
    def test_create_auth_token(self):
        """Test creating AuthToken"""
        user = User.objects.create_user(username='tokenuser', email='token@example.com')
        
        token = AuthToken.objects.create(
            user=user,
            token_hash='abc123def456ghi789',
            token_prefix='test_',
            name='API Key 1'
        )
        
        assert token.user == user
        assert token.token_hash == 'abc123def456ghi789'
        assert token.token_prefix == 'test_'
        assert token.name == 'API Key 1'
        assert token.is_active is True  # Default
    
    def test_auth_token_with_scopes(self):
        """Test AuthToken with scopes"""
        user = User.objects.create_user(username='scopeuser', email='scope@example.com')
        
        scopes = ['read:data', 'write:data']
        token = AuthToken.objects.create(
            user=user,
            token_hash='scopetoken123',
            token_prefix='api_',
            name='Read-Write Token',
            scopes=scopes
        )
        
        assert token.scopes == scopes
    
    def test_auth_token_expiration(self):
        """Test AuthToken expiration"""
        user = User.objects.create_user(username='expuser', email='exp@example.com')
        
        future_date = timezone.now() + timedelta(days=30)
        token = AuthToken.objects.create(
            user=user,
            token_hash='exptoken123',
            token_prefix='exp_',
            name='Expiring Token',
            expires_at=future_date
        )
        
        assert token.expires_at == future_date
    
    def test_auth_token_usage_tracking(self):
        """Test AuthToken usage tracking"""
        user = User.objects.create_user(username='usageuser', email='usage@example.com')
        
        token = AuthToken.objects.create(
            user=user,
            token_hash='usagetoken123',
            token_prefix='use_',
            name='Tracked Token',
            usage_count=5,
            last_used_at=timezone.now()
        )
        
        assert token.usage_count == 5
        assert token.last_used_at is not None
    
    def test_auth_token_revocation(self):
        """Test AuthToken revocation"""
        user = User.objects.create_user(username='revokeuser', email='revoke@example.com')
        
        token = AuthToken.objects.create(
            user=user,
            token_hash='revoketoken123',
            token_prefix='rev_',
            name='Revoked Token',
            is_active=False,
            revoked_at=timezone.now(),
            revoked_reason='Security concern'
        )
        
        assert token.is_active is False
        assert token.revoked_at is not None
        assert token.revoked_reason == 'Security concern'
    
    def test_auth_token_rate_limit(self):
        """Test AuthToken rate limiting"""
        user = User.objects.create_user(username='ratelimituser', email='ratelimit@example.com')
        
        token = AuthToken.objects.create(
            user=user,
            token_hash='ratelimittoken123',
            token_prefix='rl_',
            name='Rate Limited Token',
            rate_limit=5000  # 5000 requests per hour
        )
        
        assert token.rate_limit == 5000
    
    def test_auth_token_ip_whitelist(self):
        """Test AuthToken IP whitelist"""
        user = User.objects.create_user(username='ipuser', email='ip@example.com')
        
        whitelist = ['192.168.1.1', '10.0.0.1', '203.0.113.45']
        token = AuthToken.objects.create(
            user=user,
            token_hash='iptoken123',
            token_prefix='ip_',
            name='IP Restricted Token',
            ip_whitelist=whitelist
        )
        
        assert token.ip_whitelist == whitelist
    
    def test_auth_token_multiple_per_user(self):
        """Test multiple AuthTokens per user"""
        user = User.objects.create_user(username='multiuser', email='multi@example.com')
        
        token1 = AuthToken.objects.create(
            user=user,
            token_hash='token1hash',
            token_prefix='t1_',
            name='Token 1'
        )
        token2 = AuthToken.objects.create(
            user=user,
            token_hash='token2hash',
            token_prefix='t2_',
            name='Token 2'
        )
        token3 = AuthToken.objects.create(
            user=user,
            token_hash='token3hash',
            token_prefix='t3_',
            name='Token 3'
        )
        
        user_tokens = AuthToken.objects.filter(user=user)
        assert user_tokens.count() == 3
        assert token1 in user_tokens
        assert token2 in user_tokens
        assert token3 in user_tokens
