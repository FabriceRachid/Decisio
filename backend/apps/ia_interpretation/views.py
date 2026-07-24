"""M6 — interpretation KPI via Groq."""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import CanReadData
from apps.ia_interpretation.serializers import InterpretKpisSerializer
from apps.ia_interpretation.services import (
    KPIInterpretationError,
    build_kpi_context_for_user,
    build_kpi_context_by_source,
    get_kpis_by_source,
    interpret_kpis_with_groq,
    persist_ai_analysis,
)

logger = logging.getLogger(__name__)


class InterpretKpisView(APIView):
    """
    POST /api/ia/interpret-kpis/

    Corps : question, source_id? + widget_ids?, kpi_ids?, persist?, model?
    """

    permission_classes = [IsAuthenticated, CanReadData]

    def post(self, request):
        ser = InterpretKpisSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            source_id = data.get("source_id")

            if source_id:
                widget_ids = data.get("widget_ids") or None
                if widget_ids == []:
                    widget_ids = None
                kpi_context = build_kpi_context_by_source(
                    user=request.user,
                    source_id=source_id,
                    widget_ids=widget_ids,
                    max_kpis=data["max_kpis"],
                )
            else:
                kpi_ids = data.get("kpi_ids") or None
                if kpi_ids == []:
                    kpi_ids = None
                kpi_context, _ = build_kpi_context_for_user(
                    user=request.user,
                    kpi_ids=kpi_ids,
                    max_kpis=data["max_kpis"],
                )

            result = interpret_kpis_with_groq(
                user=request.user,
                question=data["question"],
                kpi_context=kpi_context,
                model=(data.get("model") or "").strip() or None,
            )
            analysis_id = None
            if data["persist"]:
                analysis_id = persist_ai_analysis(
                    user=request.user,
                    question=data["question"],
                    kpi_context=kpi_context,
                    result=result,
                )

            return Response(
                {
                    "interpretation": result["text"],
                    "model": result["model"],
                    "tokens_used": result.get("tokens_used"),
                    "processing_time_ms": result.get("processing_time_ms"),
                    "kpi_count": len(kpi_context),
                    "analysis_id": analysis_id,
                },
                status=status.HTTP_200_OK,
            )
        except KPIInterpretationError as e:
            msg = str(e)
            code = status.HTTP_503_SERVICE_UNAVAILABLE if "GROQ_API_KEY" in msg else status.HTTP_400_BAD_REQUEST
            return Response({"detail": msg}, status=code)
        except Exception:
            logger.exception("interpret-kpis failed")
            return Response(
                {"detail": "Erreur interne lors de l interpretation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SourceKPIsView(APIView):
    """
    GET /api/ia/sources/<source_id>/kpis/

    Retourne la liste des KPI disponibles pour une source de données.
    """

    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request, source_id):
        try:
            kpis = get_kpis_by_source(request.user, source_id)
            return Response({"source_id": source_id, "kpis": kpis}, status=status.HTTP_200_OK)
        except Exception:
            logger.exception("source-kpis failed")
            return Response(
                {"detail": "Erreur lors de la récupération des KPI."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AIHistoryView(APIView):
    """
    GET /api/ia/history/

    Retourne les analyses IA passées de l'utilisateur (paginé, 10 par page).
    """

    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        from apps.ia_interpretation.models import AIAnalysis

        page = int(request.query_params.get("page", 1))
        page_size = 10
        offset = (page - 1) * page_size

        qs = AIAnalysis.objects.filter(requested_by=request.user).order_by("-created_at")
        total = qs.count()
        analyses = qs[offset : offset + page_size]

        results = [
            {
                "id": a.id,
                "prompt": a.prompt,
                "response": a.response,
                "model": a.model_name,
                "tokens_used": a.tokens_used,
                "processing_time_ms": a.processing_time_ms,
                "status": a.status,
                "kpi_count": len((a.context_data or {}).get("kpis", [])),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in analyses
        ]

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )
