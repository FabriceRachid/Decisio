from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.dashboard.views import DashboardAnalyticsAPIView, DashboardAutoBuildAPIView, DashboardAddWidgetAPIView, DashboardExportPDFAPIView, DashboardPreviewAPIView, DashboardViewSet, WidgetViewSet, PreferenceView, PreferenceResetAPIView, VuePersonnaliseeViewSet


router = DefaultRouter()
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'widgets', WidgetViewSet, basename='dashboard-widget')
router.register(r'vues', VuePersonnaliseeViewSet, basename='dashboard-vue')


urlpatterns = [
    path('', include(router.urls)),
    path('analytics/', DashboardAnalyticsAPIView.as_view(), name='dashboard-analytics'),
    path('auto-build/', DashboardAutoBuildAPIView.as_view(), name='dashboard-auto-build'),
    path('add-widget/', DashboardAddWidgetAPIView.as_view(), name='dashboard-add-widget'),
    path('preview/', DashboardPreviewAPIView.as_view(), name='dashboard-preview'),
    path('preferences/', PreferenceView.as_view(), name='dashboard-preferences'),
    path('preferences/reset/', PreferenceResetAPIView.as_view(), name='dashboard-preferences-reset'),
    path('export/pdf/', DashboardExportPDFAPIView.as_view(), name='dashboard-export-pdf'),
]
