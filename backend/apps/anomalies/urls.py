"""M7 URL routing."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.anomalies.views import AnomalyModelViewSet, AnomalyViewSet, IsolationForestRunView

router = DefaultRouter()
router.register(r"detections", AnomalyViewSet, basename="anomaly-detection")
router.register(r"ml-models", AnomalyModelViewSet, basename="anomaly-ml-model")

urlpatterns = [
    path("isolation_forest/run/", IsolationForestRunView.as_view(), name="anomalies-isolation-forest-run"),
    path("", include(router.urls)),
]
