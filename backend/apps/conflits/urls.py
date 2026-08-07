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
    ReportConfigViewSet,
    TriggerReportView,
    ReportHistoryView,
    ActivityFeedView,
    PresenceHeartbeatView,
    PresenceListView,
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

    # Reporting
    path('reports/', ReportConfigViewSet.as_view({'get': 'list', 'post': 'create'}), name='report-list'),
    path('reports/<int:pk>/', ReportConfigViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='report-detail'),
    path('reports/trigger/', TriggerReportView.as_view(), name='report-trigger'),
    path('reports/history/', ReportHistoryView.as_view(), name='report-history'),

    # Activity feed (org-scoped)
    path('activity-feed/', ActivityFeedView.as_view(), name='activity_feed'),

    # Presence
    path('presence/heartbeat/', PresenceHeartbeatView.as_view(), name='presence_heartbeat'),
    path('presence/', PresenceListView.as_view(), name='presence_list'),
]
