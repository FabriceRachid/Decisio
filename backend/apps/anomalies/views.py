"""M7 — REST API for anomaly detection (Isolation Forest)."""

import logging

from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.anomalies.models import Anomaly, AnomalyModel
from apps.anomalies.serializers import (
    AnomalyDetailSerializer,
    AnomalyListSerializer,
    AnomalyModelListSerializer,
    AnomalyStatusUpdateSerializer,
    IsolationForestRunSerializer,
)
from apps.anomalies.services import AnomalyDetectionError, persist_detection_run, run_isolation_forest
from apps.authentication.permissions import CanReadData, CanWriteData
from apps.conflits.audit import log_activity

logger = logging.getLogger(__name__)


class AnomalyPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _anomaly_queryset_for_user(user):
    qs = Anomaly.objects.select_related("model", "data_source").order_by("-detected_at")
    if user.is_superuser:
        return qs
    role = getattr(user.profile, "role", "viewer")
    if role == "admin":
        return qs
    return qs.filter(data_source__uploaded_by=user)


def _anomaly_model_queryset_for_user(user):
    qs = AnomalyModel.objects.select_related("training_source").order_by("-created_at")
    if user.is_superuser:
        return qs
    role = getattr(user.profile, "role", "viewer")
    if role == "admin":
        return qs
    return qs.filter(training_source__uploaded_by=user)


class AnomalyViewSet(viewsets.ModelViewSet):
    """GET /api/anomalies/detections/ — GET/PATCH /api/anomalies/detections/{id}/"""

    pagination_class = AnomalyPagination
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "partial_update":
            return [IsAuthenticated(), CanWriteData()]
        return [IsAuthenticated(), CanReadData()]

    def get_queryset(self):
        qs = _anomaly_queryset_for_user(self.request.user)
        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)
        return qs

    def get_serializer_class(self):
        if self.action == "partial_update":
            return AnomalyStatusUpdateSerializer
        if self.action == "retrieve":
            return AnomalyDetailSerializer
        return AnomalyListSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            action_type='update',
            resource_type='Anomaly',
            resource_id=instance.id,
            resource_name=f'Anomaly #{instance.id}',
            user=self.request.user,
            request=self.request,
            status_code=status.HTTP_200_OK,
        )


class AnomalyModelViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/anomalies/ml-models/"""

    permission_classes = [IsAuthenticated, CanReadData]
    serializer_class = AnomalyModelListSerializer
    pagination_class = AnomalyPagination

    def get_queryset(self):
        return _anomaly_model_queryset_for_user(self.request.user)


class IsolationForestRunView(APIView):
    """
    POST /api/anomalies/isolation_forest/run/

    Body: source_id, feature_columns, backend (raw|cleaned), contamination, max_rows, persist, model_name?
    """

    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request):
        ser = IsolationForestRunSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            result = run_isolation_forest(
                user=request.user,
                source_id=data["source_id"],
                feature_columns=data["feature_columns"],
                backend=data["backend"],
                contamination=data["contamination"],
                max_rows=data["max_rows"],
            )
            result["max_rows_used"] = data["max_rows"]

            if data["persist"]:
                persist_info = persist_detection_run(
                    user=request.user,
                    payload=result,
                    model_name=(data.get("model_name") or "").strip() or None,
                )
                result["persisted"] = persist_info

            log_activity(
                action_type='create',
                resource_type='AnomalyModel',
                resource_id=persist_info.get('model_id') if data["persist"] else None,
                resource_name=(data.get("model_name") or "").strip() or 'Isolation Forest Run',
                user=request.user,
                request=request,
                status_code=status.HTTP_200_OK,
            )

            return Response(result, status=status.HTTP_200_OK)
        except AnomalyDetectionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Isolation Forest run failed")
            return Response({"detail": "Erreur interne lors de la detection."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
