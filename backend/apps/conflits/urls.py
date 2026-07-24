"""
M3: Conflict Detection & Resolution URL Configuration
API endpoints for conflict management, guided resolution, and audit trails.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.conflits.views import (
    ConflictTypeViewSet,
    ConflictViewSet,
    ConflictResolutionViewSet,
    ActivityLogViewSet,
    ConflictDetectionAPIView,
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'types', ConflictTypeViewSet, basename='conflicttype')
router.register(r'conflicts', ConflictViewSet, basename='conflict')
router.register(r'resolutions', ConflictResolutionViewSet, basename='conflictresolution')
router.register(r'activity-log', ActivityLogViewSet, basename='activitylog')

urlpatterns = [
    # ViewSet routes
    path('', include(router.urls)),
    
    # Manual detection endpoint
    path('detect/', ConflictDetectionAPIView.as_view(), name='conflict_detect'),
]
