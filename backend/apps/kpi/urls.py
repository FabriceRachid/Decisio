"""
M4: KPI URL Routing
Define URL patterns for KPI API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.kpi.views import (
    KPIViewSet, KPICalculationViewSet, KPIAlertViewSet, KPIDashboardAPIView,
    KPIEngineAPIView, PivotTableView, KPIPivotAPIView, KPIAvailableFiltersAPIView,
    AutoKPIListAPIView, AutoKPIDetectAPIView,
    AdvancedPivotTableAPIView, PivotDrillDownAPIView, PivotExportAPIView,
    PivotExportPDFAPIView,
)

router = DefaultRouter()
router.register(r'kpis', KPIViewSet, basename='kpi')
router.register(r'calculations', KPICalculationViewSet, basename='kpi-calculation')
router.register(r'alerts', KPIAlertViewSet, basename='kpi-alert')
router.register(r'dashboard', KPIDashboardAPIView, basename='kpi-dashboard')

urlpatterns = [
    path('', include(router.urls)),
    path('auto/', AutoKPIListAPIView.as_view(), name='kpi-auto-list'),
    path('auto/detect/', AutoKPIDetectAPIView.as_view(), name='kpi-auto-detect'),
    path('workbench/metric/', KPIEngineAPIView.as_view(), name='kpi-workbench-metric'),
    path('workbench/pivot/', PivotTableView.as_view(), name='kpi-workbench-pivot'),
    path('filtres-disponibles/', KPIAvailableFiltersAPIView.as_view(), name='kpi-available-filters'),
    path('pivot/advanced/', AdvancedPivotTableAPIView.as_view(), name='kpi-pivot-advanced'),
    path('pivot/drill-down/', PivotDrillDownAPIView.as_view(), name='kpi-pivot-drill-down'),
    path('pivot/export/', PivotExportAPIView.as_view(), name='kpi-pivot-export'),
    path('pivot/export/pdf/', PivotExportPDFAPIView.as_view(), name='kpi-pivot-export-pdf'),
]
