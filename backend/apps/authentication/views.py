"""
API Views for Authentication Module
Handles user registration, login, profile management, and token operations
"""

from datetime import timedelta
import hashlib
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.authentication.serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    AuthTokenSerializer,
    TokenCreateSerializer,
    AdminUserSerializer,
    AdminUserCreateSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from apps.authentication.models import UserProfile, AuthToken
from apps.authentication.permissions import IsAdminRole, IsAnalystRole


# ==================== JWT Token Endpoints ====================

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view
    Returns access + refresh tokens on successful login
    """
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code != status.HTTP_200_OK:
            return response

        username = request.data.get('username')
        if not username:
            return response

        # Add user info to response
        user = User.objects.filter(username=username).select_related('profile').first()
        if not user:
            return response

        response.data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.profile.role,
        }
        
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom token refresh view with rotation.
    Blacklists the old refresh token and returns a new pair (access + refresh).
    """

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            old_refresh = RefreshToken(refresh_token)
        except TokenError:
            return Response(
                {'error': 'Invalid or expired refresh token'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = old_refresh.get('user_id')
        if user_id is None:
            return Response(
                {'error': 'Token missing user claim'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            old_refresh.blacklist()
        except Exception:
            pass

        new_refresh = RefreshToken.for_user_id(user_id)

        return Response({
            'access': str(new_refresh.access_token),
            'refresh': str(new_refresh),
            'token_type': 'Bearer',
        })


# ==================== User Registration & Login ====================

class UserRegistrationView(generics.CreateAPIView):
    """
    Register a new user
    POST /api/auth/register/
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    User login endpoint
    POST /api/auth/login/
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_lookup = User.objects.filter(username=username).select_related('profile').first()
        profile = getattr(user_lookup, 'profile', None) if user_lookup else None

        if profile and profile.is_locked:
            return Response(
                {
                    'error': 'Account temporarily locked due to repeated failed logins',
                    'locked_until': profile.locked_until,
                },
                status=status.HTTP_423_LOCKED
            )

        user = authenticate(username=username, password=password)

        if not user:
            if profile:
                profile.register_failed_login()
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        profile = user.profile
        profile.reset_login_failures()
        profile.last_login_ip = _get_client_ip(request)
        profile.save(update_fields=['last_login_ip', 'updated_at'])

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'token_type': 'Bearer',
        })


# ==================== User Profile Management ====================

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get and update current user profile
    GET/PUT /api/auth/profile/
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """
    Change user password
    POST /api/auth/change-password/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        
        # Verify old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        user.profile.mark_password_changed()
        
        return Response({
            'message': 'Password changed successfully'
        })


class LogoutView(APIView):
    """
    Blacklist the provided refresh token.
    POST /api/auth/logout/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh = RefreshToken(serializer.validated_data['refresh_token'])
            refresh.blacklist()
        except TokenError:
            return Response({'error': 'Invalid or expired refresh token'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Logout successful'})


class LogoutAllView(APIView):
    """
    Blacklist all outstanding refresh tokens for the current user.
    POST /api/auth/logout-all/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        outstanding_tokens = request.user.outstandingtoken_set.all()
        blacklisted = 0

        for token in outstanding_tokens:
            try:
                RefreshToken(str(token.token)).blacklist()
                blacklisted += 1
            except TokenError:
                continue

        return Response({
            'message': 'All active refresh tokens were revoked',
            'revoked_tokens': blacklisted,
        })


# ==================== API Token Management ====================

class APITokenListView(generics.ListCreateAPIView):
    """
    List and create API tokens for authenticated user
    GET/POST /api/auth/tokens/
    """
    serializer_class = AuthTokenSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return AuthToken.objects.filter(user=self.request.user, is_active=True)

    def create(self, request, *args, **kwargs):
        request_serializer = TokenCreateSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        # Generate secure token
        token_string = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token_string.encode()).hexdigest()
        token_prefix = token_string[:8]

        # Calculate expiration
        expires_in_days = request_serializer.validated_data['expires_in_days']
        expires_at = timezone.now() + timedelta(days=expires_in_days)

        # Create token
        token = AuthToken.objects.create(
            user=self.request.user,
            token_hash=token_hash,
            token_prefix=token_prefix,
            name=request_serializer.validated_data['name'],
            scopes=request_serializer.validated_data['scopes'],
            expires_at=expires_at,
            rate_limit=request_serializer.validated_data['rate_limit'],
            created_by_ip=_get_client_ip(request),
        )

        response_data = AuthTokenSerializer(token).data
        response_data['token'] = token_string  # Show full token once
        return Response(response_data, status=status.HTTP_201_CREATED)


class APITokenRevokeView(APIView):
    """
    Revoke (delete) an API token
    POST /api/auth/tokens/<id>/revoke/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, token_id):
        token = get_object_or_404(AuthToken, id=token_id, user=request.user)
        token.revoke('Revoked by user')
        
        return Response({
            'message': f'Token "{token.name}" has been revoked'
        })


class PasswordResetRequestView(APIView):
    """
    Request a password reset token.
    POST /api/auth/password-reset/request/
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = User.objects.filter(email=email, is_active=True).select_related('profile').first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}"

            html_message = render_to_string('emails/password_reset.html', {
                'user': user,
                'reset_url': reset_url,
            })

            send_mail(
                subject='DecisioBI - Réinitialisation de mot de passe',
                message=f'Cliquez sur ce lien pour réinitialiser votre mot de passe : {reset_url}',
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

        return Response({
            'message': 'Si un compte existe avec cet email, un lien de réinitialisation a été envoyé.'
        })


class PasswordResetConfirmView(APIView):
    """
    Confirm a password reset.
    POST /api/auth/password-reset/confirm/
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
            user = User.objects.get(pk=user_id, is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data['token']
        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired reset token'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        user.profile.mark_password_changed()
        user.profile.reset_login_failures()

        return Response({'message': 'Password reset successful'})


# ==================== Admin User Management ====================

class AdminUserListView(generics.ListCreateAPIView):
    """
    List or create users (Admin only)
    GET/POST /api/auth/admin/users/
    """
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        organization = getattr(self.request.user.profile, 'organization', None)
        queryset = User.objects.select_related('profile', 'profile__organization').order_by('-date_joined')
        if organization is None:
            return queryset.filter(id=self.request.user.id)
        return queryset.filter(profile__organization=organization)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        invitation_email_sent = False
        if user.email:
            raw_password = getattr(user, '_raw_password', None)
            org_name = user.profile.organization.name if user.profile.organization else 'DecisioBI'
            role_display = dict(UserProfile.ROLE_CHOICES).get(user.profile.role, user.profile.role)
            login_url = f"{settings.FRONTEND_BASE_URL}/login"

            html_message = render_to_string('emails/invitation.html', {
                'first_name': user.first_name,
                'username': user.username,
                'password': raw_password,
                'organization_name': org_name,
                'role': role_display,
                'login_url': login_url,
            })

            try:
                send_mail(
                    subject=f'Bienvenue sur {org_name} - DecisioBI',
                    message=f'Vous avez été invité sur {org_name}. Connectez-vous ici : {login_url}',
                    html_message=html_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                invitation_email_sent = True
            except Exception:
                invitation_email_sent = False

        response_data = AdminUserSerializer(user).data
        response_data['invitation_email_sent'] = invitation_email_sent
        return Response(response_data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete specific user (Admin only)
    GET/PUT/DELETE /api/auth/admin/users/<id>/
    """
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        organization = getattr(self.request.user.profile, 'organization', None)
        queryset = User.objects.select_related('profile', 'profile__organization')
        if organization is None:
            return queryset.filter(id=self.request.user.id)
        return queryset.filter(profile__organization=organization)


class AdminUpdateUserRoleView(APIView):
    """
    Update user role (Admin only)
    POST /api/auth/admin/users/<id>/update-role/
    """
    permission_classes = [IsAdminRole]
    
    def post(self, request, user_id):
        organization = getattr(request.user.profile, 'organization', None)
        if organization is None:
            user = get_object_or_404(User, id=user_id)
            if user.id != request.user.id:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            user = get_object_or_404(User.objects.select_related('profile'), id=user_id, profile__organization=organization)
        role = request.data.get('role')
        
        if not role:
            return Response(
                {'error': 'Role is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_roles = [choice[0] for choice in UserProfile.ROLE_CHOICES]
        if role not in valid_roles:
            return Response(
                {'error': f'Invalid role. Must be one of: {valid_roles}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.profile.role = role
        user.profile.save()
        
        return Response({
            'message': f'User role updated to {role}',
            'user': AdminUserSerializer(user).data
        })


# ==================== Utility Endpoints ====================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_auth_status(request):
    """
    Check current authentication status
    GET /api/auth/status/
    """
    user = request.user
    return Response({
        'is_authenticated': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.profile.role,
            'failed_login_attempts': user.profile.failed_login_attempts,
            'locked_until': user.profile.locked_until,
        }
    })


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
