"""
M3: Conflict Detection & Resolution API Views
REST endpoints for conflict management and guided resolution workflow.
"""

from rest_framework import viewsets, generics, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Case, When, IntegerField
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models
from django.core.cache import cache

from apps.conflits.models import (
    ConflictType, Conflict, ConflictResolution, ActivityLog, ScheduledJob
)
from apps.conflits.serializers import (
    ConflictTypeSerializer, ConflictListSerializer, ConflictDetailSerializer,
    ConflictResolutionSerializer, ConflictResolutionGuidanceSerializer,
    ConflictResolutionRequestSerializer, ConflictBulkActionSerializer,
    ActivityLogSerializer, ConflictDashboardStatSerializer,
    ReportConfigSerializer, TriggerReportSerializer,
)
from apps.conflits.services import ConflictDetectionService, ConflictResolutionService
from apps.conflits.audit import log_activity
from apps.authentication.permissions import CanReadData, CanWriteData
from apps.ingestion.models import DataSource
from apps.nettoyage.models import CleaningJob
from django.shortcuts import get_object_or_404


def _is_admin_user(user):
    return user.is_superuser or user.is_staff or user.profile.role == 'admin'


def _organization_id_for_user(user):
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'organization_id', None)


def _organization_scoped_sources(queryset, user):
    if user.is_superuser:
        return queryset

    organization_id = _organization_id_for_user(user)
    if organization_id:
        return queryset.filter(uploaded_by__profile__organization_id=organization_id)

    return queryset.filter(uploaded_by=user)


def _validated_source_ids_for_queryset(queryset):
    source_ids = list(queryset.values_list('id', flat=True))
    validated_ids = []

    for source_id in source_ids:
        jobs = (
            CleaningJob.objects.filter(source_id=source_id, status='completed')
            .prefetch_related('cleaned_results')
            .order_by('-completed_at', '-created_at')
        )
        for job in jobs:
            total = job.cleaned_results.count()
            if total and job.cleaned_results.filter(is_validated=True).count() == total:
                validated_ids.append(source_id)
                break

    return validated_ids


class ConflictTypeViewSet(viewsets.ModelViewSet):
    """
    Conflict Type definitions
    
    GET /api/conflits/types/ - List all conflict types
    POST /api/conflits/types/ - Create new conflict type (admin only)
    GET /api/conflits/types/{id}/ - Get conflict type details
    """
    queryset = ConflictType.objects.all()
    serializer_class = ConflictTypeSerializer
    permission_classes = [IsAuthenticated, CanReadData]
    filterset_fields = ['severity', 'auto_resolve']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['severity', 'name']
    ordering = ['severity', 'name']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CanWriteData()]
        return super().get_permissions()


class ConflictViewSet(viewsets.ModelViewSet):
    """
    Conflict management and resolution
    
    GET /api/conflits/conflicts/ - List all conflicts with filtering
    POST /api/conflits/conflicts/ - This endpoint is not used (conflicts are auto-detected)
    GET /api/conflits/conflicts/{id}/ - Get detailed conflict info
    PATCH /api/conflits/conflicts/{id}/ - Update conflict metadata
    """
    queryset = Conflict.objects.select_related('conflict_type', 'data_source', 'assigned_to').prefetch_related('resolutions')
    serializer_class = ConflictListSerializer
    permission_classes = [IsAuthenticated, CanReadData]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'conflict_type__code', 'data_source']
    search_fields = ['description', 'conflict_type__name']
    ordering_fields = ['priority', 'detected_at', 'impact_score']
    ordering = ['-priority', '-detected_at']

    WRITE_ACTIONS = {
        'create', 'update', 'partial_update', 'destroy',
        'acknowledge', 'assign', 'resolve', 'bulk_action'
    }

    def get_permissions(self):
        if self.action in self.WRITE_ACTIONS:
            return [IsAuthenticated(), CanWriteData()]
        return [IsAuthenticated(), CanReadData()]
    
    def get_queryset(self):
        """Users can only see conflicts from their own organization sources (unless admin)"""
        user = self.request.user
        validated_source_ids = _validated_source_ids_for_queryset(
            _organization_scoped_sources(DataSource.objects.all(), user)
        )
        base_queryset = self.queryset.filter(data_source_id__in=validated_source_ids)
        if _is_admin_user(user):
            organization_id = _organization_id_for_user(user)
            if organization_id:
                return base_queryset.filter(data_source__uploaded_by__profile__organization_id=organization_id).distinct()
            return base_queryset.distinct()
        organization_id = _organization_id_for_user(user)
        base_query = Q(data_source__uploaded_by=user)
        if organization_id:
            base_query = Q(data_source__uploaded_by__profile__organization_id=organization_id)
        return base_queryset.filter(
            base_query |
            Q(assigned_to=user) |
            Q(acknowledged_by=user)
        ).distinct()
    
    def retrieve(self, request, *args, **kwargs):
        """Use detailed serializer for single conflict"""
        instance = self.get_object()
        serializer = ConflictDetailSerializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Conflicts are created via detection workflows, not direct API writes."""
        return Response(
            {'error': 'Conflicts must be created through the detection workflow'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    @action(
        detail=True,
        methods=['get'],
        serializer_class=ConflictResolutionGuidanceSerializer,
        permission_classes=[IsAuthenticated, CanReadData]
    )
    def guidance(self, request, pk=None):
        """
        Get guided resolution workflow for a conflict
        
        GET /api/conflits/conflicts/{id}/guidance/
        
        Returns step-by-step guidance on how to resolve this conflict.
        """
        conflict = self.get_object()
        service = ConflictResolutionService(request.user)
        guidance = service.get_conflict_resolution_guidance(conflict)
        serializer = ConflictResolutionGuidanceSerializer(guidance)
        return Response(serializer.data)
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated, CanWriteData]
    )
    def acknowledge(self, request, pk=None):
        """
        Acknowledge that you're working on this conflict
        
        POST /api/conflits/conflicts/{id}/acknowledge/
        """
        conflict = self.get_object()
        conflict.acknowledged_by = request.user
        conflict.acknowledged_at = timezone.now()
        if conflict.status == 'detected':
            conflict.status = 'investigating'
        conflict.save(update_fields=['acknowledged_by', 'acknowledged_at', 'status'])
        
        return Response({
            'success': True,
            'message': f'Acknowledged conflict {conflict.id}',
            'status': conflict.get_status_display()
        })
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated, CanWriteData]
    )
    def assign(self, request, pk=None):
        """
        Assign conflict to a user
        
        POST /api/conflits/conflicts/{id}/assign/
        Payload: {"assigned_to_id": 5}
        """
        conflict = self.get_object()
        assigned_to_id = request.data.get('assigned_to_id')
        
        if not assigned_to_id:
            return Response(
                {'error': 'assigned_to_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            assigned_user = User.objects.get(id=assigned_to_id, is_active=True)
            conflict.assigned_to = assigned_user
            conflict.save(update_fields=['assigned_to'])
            
            return Response({
                'success': True,
                'message': f'Assigned to {assigned_user.username}',
                'assigned_to': assigned_user.username
            })
        except User.DoesNotExist:
            return Response(
                {'error': f'User {assigned_to_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated, CanWriteData]
    )
    def resolve(self, request, pk=None):
        """
        Resolve a conflict with chosen strategy
        
        POST /api/conflits/conflicts/{id}/resolve/
        Payload: {
            "resolution_method": "user_selected",
            "chosen_value": {...},
            "resolution_notes": "Selected option A...",
            "requires_approval": false
        }
        """
        conflict = self.get_object()
        
        serializer = ConflictResolutionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = ConflictResolutionService(request.user)
        result = service.resolve_conflict(
            conflict=conflict,
            method=serializer.validated_data['resolution_method'],
            chosen_value=serializer.validated_data.get('chosen_value'),
            notes=serializer.validated_data.get('resolution_notes'),
            requires_approval=serializer.validated_data.get('requires_approval', False)
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAuthenticated, CanWriteData]
    )
    def bulk_action(self, request):
        """
        Perform action on multiple conflicts
        
        POST /api/conflits/conflicts/bulk_action/
        Payload: {
            "conflict_ids": [1, 2, 3],
            "action": "assign_to_user",
            "assigned_to_id": 5
        }
        """
        serializer = ConflictBulkActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        conflict_ids = serializer.validated_data['conflict_ids']
        action_type = serializer.validated_data['action']
        
        conflicts = self.get_queryset().filter(id__in=conflict_ids)
        if conflicts.count() != len(conflict_ids):
            return Response(
                {'error': 'One or more conflicts were not found or are not accessible'},
                status=status.HTTP_404_NOT_FOUND
            )
        updated_count = 0
        
        if action_type == 'assign_to_user':
            assigned_to_id = serializer.validated_data.get('assigned_to_id')
            assigned_user = get_object_or_404(User, id=assigned_to_id, is_active=True)
            updated_count = conflicts.update(assigned_to=assigned_user)
        
        elif action_type == 'change_priority':
            priority = serializer.validated_data.get('new_priority')
            updated_count = conflicts.update(priority=priority)
        
        elif action_type == 'change_status':
            new_status = serializer.validated_data.get('new_status')
            updated_count = conflicts.update(status=new_status)
        
        elif action_type == 'add_to_group':
            group_name = serializer.validated_data.get('group_name')
            updated_count = conflicts.update(group_name=group_name)
        
        return Response({
            'success': True,
            'action': action_type,
            'updated_count': updated_count,
            'message': f'Updated {updated_count} conflicts'
        })
    
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated, CanReadData]
    )
    def dashboard_stats(self, request):
        """
        Get dashboard statistics for conflicts
        
        GET /api/conflits/conflicts/dashboard_stats/
        """
        user = request.user

        cache_key = f'conflict_dashboard_stats_{user.id}'
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return Response(cached_stats)

        organization_id = _organization_id_for_user(user)
        validated_source_ids = _validated_source_ids_for_queryset(
            _organization_scoped_sources(DataSource.objects.all(), user)
        )
        if user.is_superuser:
            conflicts = Conflict.objects.filter(data_source_id__in=validated_source_ids).distinct()
        elif organization_id:
            conflicts = Conflict.objects.filter(
                data_source__uploaded_by__profile__organization_id=organization_id,
                data_source_id__in=validated_source_ids,
            ).distinct()
        else:
            conflicts = Conflict.objects.filter(
                data_source__uploaded_by=user,
                data_source_id__in=validated_source_ids,
            ).distinct()
        
        # Calculate statistics
        total = conflicts.count()
        by_status = dict(
            conflicts.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        by_severity = dict(
            conflicts.values('conflict_type__severity').annotate(count=Count('id')).values_list('conflict_type__severity', 'count')
        )
        by_type = dict(
            conflicts.values('conflict_type__code').annotate(count=Count('id')).values_list('conflict_type__code', 'count')
        )
        
        critical_count = conflicts.filter(priority__gte=9).count()
        
        # Overdue (due_date passed)
        overdue_count = conflicts.filter(
            due_date__lt=timezone.now(),
            status__in=['detected', 'investigating']
        ).count()
        
        assigned_to_user = conflicts.filter(assigned_to=user).count()
        
        # Average resolution time
        resolved = ConflictResolution.objects.filter(
            conflict__in=conflicts
        ).exclude(resolved_at__isnull=True)
        
        avg_time = 0
        if resolved.exists():
            avg_time = resolved.aggregate(
                avg_time=models.Avg(
                    models.F('resolved_at') - models.F('conflict__detected_at'),
                    output_field=models.DurationField()
                )
            )['avg_time']
            if avg_time:
                avg_time = avg_time.total_seconds() / 60  # Convert to minutes
        
        resolution_rate = (
            (conflicts.filter(status='resolved').count() / total * 100)
            if total > 0 else 0
        )
        
        stats = {
            'total_conflicts': total,
            'by_status': by_status,
            'by_severity': by_severity,
            'by_type': by_type,
            'critical_count': critical_count,
            'overdue_count': overdue_count,
            'assigned_to_current_user': assigned_to_user,
            'avg_resolution_time_minutes': float(avg_time) if avg_time else 0,
            'resolution_rate_percent': round(resolution_rate, 2)
        }
        
        serializer = ConflictDashboardStatSerializer(stats)
        data = serializer.data
        cache.set(cache_key, data, timeout=30)
        return Response(data)


class ConflictResolutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Resolution history and audit trail
    
    GET /api/conflits/resolutions/ - List all resolutions
    GET /api/conflits/resolutions/{id}/ - Get resolution details
    """
    queryset = ConflictResolution.objects.select_related(
        'conflict', 'resolved_by', 'reviewed_by', 'approved_by'
    ).order_by('-resolved_at')
    serializer_class = ConflictResolutionSerializer
    permission_classes = [IsAuthenticated, CanReadData]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['conflict', 'resolution_method']
    ordering_fields = ['resolved_at']

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset
        if _is_admin_user(user):
            return queryset
        return queryset.filter(
            Q(conflict__data_source__uploaded_by=user) |
            Q(conflict__assigned_to=user) |
            Q(conflict__acknowledged_by=user)
        ).distinct()


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit trail of all user actions
    
    GET /api/conflits/activity-log/ - List all activities
    GET /api/conflits/activity-log/{id}/ - Get activity details
    """
    queryset = ActivityLog.objects.select_related('user').order_by('-created_at')
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'action_type', 'resource_type', 'flagged_for_review']
    search_fields = ['resource_name', 'user__email']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        """Non-admin users can only see their own activities"""
        user = self.request.user
        if _is_admin_user(user):
            return self.queryset
        return self.queryset.filter(user=user)


class ConflictDetectionAPIView(generics.CreateAPIView):
    """
    Manually trigger conflict detection on a data source
    
    POST /api/conflits/detect/
    Payload: {
        "source_id": 5,
        "check_types": ["DUPLICATE_RECORDS", "MISSING_VALUES"]
    }
    
    Returns: Detected conflicts
    """
    permission_classes = [IsAuthenticated, CanWriteData]

    def _has_validated_cleaning(self, source: DataSource) -> bool:
        jobs = (
            CleaningJob.objects.filter(source=source, status='completed')
            .prefetch_related('cleaned_results')
            .order_by('-completed_at', '-created_at')
        )
        for job in jobs:
            total = job.cleaned_results.count()
            if total and job.cleaned_results.filter(is_validated=True).count() == total:
                return True
        return False
    
    def create(self, request, *args, **kwargs):
        source_id = request.data.get('source_id')
        check_types = request.data.get('check_types', [])
        
        if not source_id:
            return Response(
                {'error': 'source_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            source = _organization_scoped_sources(DataSource.objects.all(), request.user).get(id=source_id)
            if not self._has_validated_cleaning(source):
                return Response(
                    {
                        'error': 'Cette source ne peut pas entrer dans M3 tant que son nettoyage n’a pas été validé.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check permission
            service = ConflictDetectionService(request.user)
            result = service.detect_conflicts_in_source(source, check_types=check_types)
            serialized_conflicts = ConflictDetailSerializer(
                result.get('conflicts', []),
                many=True,
            ).data
            payload = {
                **result,
                'conflicts': serialized_conflicts,
            }
            return Response(payload, status=status.HTTP_200_OK)
        
        except DataSource.DoesNotExist:
            return Response(
                {'error': f'DataSource {source_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ─── Reporting ───────────────────────────────────────────────

class ReportConfigViewSet(viewsets.ModelViewSet):
    """CRUD for scheduled report configurations."""

    permission_classes = [IsAuthenticated, CanReadData]
    serializer_class = ReportConfigSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return ScheduledJob.objects.filter(
            job_type="report_generation",
            created_by=self.request.user,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(
            job_type="report_generation",
            created_by=self.request.user,
            owned_by=self.request.user,
            is_active=True,
        )


class TriggerReportView(APIView):
    """POST /api/conflits/reports/trigger/ — generate a report immediately."""

    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request):
        ser = TriggerReportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        config_id = ser.validated_data["config_id"]

        config = get_object_or_404(
            ScheduledJob,
            id=config_id,
            job_type="report_generation",
            created_by=request.user,
        )

        params = config.job_parameters or {}
        source_id = params.get("source_id")
        if not source_id:
            return Response(
                {"error": "Aucune source configurée pour ce rapport."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from rest_framework.test import APIRequestFactory

            factory = APIRequestFactory()
            drf_request = factory.post(
                "/api/dashboard/export/pdf/",
                {"source_id": source_id},
                format="json",
            )
            drf_request.user = request.user
            drf_request.auth = request.auth if hasattr(request, "auth") else None

            from apps.dashboard.views import DashboardExportPDFAPIView

            pdf_response = DashboardExportPDFAPIView.as_view()(drf_request)
            if pdf_response.status_code != 200:
                return Response(
                    {"error": "Erreur lors de la génération du PDF."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            pdf_bytes = pdf_response.content

            # Save to disk
            import os
            from django.conf import settings
            from django.utils import timezone

            report_dir = os.path.join(settings.MEDIA_ROOT, "reports")
            os.makedirs(report_dir, exist_ok=True)
            filename = f"report_{config.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(report_dir, filename)
            with open(filepath, "wb") as f:
                f.write(pdf_bytes)

            # Update config tracking
            config.last_run_at = timezone.now()
            config.last_run_status = "success"
            config.save(update_fields=["last_run_at", "last_run_status"])

            # Send email with attached PDF to configured recipients
            recipients = config.notification_recipients or []
            if recipients:
                try:
                    from django.core.mail import EmailMessage
                    from django.conf import settings

                    email = EmailMessage(
                        subject=f"Rapport DécisioBI — {config.job_name}",
                        body=f"Bonjour,\n\nVeuillez trouver ci-joint le rapport « {config.job_name} » généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}.\n\n— DécisioBI",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=recipients,
                    )
                    email.attach(filename, pdf_bytes, "application/pdf")
                    email.send(fail_silently=True)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Report %s generated but email failed: %s", config.id, e
                    )

            log_activity(
                action_type='export',
                resource_type='Report',
                resource_id=config.id,
                resource_name=config.job_name,
                user=request.user,
                request=request,
                details={'filename': filename},
                status_code=status.HTTP_200_OK,
            )

            return Response(
                {
                    "success": True,
                    "filename": filename,
                    "filepath": filepath,
                    "size_bytes": len(pdf_bytes),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            config.last_run_status = "failed"
            config.save(update_fields=["last_run_status"])
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReportHistoryView(APIView):
    """GET /api/conflits/reports/history/ — list generated reports."""

    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        import os, glob
        from django.conf import settings

        report_dir = os.path.join(settings.MEDIA_ROOT, "reports")
        if not os.path.isdir(report_dir):
            return Response([], status=status.HTTP_200_OK)

        files = []
        for fpath in sorted(glob.glob(os.path.join(report_dir, "*.pdf")), reverse=True):
            stat = os.stat(fpath)
            fname = os.path.basename(fpath)
            files.append(
                {
                    "filename": fname,
                    "size_bytes": stat.st_size,
                    "created_at": stat.st_mtime,
                    "download_url": f"{settings.MEDIA_URL}reports/{fname}",
                }
            )

        return Response(files[:50], status=status.HTTP_200_OK)


class ActivityFeedView(APIView):
    """
    GET /api/conflits/activity-feed/
    Returns the 50 most recent activities for the current user's organization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        org_id = _organization_id_for_user(user)

        limit = min(int(request.query_params.get('limit', 50)), 100)
        cache_key = f'activity_feed_{user.id}_{limit}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({'activities': cached})

        if org_id:
            org_user_ids = list(
                User.objects.filter(
                    profile__organization_id=org_id
                ).values_list('id', flat=True)
            )
            queryset = ActivityLog.objects.filter(
                user_id__in=org_user_ids
            ).select_related('user')
        else:
            queryset = ActivityLog.objects.filter(user=user).select_related('user')

        activities = queryset.order_by('-created_at')[:limit]

        data = []
        for a in activities:
            profile = getattr(a.user, 'profile', None) if a.user else None
            data.append({
                'id': a.id,
                'user': {
                    'id': a.user_id,
                    'username': a.user.username if a.user else None,
                    'email': a.user_email,
                    'role': a.user_role,
                },
                'action_type': a.action_type,
                'resource_type': a.resource_type,
                'resource_id': a.resource_id,
                'resource_name': a.resource_name,
                'action_details': a.action_details,
                'created_at': a.created_at.isoformat() if a.created_at else None,
            })

        cache.set(cache_key, data, timeout=15)
        return Response({'activities': data})


# ==================== Presence ====================

_active_users = {}  # {user_id: {'last_seen': datetime, 'org_id': int, 'page': str}}


def _cleanup_stale():
    now = timezone.now()
    stale = [
        uid for uid, info in _active_users.items()
        if (now - info['last_seen']).total_seconds() > 90
    ]
    for uid in stale:
        del _active_users[uid]


class PresenceHeartbeatView(APIView):
    """
    POST /api/auth/presence/heartbeat/
    Body: {"page": "dashboard"} (optional)
    Registers the user as active. Called every 30s by frontend.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        org_id = _organization_id_for_user(user)
        page = request.data.get('page', '')

        _active_users[user.id] = {
            'last_seen': timezone.now(),
            'org_id': org_id,
            'page': page,
            'username': user.username,
            'email': user.email,
            'role': getattr(getattr(user, 'profile', None), 'role', None),
        }

        _cleanup_stale()

        return Response({'status': 'ok'})


class PresenceListView(APIView):
    """
    GET /api/auth/presence/
    Returns the list of currently active members in the same organization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        org_id = _organization_id_for_user(user)
        _cleanup_stale()

        now = timezone.now()
        online = []

        for uid, info in _active_users.items():
            elapsed = (now - info['last_seen']).total_seconds()
            if elapsed > 60:
                continue

            if org_id and info.get('org_id') == org_id:
                online.append({
                    'user_id': uid,
                    'username': info['username'],
                    'email': info['email'],
                    'role': info['role'],
                    'page': info.get('page', ''),
                    'last_seen': info['last_seen'].isoformat(),
                })
            elif uid == user.id:
                online.append({
                    'user_id': uid,
                    'username': info['username'],
                    'email': info['email'],
                    'role': info['role'],
                    'page': info.get('page', ''),
                    'last_seen': info['last_seen'].isoformat(),
                })

        return Response({'online_users': online})
