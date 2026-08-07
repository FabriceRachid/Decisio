"""
M4: KPI Calculation REST API
ViewSets and API views for KPI management, calculation, and monitoring.
"""

import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal

from rest_framework import viewsets, serializers, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum, Max, Min
from django.http import FileResponse, HttpResponse
from django.contrib.auth.models import User

from apps.kpi.models import KPI, KPICalculation, KPIAlert
from apps.kpi.serializers import (
    KPIListSerializer, KPIDetailSerializer, KPICreateUpdateSerializer,
    KPICalculationDetailSerializer, KPICalculationSummarySerializer, KPICalculationCreateSerializer,
    KPIAnomalySerializer, KPIForecastSerializer,
    KPIAlertListSerializer, KPIAlertDetailSerializer, KPIAlertCreateUpdateSerializer,
    KPIAcknowledgeAlertSerializer, KPIDashboardStatSerializer, KPIVarianceAnalysisSerializer,
    KPIHistorySerializer, KPIExportRequestSerializer,
    KPIEngineRequestSerializer, PivotTableRequestSerializer,
    AutoKPIDetectResponseSerializer,
    AdvancedPivotRequestSerializer, AdvancedPivotResponseSerializer, PivotDrillDownRequestSerializer,
)
from apps.kpi.services import (
    KPICalculationService, KPIAnomalyDetectionService,
    KPIForecastingService, KPIAlertingService, M4WorkbenchService, PivotService, FilterService, AdvancedPivotService
)
from apps.kpi.auto_service import KPIAutoService
from apps.authentication.permissions import CanReadData, CanWriteData, HasSourceAccess
from apps.conflits.audit import log_activity
from apps.ingestion.models import DataSource

logger = logging.getLogger(__name__)


def _accessible_kpi_queryset(user):
    qs = KPI.objects.select_related('owner')
    if user.is_superuser:
        return qs
    return qs.filter(Q(is_public=True) | Q(owner=user)).distinct()


def _accessible_alert_queryset(user):
    qs = KPIAlert.objects.select_related('kpi', 'created_by')
    if user.is_superuser:
        return qs
    return qs.filter(
        Q(created_by=user) |
        Q(kpi__owner=user) |
        Q(kpi__is_public=True)
    ).distinct()


def _organization_scoped_sources(queryset, user):
    if user.is_superuser:
        return queryset
    organization_id = getattr(getattr(user, 'profile', None), 'organization_id', None)
    if organization_id:
        return queryset.filter(uploaded_by__profile__organization_id=organization_id)
    return queryset.filter(uploaded_by=user)


class KPIPagination(PageNumberPagination):
    """Pagination for KPI list views."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class KPIViewSet(viewsets.ModelViewSet):
    """
    Complete KPI management ViewSet.
    
    List, create, retrieve, update, delete KPIs.
    Custom actions for calculation, history, anomaly detection, forecasting.
    """
    
    queryset = KPI.objects.all().order_by('-updated_at')
    pagination_class = KPIPagination
    permission_classes = [IsAuthenticated, CanReadData]

    WRITE_ACTIONS = {'create', 'update', 'partial_update', 'destroy', 'calculate_now', 'batch_calculate'}

    def get_permissions(self):
        if self.action in self.WRITE_ACTIONS:
            permission_classes = [IsAuthenticated, CanWriteData]
        else:
            permission_classes = [IsAuthenticated, CanReadData]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action in ['list']:
            return KPIListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return KPICreateUpdateSerializer
        else:
            return KPIDetailSerializer
    
    def get_queryset(self):
        """Filter KPIs based on user permissions and search."""
        qs = _accessible_kpi_queryset(self.request.user)
        
        # Filter by active status
        active = self.request.query_params.get('active')
        if active:
            qs = qs.filter(is_active=active.lower() == 'true')
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        
        # Filter by frequency
        frequency = self.request.query_params.get('frequency')
        if frequency:
            qs = qs.filter(frequency=frequency)
        
        # Filter by owner
        owner = self.request.query_params.get('owner')
        if owner:
            qs = qs.filter(owner__username=owner)
        
        # Search by name/code/description
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return qs.order_by('-updated_at')
    
    def perform_create(self, serializer):
        """Set owner to current user when creating KPI."""
        instance = serializer.save(owner=self.request.user)
        log_activity(
            action_type='create',
            resource_type='KPI',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            action_type='update',
            resource_type='KPI',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        log_activity(
            action_type='delete',
            resource_type='KPI',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_204_NO_CONTENT,
        )
        instance.delete()
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanWriteData])
    def calculate_now(self, request, pk=None):
        """
        POST /api/kpis/{id}/calculate_now/
        Manually trigger KPI calculation for most recent period.
        """
        kpi = self.get_object()
        
        try:
            service = KPICalculationService(request.user)
            period_end = date.today()
            period_start = period_end - timedelta(days=30)
            
            result = service.calculate_kpi(kpi, period_start, period_end)
            
            if result['success']:
                service.persist_calculation(kpi, period_start, period_end, result)
                return Response({
                    'success': True,
                    'calculation_status': 'calculation_completed',
                    'calculated_value': result['calculated_value'],
                    'variance_percent': result['variance_percent'],
                    'kpi_status': result['status'],
                    'data_quality_score': result['data_quality_score'],
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat(),
                })
            return Response({
                'success': False,
                'status': 'calculation_failed',
                'error': result.get('error', 'Calculation failed')
            })
        except Exception as e:
            logger.error(f"Error calculating KPI {kpi.code}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        GET /api/kpis/{id}/history/?limit=12&period=monthly
        Get historical calculations for trending and analysis.
        """
        kpi = self.get_object()
        limit = int(request.query_params.get('limit', 12))
        
        calculations = kpi.calculations.all().order_by('-period_end')[:limit]
        serializer = KPIHistorySerializer(calculations, many=True)
        
        return Response({
            'kpi': KPIListSerializer(kpi).data,
            'calculations': serializer.data,
            'total': calculations.count()
        })
    
    @action(detail=True, methods=['get'])
    def anomaly_detection(self, request, pk=None):
        """
        GET /api/kpis/{id}/anomaly_detection/?lookback=12
        Detect anomalies in recent calculations.
        """
        kpi = self.get_object()
        lookback = int(request.query_params.get('lookback', 12))
        
        try:
            service = KPIAnomalyDetectionService(request.user)
            result = service.detect_anomalies(kpi, lookback_periods=lookback)
            
            serializer = KPIAnomalySerializer(result)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in anomaly detection for {kpi.code}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def forecast(self, request, pk=None):
        """
        GET /api/kpis/{id}/forecast/?periods=3
        Forecast next N periods with confidence intervals.
        """
        kpi = self.get_object()
        periods = int(request.query_params.get('periods', 3))
        
        try:
            service = KPIForecastingService(request.user)
            result = service.forecast_kpi(kpi, forecast_periods=periods)
            
            serializer = KPIForecastSerializer(result)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error forecasting KPI {kpi.code}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def variance_analysis(self, request, pk=None):
        """
        GET /api/kpis/{id}/variance_analysis/?period=monthly
        Compare current vs previous period performance.
        """
        kpi = self.get_object()
        
        current = kpi.calculations.order_by('-period_end').first()
        previous = kpi.calculations.filter(
            period_end__lt=current.period_end if current else timezone.now()
        ).order_by('-period_end').first()
        
        if not current or not previous:
            return Response({
                'has_sufficient_data': False,
                'kpi_name': kpi.name,
                'kpi_code': kpi.code,
                'explanation': 'At least two historical calculations are required for variance analysis'
            })
        
        variance_data = {
            'kpi_name': kpi.name,
            'kpi_code': kpi.code,
            'current_period': KPICalculationSummarySerializer(current).data,
            'previous_period': KPICalculationSummarySerializer(previous).data,
            'absolute_variance': float(current.calculated_value - previous.calculated_value),
            'percent_variance': current.variance_percent,
            'trend': 'increasing' if (current.variance_percent or 0) > 0 else 'decreasing',
            'vs_target': {
                'target_value': float(kpi.target_value) if kpi.target_value else None,
                'current_vs_target': float(current.calculated_value - kpi.target_value) if kpi.target_value else None
            }
        }
        
        return Response(variance_data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanWriteData])
    def batch_calculate(self, request):
        """
        POST /api/kpis/batch_calculate/
        Calculate multiple KPIs in one request.
        """
        serializer = KPICalculationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        kpi_ids = serializer.validated_data['kpi_ids']
        period_start = serializer.validated_data.get('period_start', date.today() - timedelta(days=30))
        period_end = serializer.validated_data.get('period_end', date.today())
        
        kpis = KPI.objects.filter(id__in=kpi_ids)
        
        try:
            service = KPICalculationService(request.user)
            results = service.batch_calculate_kpis(list(kpis), period_start, period_end)
            
            successful = sum(1 for v in results.values() if v)
            failed = len(results) - successful
            
            return Response({
                'status': 'batch_calculation_completed',
                'successful': successful,
                'failed': failed,
                'results': results
            })
        except Exception as e:
            logger.error(f"Error in batch calculation: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanWriteData])
    def recalculate_pipeline(self, request):
        """
        POST /api/kpi/kpis/recalculate_pipeline/
        Recalculate active KPIs impacted by ingestion/cleaning pipeline tables.
        """
        source_tables = request.data.get('source_tables') or ['nettoyage_cleaneddata', 'ingestion_rawdata']
        if not isinstance(source_tables, list) or not source_tables:
            return Response({'error': 'source_tables must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)

        period_start_raw = request.data.get('period_start')
        period_end_raw = request.data.get('period_end')
        period_end = date.fromisoformat(period_end_raw) if period_end_raw else date.today()
        period_start = date.fromisoformat(period_start_raw) if period_start_raw else period_end - timedelta(days=30)

        table_filters = Q()
        for table in source_tables:
            if not isinstance(table, str) or not table.strip():
                continue
            table_filters |= Q(source_table=table.strip()) | Q(formula__icontains=table.strip())

        if not table_filters:
            return Response({'error': 'No valid source tables provided'}, status=status.HTTP_400_BAD_REQUEST)

        kpis = _accessible_kpi_queryset(request.user).filter(is_active=True).filter(table_filters).distinct()
        service = KPICalculationService(request.user)
        results = service.batch_calculate_kpis(list(kpis), period_start, period_end)

        successful = sum(1 for value in results.values() if value)
        failed = len(results) - successful

        return Response({
            'status': 'pipeline_recalculation_completed',
            'source_tables': source_tables,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'kpi_count': kpis.count(),
            'successful': successful,
            'failed': failed,
            'kpis': [
                {'id': kpi.id, 'code': kpi.code, 'name': kpi.name}
                for kpi in kpis
            ],
            'results': results,
        })


class KPICalculationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for KPI calculations.
    List and retrieve historical calculation results.
    """
    
    queryset = KPICalculation.objects.all().order_by('-executed_at')
    pagination_class = KPIPagination
    permission_classes = [IsAuthenticated, CanReadData]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return KPICalculationSummarySerializer
        else:
            return KPICalculationDetailSerializer
    
    def get_queryset(self):
        """Filter calculations by KPI, date range, status."""
        qs = KPICalculation.objects.all()
        
        # Filter by KPI
        kpi_id = self.request.query_params.get('kpi_id')
        if kpi_id:
            qs = qs.filter(kpi_id=kpi_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(period_start__gte=start_date)
        if end_date:
            qs = qs.filter(period_end__lte=end_date)
        
        # Filter anomalies
        anomalies_only = self.request.query_params.get('anomalies_only')
        if anomalies_only and anomalies_only.lower() == 'true':
            qs = qs.filter(anomaly_detected=True)
        
        return qs.order_by('-executed_at')
    
    @action(detail=False, methods=['get'])
    def by_period(self, request):
        """
        GET /api/kpi-calculations/by_period/?year=2026&month=1&frequency=monthly
        Get calculations grouped by period.
        """
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        frequency = request.query_params.get('frequency', 'monthly')
        
        qs = KPICalculation.objects.all()
        if year:
            qs = qs.filter(period_end__year=int(year))
        if month:
            qs = qs.filter(period_end__month=int(month))
        
        grouped = {}
        for calc in qs:
            period_label = calc.period_label or calc.period_end.isoformat()
            if period_label not in grouped:
                grouped[period_label] = []
            grouped[period_label].append(KPICalculationSummarySerializer(calc).data)
        
        return Response({'by_period': grouped})


class KPIAlertViewSet(viewsets.ModelViewSet):
    """
    KPI Alert management ViewSet.
    Create, manage, and monitor KPI alerts and thresholds.
    """
    
    queryset = KPIAlert.objects.all().order_by('-is_active', '-updated_at')
    pagination_class = KPIPagination
    permission_classes = [IsAuthenticated, CanReadData]

    WRITE_ACTIONS = {'create', 'update', 'partial_update', 'destroy', 'acknowledge', 'test_notification'}

    def get_permissions(self):
        if self.action in self.WRITE_ACTIONS:
            permission_classes = [IsAuthenticated, CanWriteData]
        else:
            permission_classes = [IsAuthenticated, CanReadData]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return KPIAlertListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return KPIAlertCreateUpdateSerializer
        else:
            return KPIAlertDetailSerializer
    
    def get_queryset(self):
        """Filter alerts by KPI, status, type."""
        qs = _accessible_alert_queryset(self.request.user)
        
        kpi_id = self.request.query_params.get('kpi_id')
        if kpi_id:
            qs = qs.filter(kpi_id=kpi_id)
        
        is_active = self.request.query_params.get('is_active')
        if is_active:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        
        is_triggered = self.request.query_params.get('is_triggered')
        if is_triggered:
            qs = qs.filter(is_triggered=is_triggered.lower() == 'true')
        
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            qs = qs.filter(alert_type=alert_type)
        
        return qs
    
    def perform_create(self, serializer):
        """Set creator when creating alert."""
        instance = serializer.save(created_by=self.request.user)
        log_activity(
            action_type='create',
            resource_type='KPIAlert',
            resource_id=instance.id,
            resource_name=instance.name if hasattr(instance, 'name') else f'KPIAlert #{instance.id}',
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            action_type='update',
            resource_type='KPIAlert',
            resource_id=instance.id,
            resource_name=instance.name if hasattr(instance, 'name') else f'KPIAlert #{instance.id}',
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        log_activity(
            action_type='delete',
            resource_type='KPIAlert',
            resource_id=instance.id,
            resource_name=instance.name if hasattr(instance, 'name') else f'KPIAlert #{instance.id}',
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_204_NO_CONTENT,
        )
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        POST /api/kpi-alerts/{id}/acknowledge/
        Mark alert as acknowledged with optional resolution notes.
        """
        alert = self.get_object()
        serializer = KPIAcknowledgeAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            service = KPIAlertingService(request.user)
            service.acknowledge_alert(alert, serializer.validated_data.get('notes'))
            
            return Response({
                'status': 'acknowledged',
                'acknowledged_by': request.user.username,
                'acknowledged_at': alert.acknowledged_at.isoformat()
            })
        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def test_notification(self, request, pk=None):
        """
        POST /api/kpi-alerts/{id}/test_notification/
        Send a test notification through configured channels.
        """
        alert = self.get_object()
        
        try:
            service = KPIAlertingService(request.user)
            service._send_alert_notifications(alert, alert.kpi.calculations.first())
            
            return Response({
                'status': 'test_notification_sent',
                'channels': alert.notification_channels
            })
        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def triggered_recently(self, request):
        """
        GET /api/kpi-alerts/triggered_recently/?hours=24
        Get alerts triggered in recent hours.
        """
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        alerts = _accessible_alert_queryset(request.user).filter(last_triggered_at__gte=since)
        serializer = KPIAlertListSerializer(alerts, many=True)
        
        return Response({
            'period_hours': hours,
            'count': alerts.count(),
            'alerts': serializer.data
        })


class KPIDashboardAPIView(viewsets.ViewSet):
    """
    KPI Dashboard statistics and overview.
    """
    
    permission_classes = [IsAuthenticated, CanReadData]
    
    def list(self, request):
        """
        GET /api/kpi-dashboard/
        Get comprehensive KPI dashboard statistics.
        """
        try:
            accessible_kpis = _accessible_kpi_queryset(request.user)
            accessible_alerts = _accessible_alert_queryset(request.user)
            total_kpis = accessible_kpis.count()
            active_kpis = accessible_kpis.filter(is_active=True).count()
            
            # Status breakdown
            recent_calcs = KPICalculation.objects.filter(
                kpi__in=accessible_kpis,
                executed_at__gte=timezone.now() - timedelta(days=30)
            )
            on_target = recent_calcs.filter(status='on_target').count()
            warning = recent_calcs.filter(status='warning').count()
            critical = recent_calcs.filter(status='critical').count()
            
            # By category & frequency
            by_category = {}
            for cat in accessible_kpis.values_list('category', flat=True).distinct():
                by_category[cat or 'Uncategorized'] = accessible_kpis.filter(category=cat).count()
            
            by_frequency = {}
            for freq, label in KPI.FREQUENCY_CHOICES:
                count = accessible_kpis.filter(frequency=freq).count()
                if count > 0:
                    by_frequency[label] = count
            
            # Performance metrics
            success_calcs = recent_calcs.filter(data_quality_score__gte=70).count()
            success_rate = (success_calcs / recent_calcs.count() * 100) if recent_calcs.exists() else 0
            
            avg_quality = recent_calcs.aggregate(Avg('data_quality_score'))['data_quality_score__avg'] or 0
            
            # Alerts
            active_alerts = accessible_alerts.filter(is_active=True).count()
            triggered_this_week = accessible_alerts.filter(
                last_triggered_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Top & bottom performers
            top_performers = recent_calcs.filter(status='on_target').values('kpi__name', 'kpi__code').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            bottom_performers = recent_calcs.filter(status='critical').values('kpi__name', 'kpi__code').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            data = {
                'total_kpis': total_kpis,
                'kpis_active': active_kpis,
                'kpis_on_target': on_target,
                'kpis_warning': warning,
                'kpis_critical': critical,
                'by_category': by_category,
                'by_frequency': by_frequency,
                'calculation_success_rate': round(success_rate, 2),
                'avg_data_quality': round(float(avg_quality), 2),
                'active_alerts': active_alerts,
                'triggered_this_week': triggered_this_week,
                'top_performers': list(top_performers),
                'bottom_performers': list(bottom_performers)
            }
            
            serializer = KPIDashboardStatSerializer(data)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error generating dashboard stats: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class KPIEngineAPIView(APIView):
    """Compute a configurable KPI value using SUM / AVG / COUNT / MIN / MAX."""

    permission_classes = [IsAuthenticated, CanReadData]

    def post(self, request):
        serializer = KPIEngineRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = M4WorkbenchService(request.user).calculate_metric(serializer.validated_data)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class PivotTableView(APIView):
    """Build a configurable pivot table with time dimensions and filters."""

    permission_classes = [IsAuthenticated, HasSourceAccess]

    def post(self, request):
        serializer = PivotTableRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PivotService(request.user).build(serializer.validated_data)
        return Response(result)


KPIPivotAPIView = PivotTableView


class KPIAvailableFiltersAPIView(APIView):
    """Return unique values to populate dynamic filter controls."""

    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        source_table = request.query_params.get('source_table', 'nettoyage_cleaneddata')
        source_id = request.query_params.get('source_id')
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')

        frame = PivotService(request.user)._load_frame({
            'source_table': source_table,
            'source_id': source_id,
            'period_start': period_start,
            'period_end': period_end,
        })
        values = FilterService().available_values(frame)
        return Response(values)


class AutoKPIListAPIView(APIView):
    """Return the latest detection & suggestion results for the user's organization."""

    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        organization = getattr(getattr(request.user, "profile", None), "organization", None)
        if organization is None:
            return Response([], status=status.HTTP_200_OK)

        source_id = request.query_params.get("source_id")
        if source_id:
            source = _organization_scoped_sources(DataSource.objects.all(), request.user).filter(pk=source_id).first()
            if source is None:
                return Response(
                    {"error": "Source introuvable pour votre espace."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                result = KPIAutoService().detect_and_suggest(source=source)
                serializer = AutoKPIDetectResponseSerializer(result)
                return Response(serializer.data)
            except ValueError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response([], status=status.HTTP_200_OK)


class AutoKPIDetectAPIView(APIView):
    """Detect columns and suggest possible KPIs from the latest validated cleaned source."""

    permission_classes = [IsAuthenticated, CanReadData, HasSourceAccess]

    def post(self, request):
        source_id = request.data.get("source_id")
        if not source_id:
            return Response({"error": "source_id est requis."}, status=status.HTTP_400_BAD_REQUEST)

        source = _organization_scoped_sources(DataSource.objects.all(), request.user).filter(
            pk=source_id
        ).first()
        if source is None:
            return Response(
                {"error": "Source introuvable pour votre espace."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = KPIAutoService().detect_and_suggest(source=source)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error("Erreur détection M4 pour la source %s: %s", source.id, exc)
            return Response(
                {"error": "La détection des colonnes a échoué."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = AutoKPIDetectResponseSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdvancedPivotTableAPIView(APIView):
    """Build advanced pivot tables with multi-level hierarchies and drill-down."""

    permission_classes = [IsAuthenticated, CanReadData, HasSourceAccess]

    def post(self, request):
        serializer = AdvancedPivotRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config = serializer.validated_data

        try:
            source = _organization_scoped_sources(DataSource.objects.all(), request.user).filter(
                pk=config['source_id']
            ).first()
            if source is None:
                return Response(
                    {"error": "Source not found or not accessible"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            config['source_table'] = 'ingestion_rawdata' if config['source_type'] == 'raw' else 'nettoyage_cleaneddata'

            service = AdvancedPivotService(user=request.user)
            pivot_result = service.build_pivot_with_hierarchy(config)

            response_serializer = AdvancedPivotResponseSerializer(pivot_result)
            return Response(
                {
                    'success': True,
                    'data': response_serializer.data,
                    'message': f"Pivot built successfully with {pivot_result['metadata']['rows_processed']} rows",
                },
                status=status.HTTP_200_OK,
            )

        except ValueError as exc:
            logger.error("Pivot build error: %s", exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.error("Unexpected error building pivot: %s", exc)
            return Response(
                {"error": "Failed to build pivot table"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PivotDrillDownAPIView(APIView):
    """Drill down into pivot table cell to see detail rows."""

    permission_classes = [IsAuthenticated, CanReadData, HasSourceAccess]

    def post(self, request):
        serializer = PivotDrillDownRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config = serializer.validated_data.get('pivot_config')
        row_key = serializer.validated_data.get('row_key', '')
        col_key = serializer.validated_data.get('col_key', '')

        try:
            source = _organization_scoped_sources(DataSource.objects.all(), request.user).filter(
                pk=config['source_id']
            ).first()
            if source is None:
                return Response(
                    {"error": "Source not found or not accessible"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            config['source_table'] = 'ingestion_rawdata' if config['source_type'] == 'raw' else 'nettoyage_cleaneddata'

            service = AdvancedPivotService(user=request.user)
            detail_rows = service.compute_drill_down(config, row_key, col_key)

            return Response(
                {
                    'success': True,
                    'rows': detail_rows,
                    'row_count': len(detail_rows),
                    'columns': list(detail_rows[0].keys()) if detail_rows else [],
                },
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            logger.error("Drill-down error: %s", exc)
            return Response(
                {"error": "Failed to drill down into pivot"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PivotExportAPIView(APIView):
    """Export pivot table data to Excel (.xlsx)."""

    permission_classes = [IsAuthenticated, CanReadData, HasSourceAccess]

    def post(self, request):
        serializer = AdvancedPivotRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config = serializer.validated_data

        try:
            source = _organization_scoped_sources(DataSource.objects.all(), request.user).filter(
                pk=config['source_id']
            ).first()
            if source is None:
                return Response(
                    {"error": "Source not found or not accessible"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            config['source_table'] = 'ingestion_rawdata' if config['source_type'] == 'raw' else 'nettoyage_cleaneddata'

            service = AdvancedPivotService(user=request.user)
            pivot_result = service.build_pivot_with_hierarchy(config)

            excel_bytes = service.export_to_excel(pivot_result)

            from django.http import HttpResponse
            response = HttpResponse(excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="pivot_export_{config["source_id"]}.xlsx"'
            return response

        except ValueError as exc:
            logger.error("Pivot export error: %s", exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.error("Unexpected error exporting pivot: %s", exc)
            return Response(
                {"error": "Failed to export pivot table"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PivotExportPDFAPIView(APIView):
    """Export pivot table data to PDF."""

    permission_classes = [IsAuthenticated, CanReadData, HasSourceAccess]

    def post(self, request):
        serializer = AdvancedPivotRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config = serializer.validated_data

        try:
            from apps.notifications.pdf_report import generate_pivot_report_pdf

            source = _organization_scoped_sources(DataSource.objects.all(), request.user).filter(
                pk=config['source_id']
            ).first()
            if source is None:
                return Response(
                    {"error": "Source not found or not accessible"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            config['source_table'] = 'ingestion_rawdata' if config['source_type'] == 'raw' else 'nettoyage_cleaneddata'

            service = AdvancedPivotService(user=request.user)
            pivot_result = service.build_pivot_with_hierarchy(config)

            pdf_bytes = generate_pivot_report_pdf(
                user=request.user,
                pivot_data=pivot_result,
                title=f"Tableau Croisé Dynamique - {source.name}",
            )

            if pdf_bytes is None:
                return Response(
                    {"error": "PDF generation not available (reportlab not installed)"},
                    status=status.HTTP_501_NOT_IMPLEMENTED,
                )

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="pivot_export_{config["source_id"]}.pdf"'
            return response

        except ValueError as exc:
            logger.error("Pivot PDF export error: %s", exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.error("Unexpected error exporting pivot PDF: %s", exc)
            return Response(
                {"error": "Failed to export pivot table as PDF"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

