from django.db import models
from django.http import HttpResponse
from django.utils.text import slugify
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import CanReadData, CanWriteData
from apps.dashboard.models import Dashboard, Widget, PreferenceUtilisateur, VuePersonnalisee
from apps.dashboard.serializers import (
    DashboardAnalyticsSerializer, DashboardSerializer, WidgetSerializer,
    WidgetReorderSerializer,
    PreferenceUtilisateurSerializer, VuePersonnaliseeSerializer,
)
from apps.dashboard.services import auto_build_dashboard, add_widget_to_dashboard, build_business_rankings, default_preferences_for_role
from apps.kpi.serializers import DashboardPreviewRequestSerializer
from apps.kpi.services import M4WorkbenchService
from apps.conflits.audit import log_activity


class DashboardAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        payload = build_business_rankings(request.user)
        serializer = DashboardAnalyticsSerializer(payload)
        return Response(serializer.data)


class DashboardViewSet(viewsets.ModelViewSet):
    queryset = Dashboard.objects.all().order_by('-updated_at')
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated, CanReadData]

    WRITE_ACTIONS = {'create', 'update', 'partial_update', 'destroy'}

    def get_permissions(self):
        if self.action in self.WRITE_ACTIONS:
            permission_classes = [IsAuthenticated, CanWriteData]
        else:
            permission_classes = [IsAuthenticated, CanReadData]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        qs = Dashboard.objects.all().order_by('-updated_at')
        if self.request.user.is_superuser:
            return qs
        return qs.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        name = serializer.validated_data.get('name', '')
        dashboard = serializer.save(
            created_by=self.request.user,
            slug=serializer.validated_data.get('slug') or slugify(name) or f'dashboard-{self.request.user.id}',
        )
        log_activity(
            action_type='create',
            resource_type='Dashboard',
            resource_id=dashboard.id,
            resource_name=dashboard.name,
            user=self.request.user,
            request=self.request,
        )

    def perform_update(self, serializer):
        dashboard = serializer.save()
        log_activity(
            action_type='update',
            resource_type='Dashboard',
            resource_id=dashboard.id,
            resource_name=dashboard.name,
            user=self.request.user,
            request=self.request,
        )

    def perform_destroy(self, instance):
        log_activity(
            action_type='delete',
            resource_type='Dashboard',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user,
            request=self.request,
            risk_score=30,
        )
        instance.delete()


class WidgetViewSet(viewsets.ModelViewSet):
    queryset = Widget.objects.select_related('dashboard').all().order_by('position_y', 'position_x')
    serializer_class = WidgetSerializer
    permission_classes = [IsAuthenticated, CanReadData]

    SORTABLE_FIELDS = {'title', 'name', 'widget_type', 'position_x', 'position_y', 'created_at', 'updated_at'}

    WRITE_ACTIONS = {'create', 'update', 'partial_update', 'destroy', 'reorder'}

    def get_permissions(self):
        if self.action in self.WRITE_ACTIONS:
            permission_classes = [IsAuthenticated, CanWriteData]
        else:
            permission_classes = [IsAuthenticated, CanReadData]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        qs = Widget.objects.select_related('dashboard').all()
        if not self.request.user.is_superuser:
            qs = qs.filter(dashboard__created_by=self.request.user)

        sort_by = self.request.query_params.get('sort_by', 'position_y')
        sort_order = self.request.query_params.get('sort_order', 'asc')

        if sort_by in self.SORTABLE_FIELDS:
            order_prefix = '' if sort_order == 'asc' else '-'
            qs = qs.order_by(f'{order_prefix}{sort_by}', 'position_x')
        else:
            qs = qs.order_by('position_y', 'position_x')

        dashboard_id = self.request.query_params.get('dashboard_id')
        if dashboard_id:
            qs = qs.filter(dashboard_id=dashboard_id)

        widget_type = self.request.query_params.get('widget_type')
        if widget_type:
            qs = qs.filter(widget_type=widget_type)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(title__icontains=search)

        return qs

    def perform_create(self, serializer):
        widget = serializer.save()
        log_activity(
            action_type='create',
            resource_type='Widget',
            resource_id=widget.id,
            resource_name=widget.title or widget.name or f'Widget {widget.id}',
            details={'dashboard_id': widget.dashboard_id, 'widget_type': widget.widget_type},
            user=self.request.user,
            request=self.request,
        )

    def perform_update(self, serializer):
        widget = serializer.save()
        log_activity(
            action_type='update',
            resource_type='Widget',
            resource_id=widget.id,
            resource_name=widget.title or widget.name or f'Widget {widget.id}',
            details={'dashboard_id': widget.dashboard_id},
            user=self.request.user,
            request=self.request,
        )

    def perform_destroy(self, instance):
        log_activity(
            action_type='delete',
            resource_type='Widget',
            resource_id=instance.id,
            resource_name=instance.title or instance.name or f'Widget {instance.id}',
            details={'dashboard_id': instance.dashboard_id},
            user=self.request.user,
            request=self.request,
        )
        instance.delete()

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanWriteData])
    def reorder(self, request):
        serializer = WidgetReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updates = []
        errors = []
        for item in serializer.validated_data['widgets']:
            try:
                widget = Widget.objects.get(pk=item['id'])
                if not request.user.is_superuser and widget.dashboard.created_by != request.user:
                    errors.append({'id': item['id'], 'error': 'Permission denied'})
                    continue
                widget.position_x = item['position_x']
                widget.position_y = item['position_y']
                update_fields = ['position_x', 'position_y']
                if 'width' in item:
                    widget.width = item['width']
                    update_fields.append('width')
                if 'height' in item:
                    widget.height = item['height']
                    update_fields.append('height')
                widget.save(update_fields=update_fields)
                updates.append(widget.id)
            except Widget.DoesNotExist:
                errors.append({'id': item['id'], 'error': 'Widget not found'})

        return Response({
            'updated': updates,
            'errors': errors,
            'count': len(updates),
        })

    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, CanWriteData])
    def chart_type(self, request, pk=None):
        widget = self.get_object()
        if not request.user.is_superuser and widget.dashboard.created_by != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        chart_type = request.data.get('chart_type')
        if not chart_type:
            return Response({'error': 'chart_type requis'}, status=status.HTTP_400_BAD_REQUEST)
        config = dict(widget.configuration or {})
        config['chart_type_override'] = chart_type
        widget.configuration = config
        widget.save(update_fields=['configuration'])
        return Response({'chart_type_override': chart_type})


class DashboardPreviewAPIView(APIView):
    permission_classes = [IsAuthenticated, CanReadData]

    def post(self, request):
        serializer = DashboardPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = M4WorkbenchService(request.user).build_dashboard(serializer.validated_data)
        return Response(payload, status=status.HTTP_200_OK)


class DashboardAutoBuildAPIView(APIView):
    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        """Charge le dashboard existant pour un user+source sans régénérer."""
        source_id = request.query_params.get('source_id')
        if not source_id:
            return Response({'error': 'source_id est requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            source_id_int = int(source_id)
        except (ValueError, TypeError):
            return Response({'error': 'source_id invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        slug = f"dashboard-auto-{request.user.id}-{source_id}"
        try:
            dashboard = Dashboard.objects.get(created_by=request.user, slug=slug)
        except Dashboard.DoesNotExist:
            return Response({'error': 'Dashboard introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.ingestion.models import DataSource
        widget_source_id = None
        first_widget = Widget.objects.filter(dashboard=dashboard).first()
        if first_widget and first_widget.configuration:
            widget_source_id = first_widget.configuration.get('source_id')
        source = DataSource.objects.filter(id=widget_source_id).first() if widget_source_id else None
        source_name = source.name if source else dashboard.name

        # Nettoyage des doublons auto-générés uniquement
        all_widgets = list(Widget.objects.filter(dashboard=dashboard).order_by('position_y', 'position_x'))
        seen: set[tuple] = set()
        to_keep: list[Widget] = []
        for w in all_widgets:
            is_auto = w.configuration.get('auto_generated') is not False
            cfg = w.configuration or {}
            key = (cfg.get('measure', ''), cfg.get('aggregation', ''), tuple(cfg.get('group_by') or []), w.widget_type)
            if is_auto and key in seen:
                w.delete()
            else:
                seen.add(key)
                to_keep.append(w)

        workbench = M4WorkbenchService(request.user)
        widgets = to_keep
        widget_list = []
        for w in widgets:
            config = dict(w.configuration)
            config.pop('auto_generated', None)
            try:
                payload = workbench.calculate_metric(config)
            except Exception:
                payload = {
                    'nom_kpi': w.title, 'value': 0, 'formatted_value': '0',
                    'rows_processed': 0, 'breakdown': [], 'chart_type': w.widget_type,
                    'data_quality_score': 0,
                }
            widget_list.append({
                'id': w.id,
                'title': w.title,
                'type': w.widget_type,
                'position': {'x': w.position_x, 'y': w.position_y, 'w': w.width, 'h': w.height},
                'payload': payload,
                'auto_generated': w.configuration.get('auto_generated', True),
                'chart_type_override': w.configuration.get('chart_type_override'),
            })
        return Response({
            'dashboard': {
                'id': dashboard.id,
                'name': dashboard.name,
                'slug': dashboard.slug,
                'source_name': source_name,
                'source_id': source_id_int,
                'domain': 'generic',
            },
            'widgets': widget_list,
        })

    def post(self, request):
        source_id = request.data.get('source_id')
        if not source_id:
            return Response({'error': 'source_id est requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            period_start = request.data.get('period_start')
            period_end = request.data.get('period_end')
            filters = request.data.get('filters')
            from datetime import date
            ps = date.fromisoformat(period_start) if period_start else None
            pe = date.fromisoformat(period_end) if period_end else None
            result = auto_build_dashboard(request.user, source_id, ps, pe, filters)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DashboardAddWidgetAPIView(APIView):
    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request):
        source_id = request.data.get('source_id')
        config = request.data.get('config', {})
        if not source_id or not config:
            return Response({'error': 'source_id et config sont requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = add_widget_to_dashboard(request.user, source_id, config)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DashboardExportPDFAPIView(APIView):
    permission_classes = [IsAuthenticated, CanReadData]

    def post(self, request):
        source_id = request.data.get('source_id')

        if not source_id:
            return Response({'error': 'source_id est requis.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            source_id_int = int(source_id)
        except (ValueError, TypeError):
            return Response({'error': 'source_id invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            slug = f"dashboard-auto-{request.user.id}-{source_id}"
            dashboard = Dashboard.objects.get(created_by=request.user, slug=slug)
        except Dashboard.DoesNotExist:
            return Response({'error': 'Dashboard introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.ingestion.models import DataSource
        from apps.notifications.pdf_report import generate_dashboard_pdf
        from apps.kpi.services import M4WorkbenchService

        source = DataSource.objects.filter(id=source_id_int).first()
        source_name = source.name if source else dashboard.name

        widgets_db = dashboard.widgets.filter(is_visible=True).order_by('position_y', 'position_x')
        workbench = M4WorkbenchService(source_id_int)

        widget_data = []
        for w in widgets_db:
            try:
                config = dict(w.configuration) if w.configuration else {}
                config.pop('auto_generated', None)
                config['source_id'] = source_id_int
                payload = workbench.calculate_metric(config)
            except Exception as e:
                logger.warning("Failed to compute payload for widget %s: %s", w.id, e)
                payload = {
                    'nom_kpi': w.title or w.name or 'Widget',
                    'value': 0, 'formatted_value': '0',
                    'rows_processed': 0, 'breakdown': [],
                    'chart_type': w.widget_type, 'data_quality_score': 0,
                }

            widget_data.append({
                'id': w.id,
                'title': w.title or w.name or f'Widget {w.id}',
                'type': w.widget_type,
                'payload': payload,
            })

        pdf_bytes = generate_dashboard_pdf(
            user=request.user,
            dashboard_name=dashboard.name,
            source_name=source_name,
            widgets=widget_data,
            title=f"Rapport Dashboard — {source_name}",
        )

        if pdf_bytes is None:
            return Response(
                {"error": "Génération PDF indisponible (reportlab non installé)."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="dashboard_{source_id}.pdf"'
        return response


class PreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_or_create_preferences(self, user):
        prefs, created = PreferenceUtilisateur.objects.get_or_create(
            user=user,
            defaults=default_preferences_for_role(getattr(user.profile, 'role', 'viewer')),
        )
        if created:
            prefs.save()
        return prefs

    def get(self, request):
        prefs = self._get_or_create_preferences(request.user)
        return Response(PreferenceUtilisateurSerializer(prefs).data)

    def put(self, request):
        prefs = self._get_or_create_preferences(request.user)
        serializer = PreferenceUtilisateurSerializer(prefs, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data)


class PreferenceResetAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        prefs, _ = PreferenceUtilisateur.objects.get_or_create(
            user=request.user,
            defaults=default_preferences_for_role(getattr(request.user.profile, 'role', 'viewer')),
        )
        prefs.delete()
        prefs, _ = PreferenceUtilisateur.objects.get_or_create(
            user=request.user,
            defaults=default_preferences_for_role(getattr(request.user.profile, 'role', 'viewer')),
        )
        return Response(PreferenceUtilisateurSerializer(prefs).data, status=status.HTTP_201_CREATED)


class VuePersonnaliseeViewSet(viewsets.ModelViewSet):
    serializer_class = VuePersonnaliseeSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [permission() for permission in [IsAuthenticated]]

    def get_queryset(self):
        qs = VuePersonnalisee.objects.all().order_by('ordre', 'nom')
        if self.request.user.is_superuser:
            return qs
        return qs.filter(models.Q(user=self.request.user) | models.Q(is_partagee=True))

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.user_id != self.request.user.id and not self.request.user.is_superuser:
            raise PermissionDenied('You can only edit your own views')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id and not self.request.user.is_superuser:
            raise PermissionDenied('You can only delete your own views')
        instance.delete()

    @action(detail=True, methods=['post'])
    def default(self, request, pk=None):
        instance = self.get_object()
        if instance.user_id != request.user.id and not request.user.is_superuser:
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        instance.is_default = True
        instance.save(update_fields=['is_default', 'updated_at'])
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def dupliquer(self, request, pk=None):
        instance = self.get_object()
        if instance.user_id != request.user.id and not request.user.is_superuser:
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        duplicate = VuePersonnalisee.objects.create(
            user=request.user,
            nom=f"{instance.nom} (copie)",
            description=instance.description,
            icone=instance.icone,
            config=instance.config,
            is_default=False,
            is_partagee=False,
            ordre=instance.ordre + 1,
        )
        return Response(self.get_serializer(duplicate).data, status=status.HTTP_201_CREATED)
