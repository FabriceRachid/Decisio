"""
URL Configuration for Authentication Module
Defines API endpoints for user authentication and management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.authentication.views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    UserRegistrationView,
    LoginView,
    LogoutView,
    LogoutAllView,
    UserProfileView,
    ChangePasswordView,
    APITokenListView,
    APITokenRevokeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    AdminUserListView,
    AdminUserDetailView,
    AdminUpdateUserRoleView,
    check_auth_status,
)
from apps.authentication.notification_views import (
    NotificationListView,
    NotificationDetailView,
    NotificationMarkAllReadView,
)

# Create router for ViewSets if needed
router = DefaultRouter()
# router.register(r'users', UserViewSet)  # If using ViewSets

urlpatterns = [
    # ==================== JWT Token Endpoints ====================
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    
    # ==================== Public Endpoints ====================
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('login/', LoginView.as_view(), name='user_login'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # ==================== User Management ====================
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('logout-all/', LogoutAllView.as_view(), name='logout_all'),
    
    # ==================== API Token Management ====================
    path('tokens/', APITokenListView.as_view(), name='api_token_list'),
    path('tokens/<int:token_id>/revoke/', APITokenRevokeView.as_view(), name='api_token_revoke'),
    
    # ==================== Utility ====================
    path('status/', check_auth_status, name='auth_status'),
    
    # ==================== Admin Endpoints ====================
    path('admin/users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin_user_detail'),
    path('admin/users/<int:user_id>/update-role/', AdminUpdateUserRoleView.as_view(), name='admin_update_role'),

    # ==================== Notification Endpoints ====================
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification_mark_all_read'),
    path('notifications/<int:notification_id>/', NotificationDetailView.as_view(), name='notification_detail'),
]

# Include router URLs
urlpatterns += router.urls
