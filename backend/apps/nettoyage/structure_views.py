"""
DRF views for intelligent structural reconstruction endpoints.
"""
import json
import logging
import os

from django.conf import settings
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import CanReadData, CanWriteData
from apps.conflits.audit import log_activity
from apps.ingestion.models import DataSource
from apps.nettoyage.structure_detection.orchestrator import StructureDetectionOrchestrator
from apps.nettoyage.structure_detection.correction_memory import CorrectionMemory
from apps.nettoyage.structure_models import (
    CleaningRun,
    CorrectionExample,
    RawStructuralSnapshot,
)
from apps.nettoyage.structure_serializers import (
    CleaningRunListSerializer,
    CleaningRunSerializer,
    CorrectionExampleSerializer,
    CorrectionValidateRequestSerializer,
    StructuralDetectRequestSerializer,
    StructuralDetectResponseSerializer,
)

logger = logging.getLogger(__name__)


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


class StructuralDetectView(APIView):
    """
    POST /api/nettoyage/sources/<source_id>/structural-detect/
    Launch intelligent structural reconstruction on an already-imported source.
    """
    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request, source_id):
        serializer = StructuralDetectRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            source = DataSource.objects.get(pk=source_id)
        except DataSource.DoesNotExist:
            return Response(
                {'error': f'Source {source_id} introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        sheet_name = data.get('sheet_name', '')
        force_llm = data.get('force_llm', False)
        validation_config = data.get('validation_config', {})

        file_path = self._resolve_file_path(source)
        if not file_path:
            return Response(
                {'error': 'Fichier source introuvable sur le serveur'},
                status=status.HTTP_404_NOT_FOUND,
            )

        orchestrator = StructureDetectionOrchestrator({'validation_config': validation_config})

        try:
            result = orchestrator.detect_and_reconstruct(
                file_path=file_path,
                sheet_name=sheet_name or None,
                source_id=source_id,
                force_llm=force_llm,
            )
        except Exception as e:
            logger.exception(f"Structural detection failed for source {source_id}")
            return Response(
                {'error': f'Echec de la detection: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        reconstruction_plan = result.get('reconstruction_plan') or {}
        structural_fp = result.get('structural_fingerprint') or {}
        validation_report = result.get('validation_report') or {}

        snapshot = RawStructuralSnapshot.objects.create(
            source=source,
            sheet_name=sheet_name,
            structural_fingerprint=_json_safe(structural_fp),
            confidence_score=result.get('confidence_score', 0),
            detected_subtables=_json_safe(reconstruction_plan.get('subtables', [])),
            header_candidates=_json_safe(structural_fp.get('header_candidates', [])),
            merged_cells=_json_safe(structural_fp.get('merged_cells', [])),
            blank_zones=_json_safe(structural_fp.get('blank_rows', [])),
            column_types=_json_safe(structural_fp.get('column_types', {})),
        )

        fp = structural_fp
        cleaning_run = CleaningRun.objects.create(
            source=source,
            snapshot=snapshot,
            method_used=result.get('method_used', 'heuristic'),
            status=result.get('status', 'completed'),
            confidence_score=result.get('confidence_score', 0),
            correction_examples_used=result.get('correction_examples_used', []),
            llm_model=result.get('llm_model', ''),
            llm_tokens_used=result.get('llm_tokens_used', 0),
            llm_duration_ms=result.get('llm_duration_ms', 0),
            reconstruction_plan=_json_safe(reconstruction_plan),
            validation_gates_passed=validation_report.get('all_passed', True),
            validation_gates_detail=_json_safe(validation_report),
            sheet_name=sheet_name,
            rows_before=fp.get('total_rows', 0),
            columns_before=fp.get('total_cols', 0),
            subtables_detected=len(reconstruction_plan.get('subtables', [])),
            duration_ms=result.get('duration_ms', 0),
            error_message=result.get('error') or '',
            created_by=request.user,
        )

        log_activity(
            action_type='STRUCTURAL_DETECT',
            resource_type='DataSource',
            resource_id=source_id,
            details={
                'method': result.get('method_used'),
                'confidence': result.get('confidence_score'),
                'status': result.get('status'),
            },
            user=request.user,
        )

        response_data = {
            'run_id': cleaning_run.id,
            'snapshot_id': snapshot.id,
            'method_used': cleaning_run.method_used,
            'status': cleaning_run.status,
            'confidence_score': float(cleaning_run.confidence_score),
            'structural_fingerprint': result.get('structural_fingerprint', {}),
            'reconstruction_plan': result.get('reconstruction_plan'),
            'validation_report': result.get('validation_report'),
            'requires_human_review': result.get('requires_human_review', False),
            'correction_examples_used': cleaning_run.correction_examples_used,
            'llm_model': cleaning_run.llm_model,
            'llm_tokens_used': cleaning_run.llm_tokens_used,
            'llm_duration_ms': cleaning_run.llm_duration_ms,
            'duration_ms': cleaning_run.duration_ms,
            'error': cleaning_run.error_message or None,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def _resolve_file_path(self, source):
        if source.file_path:
            if os.path.isabs(source.file_path) and os.path.exists(source.file_path):
                return source.file_path
            from django.conf import settings
            full = os.path.join(settings.MEDIA_ROOT, source.file_path)
            if os.path.exists(full):
                return full
        return None


class StructuralRunDetailView(APIView):
    """
    GET /api/nettoyage/structural-runs/<run_id>/
    Get the status and result of a structural detection run.
    """
    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request, run_id):
        try:
            run = CleaningRun.objects.select_related('source', 'snapshot').get(pk=run_id)
        except CleaningRun.DoesNotExist:
            return Response(
                {'error': f'Run {run_id} introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = CleaningRunSerializer(run).data
        data['structural_fingerprint'] = run.snapshot.structural_fingerprint if run.snapshot else {}
        data['snapshot_id'] = run.snapshot_id
        data['source_name'] = run.source.name

        return Response(data, status=status.HTTP_200_OK)


class StructuralRunListView(APIView):
    """
    GET /api/nettoyage/structural-runs/?source_id=<id>
    List structural detection runs for a source.
    """
    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        source_id = request.query_params.get('source_id')
        qs = CleaningRun.objects.select_related('source').order_by('-created_at')
        if source_id:
            qs = qs.filter(source_id=source_id)
        qs = qs[:50]

        data = CleaningRunListSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class CorrectionValidateView(APIView):
    """
    POST /api/nettoyage/structural-runs/<run_id>/validate/
    User validates or corrects a reconstruction proposal.
    - Stores a CorrectionExample for future learning.
    - If apply_plan=True, auto-generates CleaningRules and optionally executes cleaning.
    """
    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request, run_id):
        serializer = CorrectionValidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            run = CleaningRun.objects.select_related('source', 'snapshot').get(pk=run_id)
        except CleaningRun.DoesNotExist:
            return Response(
                {'error': f'Run {run_id} introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        correction_type = data.get('correction_type', 'structural')
        description = data.get('description', '')
        apply_plan = data.get('apply_plan', True)
        execute_cleaning = data.get('execute_cleaning', False)

        if not run.snapshot:
            return Response(
                {'error': 'Pas de snapshot associe a ce run'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        memory = CorrectionMemory()
        correction_id = memory.store_correction(
            structural_before=run.snapshot.structural_fingerprint,
            structural_after=run.reconstruction_plan,
            reconstruction_plan=run.reconstruction_plan,
            description=description or f'Validation du run {run_id}',
            correction_type=correction_type,
            source_id=run.source_id,
            snapshot_id=run.snapshot_id,
            user_id=request.user.id,
        )

        run.status = 'completed'
        run.method_used = 'human_corrected' if correction_type != 'structural' else 'human_review'
        run.completed_at = __import__('django.utils.timezone', fromlist=['now']).now()
        run.save(update_fields=['status', 'method_used', 'completed_at'])

        plan_application_result = None
        if apply_plan and run.reconstruction_plan:
            from apps.nettoyage.structure_detection.plan_to_rules import PlanToRulesService
            service = PlanToRulesService()

            if execute_cleaning:
                plan_application_result = service.execute_plan(
                    plan=run.reconstruction_plan,
                    source=run.source,
                    user=request.user,
                )
            else:
                plan_application_result = service.apply_plan_to_source(
                    plan=run.reconstruction_plan,
                    source=run.source,
                    user=request.user,
                )

        log_activity(
            action_type='STRUCTURAL_VALIDATE',
            resource_type='CleaningRun',
            resource_id=run_id,
            user=request.user,
            details={
                'correction_id': correction_id,
                'correction_type': correction_type,
                'description': description,
                'apply_plan': apply_plan,
                'execute_cleaning': execute_cleaning,
                'rules_created': plan_application_result.get('total_rules', 0) if plan_application_result else 0,
            },
        )

        response_payload = {
            'status': 'success',
            'correction_id': correction_id,
            'message': 'Validation enregistree et ajoutee a la memoire de corrections',
        }

        if plan_application_result:
            response_payload['plan_application'] = plan_application_result
            if execute_cleaning and plan_application_result.get('status') == 'completed':
                response_payload['message'] = (
                    'Plan applique, regles generees et nettoyage execute avec succes'
                )
            elif plan_application_result.get('total_rules', 0) > 0:
                response_payload['message'] = (
                    f"{plan_application_result['total_rules']} regle(s) generee(s) "
                    f"et pipeline '{plan_application_result.get('pipeline_name')}' cree"
                )

        return Response(response_payload, status=status.HTTP_200_OK)


class CorrectionExamplesView(APIView):
    """
    GET /api/nettoyage/correction-examples/
    List recent correction examples (for transparency/debugging).
    """
    permission_classes = [IsAuthenticated, CanReadData]

    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        corrections = CorrectionExample.objects.select_related('created_by').order_by('-created_at')[:limit]
        data = CorrectionExampleSerializer(corrections, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class ApplyPlanView(APIView):
    """
    POST /api/nettoyage/sources/<source_id>/apply-plan/
    Apply a reconstruction plan to a source: generate cleaning rules and optionally execute.
    """
    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request, source_id):
        try:
            source = DataSource.objects.get(pk=source_id)
        except DataSource.DoesNotExist:
            return Response(
                {'error': f'Source {source_id} introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        plan = request.data.get('reconstruction_plan')
        execute_cleaning = request.data.get('execute_cleaning', False)

        if not plan:
            return Response(
                {'error': 'reconstruction_plan est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.nettoyage.structure_detection.plan_to_rules import PlanToRulesService
        service = PlanToRulesService()

        try:
            if execute_cleaning:
                result = service.execute_plan(plan=plan, source=source, user=request.user)
            else:
                result = service.apply_plan_to_source(plan=plan, source=source, user=request.user)
        except Exception as e:
            logger.exception(f"Failed to apply plan to source {source_id}")
            return Response(
                {'error': f'Echec de l\'application du plan: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        log_activity(
            action_type='APPLY_RECONSTRUCTION_PLAN',
            resource_type='DataSource',
            resource_id=source_id,
            user=request.user,
            details={
                'rules_created': result.get('total_rules', 0),
                'pipeline_id': result.get('pipeline_id'),
                'execute_cleaning': execute_cleaning,
            },
        )

        return Response(result, status=status.HTTP_200_OK)


class PlanPreviewView(APIView):
    """
    POST /api/nettoyage/sources/<source_id>/plan-preview/
    Preview what rules would be generated from a reconstruction plan, without creating them.
    """
    permission_classes = [IsAuthenticated, CanReadData]

    def post(self, request, source_id):
        try:
            source = DataSource.objects.get(pk=source_id)
        except DataSource.DoesNotExist:
            return Response(
                {'error': f'Source {source_id} introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        plan = request.data.get('reconstruction_plan')
        if not plan:
            return Response(
                {'error': 'reconstruction_plan est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.nettoyage.structure_detection.plan_to_rules import PlanToRulesService
        service = PlanToRulesService()
        result = service.preview_rules(plan=plan, source=source)

        return Response(result, status=status.HTTP_200_OK)


class ExecuteAfterReviewView(APIView):
    """
    POST /api/nettoyage/sources/<source_id>/execute-after-review/
    Execute cleaning with a previously created pipeline, after human review of rules.
    """
    permission_classes = [IsAuthenticated, CanWriteData]

    def post(self, request, source_id):
        try:
            source = DataSource.objects.get(pk=source_id)
        except DataSource.DoesNotExist:
            return Response(
                {'error': f'Source {source_id} introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        pipeline_id = request.data.get('pipeline_id')
        if not pipeline_id:
            return Response(
                {'error': 'pipeline_id est requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.nettoyage.models import CleaningPipeline
        try:
            pipeline = CleaningPipeline.objects.get(pk=pipeline_id, is_active=True)
        except CleaningPipeline.DoesNotExist:
            return Response(
                {'error': f'Pipeline {pipeline_id} introuvable ou inactif'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from apps.nettoyage.services import apply_cleaning
        try:
            result = apply_cleaning(
                source=source,
                user=request.user,
                pipeline_id=pipeline_id,
                rule_ids=None,
                include_all_auto_rules=False,
                quality_gate={},
            )
        except Exception as e:
            logger.exception(f"Failed to execute cleaning for source {source_id}")
            return Response(
                {'error': f'Echec du nettoyage: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        log_activity(
            action_type='EXECUTE_CLEANING_AFTER_REVIEW',
            resource_type='DataSource',
            resource_id=source_id,
            user=request.user,
            details={
                'pipeline_id': pipeline_id,
                'job_id': result.get('job_id'),
                'rows_affected': result.get('summary', {}).get('rows_affected', 0),
            },
        )

        return Response(result, status=status.HTTP_200_OK)
