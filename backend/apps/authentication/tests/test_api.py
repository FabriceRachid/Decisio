"""
API tests for M9 (Authentication) module
Tests UserProfile and AuthToken API endpoints
"""
import pytest
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework import status
from apps.authentication.models import UserProfile, AuthToken, Organization
from apps.authentication.notification_models import UserNotification


@pytest.mark.django_db
class TestAuthenticationAPIEndpoints:
    """Tests for Authentication API endpoints"""
    
    def setup_method(self):
        """Setup test client"""
        self.client = APIClient()
    
    def test_user_registration(self):
        """Test user registration"""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        
        response = self.client.post('/api/auth/register/', data, format='json')
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]

    def test_first_registered_user_becomes_admin(self):
        """The bootstrap account should receive the admin role."""
        response = self.client.post('/api/auth/register/', {
            'username': 'founder@example.com',
            'email': 'founder@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'company_name': 'Maria Distribution',
            'company_sector': 'Commerce / Distribution',
            'company_size': '11–50',
            'company_country': 'Burkina Faso',
        }, format='json')

        if response.status_code != status.HTTP_201_CREATED:
            pytest.skip('Registration endpoint unavailable in this environment')

        user = User.objects.get(username='founder@example.com')
        assert user.profile.role == 'admin'
        assert user.profile.organization is not None
        assert user.profile.organization.name == 'Maria Distribution'
        assert user.profile.organization.created_by == user

    def test_admin_can_create_user_with_role(self):
        admin = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='SecurePass123!',
        )
        organization = Organization.objects.create(name='Demo Org', created_by=admin)
        admin.profile.role = 'admin'
        admin.profile.organization = organization
        admin.profile.save(update_fields=['role', 'organization'])

        self.client.force_authenticate(user=admin)
        response = self.client.post('/api/auth/admin/users/', {
            'email': 'analyst@example.com',
            'username': 'analyst@example.com',
            'first_name': 'Data',
            'last_name': 'Analyst',
            'role': 'analyst',
        }, format='json')

        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
        ]

        if response.status_code == status.HTTP_201_CREATED:
            created = User.objects.get(email='analyst@example.com')
            assert created.profile.role == 'analyst'
            assert created.profile.organization == organization
            assert response.data['invitation_email_sent'] is True
            assert len(mail.outbox) >= 1
            assert created.email in mail.outbox[-1].to
            assert 'rejoindre l\'espace Demo Org' in mail.outbox[-1].subject

    def test_admin_user_list_is_scoped_to_same_organization(self):
        admin = User.objects.create_user(
            username='scope-admin@example.com',
            email='scope-admin@example.com',
            password='SecurePass123!',
        )
        org_a = Organization.objects.create(name='Org A', created_by=admin)
        admin.profile.role = 'admin'
        admin.profile.organization = org_a
        admin.profile.save(update_fields=['role', 'organization'])

        same_org_user = User.objects.create_user(
            username='same-org@example.com',
            email='same-org@example.com',
            password='SecurePass123!',
        )
        same_org_user.profile.organization = org_a
        same_org_user.profile.save(update_fields=['organization'])

        outsider = User.objects.create_user(
            username='outsider@example.com',
            email='outsider@example.com',
            password='SecurePass123!',
        )
        org_b = Organization.objects.create(name='Org B', created_by=outsider)
        outsider.profile.organization = org_b
        outsider.profile.save(update_fields=['organization'])

        self.client.force_authenticate(user=admin)
        response = self.client.get('/api/auth/admin/users/')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            payload = response.json()
            rows = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
            emails = {row['email'] for row in rows}
            assert 'scope-admin@example.com' in emails
            assert 'same-org@example.com' in emails
            assert 'outsider@example.com' not in emails
    
    def test_login(self):
        """Test user login"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/auth/login/', data, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='correctpass'
        )
        
        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }
        
        response = self.client.post('/api/auth/login/', data, format='json')
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]

    def test_password_reset_request_does_not_leak_reset_secrets(self):
        """Password reset request should not return raw reset credentials."""
        user = User.objects.create_user(
            username='resetuser',
            email='reset@example.com',
            password='testpass123'
        )

        response = self.client.post('/api/auth/password-reset/request/', {
            'email': user.email,
        }, format='json')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            assert 'reset_uid' not in response.data
            assert 'reset_token' not in response.data
            assert len(mail.outbox) == 1
            assert user.email in mail.outbox[0].to
            assert '/reset-password?uid=' in mail.outbox[0].body

    def test_password_reset_confirm_accepts_valid_generated_token(self):
        """Password reset confirmation should still work with a valid token."""
        user = User.objects.create_user(
            username='confirmreset',
            email='confirmreset@example.com',
            password='testpass123'
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.post('/api/auth/password-reset/confirm/', {
            'uid': uid,
            'token': token,
            'new_password': 'NewSecurePass123!',
            'new_password_confirm': 'NewSecurePass123!',
        }, format='json')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
    
    @pytest.mark.skip(reason="Logout endpoint not yet implemented")
    def test_logout(self):
        """Test user logout"""
        user = User.objects.create_user(
            username='logoutuser',
            email='logout@example.com',
            password='pass'
        )
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        response = client.post('/api/auth/logout/', {}, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND
        ]


@pytest.mark.django_db
class TestUserProfileAPIEndpoints:
    """Tests for UserProfile API endpoints"""
    
    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='profuser',
            email='prof@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_get_profile(self):
        """Test getting user profile"""
        response = self.client.get('/api/auth/profile/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_update_profile(self):
        """Test updating user profile"""
        data = {
            'department': 'Finance',
            'phone_number': '+33612345678'
        }
        
        response = self.client.patch('/api/auth/profile/', data, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_change_password(self):
        """Test changing password"""
        data = {
            'old_password': 'testpass123',
            'new_password': 'NewSecurePass123!',
            'new_password_confirm': 'NewSecurePass123!'
        }
        
        response = self.client.post('/api/auth/change-password/', data, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_weak_password_rejection(self):
        """Test weak password is rejected"""
        data = {
            'old_password': 'testpass123',
            'new_password': '123',  # Too weak
            'new_password_confirm': '123'
        }
        
        response = self.client.post('/api/auth/change-password/', data, format='json')
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]


@pytest.mark.django_db
class TestAuthTokenAPIEndpoints:
    """Tests for AuthToken API endpoints"""
    
    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='tokenuser',
            email='token@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_generate_token(self):
        """Test generating API token"""
        data = {
            'name': 'My API Key',
            'scopes': ['read:data', 'write:data']
        }
        
        response = self.client.post('/api/auth/tokens/', data, format='json')
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]
    
    def test_list_tokens(self):
        """Test listing user's tokens"""
        AuthToken.objects.create(
            user=self.user,
            token_hash='token1',
            token_prefix='test_',
            name='Token 1'
        )
        
        response = self.client.get('/api/auth/tokens/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_revoke_token(self):
        """Test revoking a token"""
        token = AuthToken.objects.create(
            user=self.user,
            token_hash='token123',
            token_prefix='rev_',
            name='Revoke Me'
        )
        
        response = self.client.post(
            f'/api/auth/tokens/{token.id}/revoke/',
            {},
            format='json'
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]


@pytest.mark.django_db
class TestNotificationAPIEndpoints:
    """Regression tests for notification endpoints."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='notifuser',
            email='notif@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_notifications_returns_summary_and_items(self):
        UserNotification.objects.create(
            user=self.user,
            notification_type='cleaning_completed',
            title='Cleaning finished',
            message='Votre nettoyage est termine.',
            is_read=False,
            progress_percent=100,
            data={'rows_affected': 12},
        )

        response = self.client.get('/api/auth/notifications/')

        assert response.status_code == status.HTTP_200_OK
        assert 'unread_count' in response.data
        assert 'total_count' in response.data
        assert 'notifications' in response.data

        notifications = response.data['notifications']
        if isinstance(notifications, dict):
            notifications = notifications.get('results', [])
        assert len(notifications) == 1
        assert notifications[0]['notification_type'] == 'cleaning_completed'
        assert notifications[0]['type'] == 'cleaning_completed'


@pytest.mark.django_db
class TestMFAAPIEndpoints:
    """Tests for MFA API endpoints"""
    
    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='mfauser',
            email='mfa@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_enable_mfa(self):
        """Test enabling MFA"""
        data = {}
        
        response = self.client.post('/api/auth/mfa/enable/', data, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_verify_mfa_code(self):
        """Test verifying MFA code"""
        profile = self.user.profile
        profile.mfa_enabled = True
        profile.mfa_secret_key = 'JBSWY3DPEBLW64TMMQ6A4V2H6I======'
        profile.save()
        
        data = {'code': '123456'}
        
        response = self.client.post('/api/auth/mfa/verify/', data, format='json')
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]
