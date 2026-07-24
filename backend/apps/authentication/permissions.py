"""
Custom Permission Classes for Role-Based Access Control (RBAC)
Define who can access what based on user roles
"""

from rest_framework import permissions

from apps.ingestion.models import DataSource


class BaseRolePermission(permissions.BasePermission):
    """Base class for role-based permissions"""
    
    required_role = None
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers can do anything
        if request.user.is_superuser:
            return True
        
        # Check user's role
        user_role = request.user.profile.role
        return user_role == self.required_role or self._has_higher_role(user_role)
    
    def _has_higher_role(self, user_role):
        """Check if user has a higher role than required"""
        role_hierarchy = {'viewer': 1, 'analyst': 2, 'admin': 3}
        return role_hierarchy.get(user_role, 0) > role_hierarchy.get(self.required_role, 0)


class IsAdminRole(BaseRolePermission):
    """Permission for admin users only"""
    required_role = 'admin'


class IsAnalystRole(BaseRolePermission):
    """Permission for analyst and admin users"""
    required_role = 'analyst'


class IsViewerRole(BaseRolePermission):
    """Permission for viewer, analyst, and admin users"""
    required_role = 'viewer'


class CanReadData(permissions.BasePermission):
    """Permission to read data"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        role = request.user.profile.role
        return role in ['viewer', 'analyst', 'admin']


class CanWriteData(permissions.BasePermission):
    """Permission to write/modify data"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        role = request.user.profile.role
        return role in ['analyst', 'admin']


class CanDeleteData(permissions.BasePermission):
    """Permission to delete data"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        role = request.user.profile.role
        return role == 'admin'


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object-level permission to only allow owners to edit"""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions allowed for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsOwnerOrAdmin(permissions.BasePermission):
    """Object-level permission for owner or admin"""
    
    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.is_superuser or request.user.profile.role == 'admin':
            return True
        
        # Owner can manage their own object
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class HasSourceAccess(permissions.BasePermission):
    """Allow access to a source when the user owns it or has elevated data access."""

    message = 'You do not have access to this data source.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        source_id = request.data.get('source_id') if hasattr(request, 'data') else None
        if source_id is None:
            source_id = request.query_params.get('source_id')

        if not source_id:
            return True

        try:
            source = DataSource.objects.select_related('uploaded_by').get(pk=source_id)
        except (DataSource.DoesNotExist, ValueError, TypeError):
            return False

        if source.uploaded_by_id == request.user.id:
            return True

        return getattr(request.user.profile, 'role', None) in {'analyst', 'admin'}
