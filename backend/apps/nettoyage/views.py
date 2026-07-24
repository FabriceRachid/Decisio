from rest_framework import generics, status, filters
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
import logging

from apps.authentication.permissions import CanReadData, CanWriteData
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleaningPipeline, CleaningRule, CleaningJob
from apps.nettoyage.serializers import (
    CleaningApplyRequestSerializer,
    CleaningJobListSerializer,
    CleaningJobValidationSerializer,
    CleaningPipelineSerializer,
    CleaningPreviewRequestSerializer,
    CleaningRuleCreateSerializer,
    CleaningRuleSerializer,
    CleaningRuleUpdateSerializer,
    CleaningExportRequestSerializer,
)
from apps.nettoyage.services import (
    CleaningError,
    apply_cleaning,
    get_cleaning_job_detail,
    preview_cleaning,
    replay_cleaning,
    suggest_cleaning,
    validate_cleaning_job,
)
from apps.nettoyage.tasks import apply_cleaning_async, export_cleaned_data_async


logger = logging.getLogger(__name__)


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


def _organization_scoped_jobs(queryset, user):
    if user.is_superuser:
        return queryset

    organization_id = _organization_id_for_user(user)
    if organization_id:
        return queryset.filter(
            source__uploaded_by__profile__organization_id=organization_id
        ).distinct()

    return queryset.filter(created_by=user)


class CleaningRuleListCreateView(generics.ListCreateAPIView):
    """
    List cleaning rules with filtering, or create a new rule.
    GET /api/nettoyage/rules/?rule_type=standardize&category=formatting&is_active=true
    POST /api/nettoyage/rules/
    """
    permission_classes = [CanReadData]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['rule_type', 'category', 'is_active']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['priority', 'created_at', 'execution_count', 'success_rate']
    ordering = ['-priority', '-created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CleaningRuleCreateSerializer
        return CleaningRuleSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [CanWriteData()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        queryset = CleaningRule.objects.select_related('created_by').order_by('-priority', '-created_at')
        
        # Filter by tags if provided
        tags = self.request.query_params.getlist('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=tag)
        
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CleaningRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a cleaning rule.
    GET /api/nettoyage/rules/<id>/
    PUT /api/nettoyage/rules/<id>/
    PATCH /api/nettoyage/rules/<id>/
    DELETE /api/nettoyage/rules/<id>/
    """
    queryset = CleaningRule.objects.select_related('created_by')
    permission_classes = [CanReadData]
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CleaningRuleUpdateSerializer
        return CleaningRuleSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [CanWriteData()]
        return [permission() for permission in self.permission_classes]
    
    def update(self, request, *args, **kwargs):
        """Update rule properties"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(CleaningRuleSerializer(instance).data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """Soft-delete by marking inactive"""
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class CleaningPipelineListCreateView(generics.ListCreateAPIView):
    """
    List cleaning pipelines with filtering, or create a new pipeline.
    """
    permission_classes = [CanReadData]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source_type_scope', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']
    ordering = ['name']

    def get_serializer_class(self):
        return CleaningPipelineSerializer

    def get_queryset(self):
        return CleaningPipeline.objects.select_related('created_by').prefetch_related('rules').order_by('name')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [CanWriteData()]
        return [permission() for permission in self.permission_classes]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CleaningPipelineDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a cleaning pipeline."""
    queryset = CleaningPipeline.objects.select_related('created_by').prefetch_related('rules')
    serializer_class = CleaningPipelineSerializer
    permission_classes = [CanReadData]

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [CanWriteData()]
        return [permission() for permission in self.permission_classes]


class CleaningPreviewView(APIView):
    """Preview cleaning results before applying"""
    permission_classes = [CanReadData]

    def post(self, request, source_id):
        serializer = CleaningPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = _get_accessible_source(request, source_id)

        try:
            result = preview_cleaning(
                source=source,
                user=request.user,
                pipeline_id=serializer.validated_data.get('pipeline_id'),
                rule_ids=serializer.validated_data['rule_ids'],
                include_all_auto_rules=serializer.validated_data['include_all_auto_rules'],
                quality_gate=serializer.validated_data.get('quality_gate', {}),
                decision_overrides=serializer.validated_data.get('decision_overrides', []),
            )
        except CleaningError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Unexpected cleaning preview failure for source #%s.', source.id)
            return Response(
                {'error': 'Une erreur inattendue est survenue pendant la previsualisation du nettoyage.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class CleaningApplyView(APIView):
    """Apply cleaning rules synchronously (for small datasets)"""
    permission_classes = [CanWriteData]

    def post(self, request, source_id):
        serializer = CleaningApplyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = _get_accessible_source(request, source_id)

        try:
            result = apply_cleaning(
                source=source,
                user=request.user,
                pipeline_id=serializer.validated_data.get('pipeline_id'),
                rule_ids=serializer.validated_data['rule_ids'],
                include_all_auto_rules=serializer.validated_data['include_all_auto_rules'],
                quality_gate=serializer.validated_data.get('quality_gate', {}),
                decision_overrides=serializer.validated_data.get('decision_overrides', []),
            )
        except CleaningError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Unexpected sync cleaning failure for source #%s.', source.id)
            return Response(
                {'error': 'Une erreur inattendue est survenue pendant l application du nettoyage.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_201_CREATED)


class CleaningApplyAsyncView(APIView):
    """Apply cleaning rules asynchronously (for large datasets)"""
    permission_classes = [CanWriteData]

    def post(self, request, source_id):
        serializer = CleaningApplyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = _get_accessible_source(request, source_id)

        execution_context = {
            'pipeline_id': serializer.validated_data.get('pipeline_id'),
            'rule_ids': serializer.validated_data.get('rule_ids', []),
            'include_all_auto_rules': serializer.validated_data.get('include_all_auto_rules', False),
            'quality_gate': serializer.validated_data.get('quality_gate', {}),
            'decision_overrides': serializer.validated_data.get('decision_overrides', []),
        }

        # Create job record
        job = CleaningJob.objects.create(
            source=source,
            rule_id=None,  # Async job doesn't track single rule
            status='queued',
            created_by=request.user,
            total_rows=source.row_count or 0,
            execution_context=execution_context,
        )

        # Queue async task (with sync fallback if broker is unavailable).
        try:
            apply_cleaning_async.delay(
                job_id=job.id,
                source_id=source_id,
                user_id=request.user.id,
                pipeline_id=execution_context['pipeline_id'],
                rule_ids=execution_context['rule_ids'],
                include_all_auto_rules=execution_context['include_all_auto_rules'],
                quality_gate=execution_context['quality_gate'],
                decision_overrides=execution_context.get('decision_overrides', []),
            )
        except Exception as exc:
            logger.exception('Failed to enqueue cleaning job #%s, falling back to sync mode.', job.id)

            try:
                sync_result = apply_cleaning(
                    source=source,
                    user=request.user,
                    pipeline_id=execution_context['pipeline_id'],
                    rule_ids=execution_context['rule_ids'],
                    include_all_auto_rules=execution_context['include_all_auto_rules'],
                    quality_gate=execution_context['quality_gate'],
                    decision_overrides=execution_context.get('decision_overrides', []),
                )
            except CleaningError as cleaning_exc:
                job.status = 'failed'
                job.error_message = str(cleaning_exc)
                job.save(update_fields=['status', 'error_message'])
                return Response({'error': str(cleaning_exc)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                logger.exception('Unexpected sync fallback failure for cleaning job #%s.', job.id)
                job.status = 'failed'
                job.error_message = 'Une erreur inattendue est survenue pendant le nettoyage.'
                job.save(update_fields=['status', 'error_message'])
                return Response(
                    {'error': 'Une erreur inattendue est survenue pendant le nettoyage.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            job.status = 'completed'
            job.progress_percent = 100
            job.rows_processed = sync_result['summary']['rows_processed']
            job.rows_affected = sync_result['summary']['rows_affected']
            job.rows_skipped = sync_result['summary']['rows_skipped']
            job.rows_failed = sync_result['summary']['rows_failed']
            job.execution_context = {
                **execution_context,
                'fallback_mode': 'sync',
                'enqueue_error': str(exc),
                'result_job_id': sync_result['job_id'],
            }
            job.save(
                update_fields=[
                    'status',
                    'progress_percent',
                    'rows_processed',
                    'rows_affected',
                    'rows_skipped',
                    'rows_failed',
                    'execution_context',
                ]
            )

        return Response(CleaningJobListSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class CleaningJobListView(generics.ListAPIView):
    """
    List cleaning jobs with advanced filtering.
    GET /api/nettoyage/jobs/?status=completed&source_id=1&created_after=2026-03-01
    """
    permission_classes = [CanReadData]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'source_id']
    ordering_fields = ['created_at', 'rows_affected', 'duration_ms']
    ordering = ['-created_at']

    def get_serializer_class(self):
        return CleaningJobListSerializer

    def get_queryset(self):
        queryset = CleaningJob.objects.select_related('source', 'rule', 'created_by')
        queryset = _organization_scoped_jobs(queryset, self.request.user)
        
        # Date range filtering
        created_after = self.request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        created_before = self.request.query_params.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        return queryset.order_by('-created_at')


class CleaningJobDetailView(APIView):
    """Get full details of a cleaning job"""
    permission_classes = [CanReadData]

    def get(self, request, job_id):
        job = _get_effective_job(_get_accessible_job(request, job_id))
        return Response(get_cleaning_job_detail(job=job), status=status.HTTP_200_OK)


class CleaningJobReplayView(APIView):
    """Re-run cleaning job with same parameters"""
    permission_classes = [CanWriteData]

    def post(self, request, job_id):
        job = _get_effective_job(_get_accessible_job(request, job_id))
        try:
            result = replay_cleaning(job=job, user=request.user)
        except CleaningError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


class CleaningJobValidationView(APIView):
    """Validate/approve cleaned data"""
    permission_classes = [CanWriteData]

    def post(self, request, job_id):
        job = _get_effective_job(_get_accessible_job(request, job_id))
        serializer = CleaningJobValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = validate_cleaning_job(
            job=job,
            user=request.user,
            is_validated=serializer.validated_data['is_validated'],
            validation_notes=serializer.validated_data['validation_notes'],
        )
        return Response(result, status=status.HTTP_200_OK)


class CleaningJobExportView(APIView):
    """Export cleaned data from job"""
    permission_classes = [CanReadData]

    def post(self, request, job_id):
        job = _get_effective_job(_get_accessible_job(request, job_id))
        serializer = CleaningExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Queue async export task
        task = export_cleaned_data_async.delay(
            job_id=job.id,
            format=serializer.validated_data.get('format', 'csv'),
            include_metadata=serializer.validated_data.get('include_metadata', False),
            include_validation_status=serializer.validated_data.get('include_validation_status', False),
        )

        return Response({
            'message': 'Export task queued',
            'job_id': job.id,
            'task_id': task.id,
            'format': serializer.validated_data.get('format', 'csv'),
        }, status=status.HTTP_202_ACCEPTED)


class CleaningSuggestionView(APIView):
    """Get auto-suggested cleaning rules for a source"""
    permission_classes = [CanReadData]

    def get(self, request, source_id):
        source = _get_accessible_source(request, source_id)
        return Response(suggest_cleaning(source=source), status=status.HTTP_200_OK)


class CleaningComparisonView(APIView):
    """
    Show before/after comparison for a cleaning job.
    Displays data transformations, quality improvements, and row-level diffs.
    
    GET /api/nettoyage/jobs/<id>/comparison/
    """
    permission_classes = [CanReadData]

    def get(self, request, job_id):
        job = _get_effective_job(_get_accessible_job(request, job_id))
        
        if job.status != 'completed':
            return Response(
                {'error': f'Job status is {job.status}, not completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        structural_metadata = _get_structure_reconstruction(job)
        comparison_mode = 'structural_reconstruction' if structural_metadata.get('activee') else 'row_aligned'

        # Gather before/after data
        comparison = {
            'job': {
                'id': job.id,
                'source_id': job.source_id,
                'source_name': job.source.name,
                'status': job.status,
                'is_auto_triggered': job.is_auto_triggered,
                'created_at': job.created_at,
                'completed_at': job.completed_at,
                'duration_ms': job.duration_ms,
            },
            'summary': {
                'total_rows_before': job.total_rows,
                'total_rows_after': job.cleaned_results.count(),
                'rows_affected': job.rows_affected,
                'rows_removed': job.total_rows - job.cleaned_results.count() if job.total_rows else None,
                'average_quality_score_before': 0,  # Raw data has no quality score
                'average_quality_score_after': _calculate_avg_quality_score(job),
            },
            'comparison_mode': comparison_mode,
            'structure_reconstruction': structural_metadata or None,
            'changes_by_type': _aggregate_changes_by_type(job),
            'columns': _build_comparison_columns(job),
            'rows': _build_full_comparison_rows(job),
            'sample_comparisons': _build_before_after_samples(job),
            'quality_improvements': _analyze_quality_improvements(job),
        }
        comparison['before_columns'] = _build_before_columns(job)
        comparison['before_rows_preview'] = _build_before_rows(job)
        comparison['after_columns'] = _build_after_columns(job)
        comparison['after_rows_preview'] = _build_after_rows(job)
        
        return Response(comparison, status=status.HTTP_200_OK)


def _calculate_avg_quality_score(job):
    """Calculate average quality score for cleaned data"""
    from django.db.models import Avg
    from apps.nettoyage.models import CleanedData
    
    avg = CleanedData.objects.filter(job=job).aggregate(Avg('quality_score'))
    return float(avg['quality_score__avg'] or 0)


def _aggregate_changes_by_type(job):
    """Count transformations by type"""
    from apps.nettoyage.models import CleanedData
    
    changes = {}
    for cleaned in job.cleaned_results.all():
        for change in cleaned.changes_made:
            action = change.get('action', 'unknown')
            changes[action] = changes.get(action, 0) + 1
    
    return changes


def _build_before_after_samples(job):
    """Build side-by-side before/after comparison samples"""
    if _is_structural_job(job):
        return _build_structural_sample_comparisons(job)

    samples = []
    cleaned_data = list(
        job.cleaned_results.select_related('original_data')
        .order_by('original_data__row_number')[:5]  # First 5 samples
    )
    
    for item in cleaned_data:
        if not item.original_data:
            continue
        
        sample = {
            'row_number': item.original_data.row_number,
            'before': item.original_data.data,
            'after': item.data,
            'changes': item.changes_made,
            'quality_score': float(item.quality_score or 0),
            'validation_status': 'validated' if item.is_validated else 'pending',
        }
        samples.append(sample)
    
    return samples


def _build_comparison_columns(job):
    if _is_structural_job(job):
        return _build_structural_after_columns(job)
    return _build_after_columns(job)


def _build_before_columns(job):
    if _is_structural_job(job):
        return _build_structural_before_columns(job)
    columns = []
    seen = set()
    for row in job.source.raw_data_rows.order_by('row_number'):
        for column in row.data.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def _build_before_rows(job):
    if _is_structural_job(job):
        return _build_structural_before_rows(job)
    columns = _build_before_columns(job)
    rows = []
    for raw_row in job.source.raw_data_rows.order_by('row_number'):
        rows.append({
            'row_number': raw_row.row_number,
            'status': 'raw',
            'data': {column: raw_row.data.get(column) for column in columns},
            'validation_status': raw_row.validation_status,
        })
    return rows


def _build_after_columns(job):
    if _is_structural_job(job):
        return _build_structural_after_columns(job)
    columns = []
    seen = set()
    for cleaned in job.cleaned_results.order_by('id'):
        for column in cleaned.data.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def _build_after_rows(job):
    if _is_structural_job(job):
        return _build_structural_after_rows(job)
    columns = _build_after_columns(job)
    rows = []
    cleaned_rows = list(job.cleaned_results.order_by('id'))
    for index, cleaned in enumerate(cleaned_rows, start=1):
        rows.append({
            'row_number': int(cleaned.original_data.row_number) if cleaned.original_data else index,
            'status': 'cleaned',
            'data': {column: cleaned.data.get(column) for column in columns},
            'changes': cleaned.changes_made,
            'quality_score': float(cleaned.quality_score or 0),
            'validation_status': 'validated' if cleaned.is_validated else 'pending',
        })
    return rows


def _build_full_comparison_rows(job):
    if _is_structural_job(job):
        return _build_structural_comparison_rows(job)

    cleaned_rows = {
        item.original_data.row_number: item
        for item in job.cleaned_results.select_related('original_data').order_by('original_data__row_number')
        if item.original_data
    }

    rows = []
    for raw_row in job.source.raw_data_rows.order_by('row_number'):
        cleaned_row = cleaned_rows.get(raw_row.row_number)
        rows.append({
            'row_number': raw_row.row_number,
            'status': 'removed' if cleaned_row is None else 'kept',
            'before': raw_row.data,
            'after': cleaned_row.data if cleaned_row else None,
            'changes': cleaned_row.changes_made if cleaned_row else [],
            'quality_score': float(cleaned_row.quality_score or 0) if cleaned_row else 0,
            'validation_status': 'removed' if cleaned_row is None else ('validated' if cleaned_row.is_validated else 'pending'),
        })

    return rows


def _get_cleaning_report(job):
    execution_context = job.execution_context or {}
    report = execution_context.get('cleaning_report')
    return report if isinstance(report, dict) else {}


def _get_structure_reconstruction(job):
    metadata = _get_cleaning_report(job).get('metadata', {})
    structure = metadata.get('structure_reconstruction', {})
    return structure if isinstance(structure, dict) else {}


def _is_structural_job(job):
    return bool(_get_structure_reconstruction(job).get('activee'))


def _build_structural_before_columns(job):
    columns = []
    seen = set()
    for row in job.source.raw_data_rows.order_by('row_number'):
        for column in row.data.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def _build_structural_before_rows(job):
    columns = _build_structural_before_columns(job)
    rows = []
    for raw_row in job.source.raw_data_rows.order_by('row_number'):
        rows.append({
            'row_number': raw_row.row_number,
            'status': 'raw',
            'data': {column: raw_row.data.get(column) for column in columns},
        })
    return rows


def _build_structural_after_columns(job):
    columns = []
    seen = set()
    for cleaned in job.cleaned_results.order_by('id'):
        for column in cleaned.data.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def _build_structural_after_rows(job):
    columns = _build_structural_after_columns(job)
    rows = []
    for index, cleaned in enumerate(job.cleaned_results.order_by('id'), start=1):
        trace = _extract_source_trace(cleaned)
        rows.append({
            'row_number': _resolve_structural_row_number(cleaned, fallback=index),
            'status': 'reconstructed',
            'data': {column: cleaned.data.get(column) for column in columns},
            'source_trace': trace,
            'quality_score': float(cleaned.quality_score or 0),
            'validation_status': 'validated' if cleaned.is_validated else 'pending',
        })
    return rows


def _build_structural_comparison_rows(job):
    rows = []
    for index, cleaned in enumerate(job.cleaned_results.order_by('id'), start=1):
        trace = _extract_source_trace(cleaned)
        before = {}
        if cleaned.original_data:
            before = cleaned.original_data.data
        elif trace:
            before = {'Source Excel': f"R{trace.get('origine_excel', {}).get('row', '—')}C{trace.get('origine_excel', {}).get('column', '—')}"}

        rows.append({
            'row_number': _resolve_structural_row_number(cleaned, fallback=index),
            'status': 'reconstructed',
            'before': before,
            'after': cleaned.data,
            'changes': cleaned.changes_made,
            'quality_score': float(cleaned.quality_score or 0),
            'validation_status': 'validated' if cleaned.is_validated else 'pending',
            'source_trace': trace,
        })
    return rows


def _build_structural_sample_comparisons(job):
    samples = []
    for index, cleaned in enumerate(job.cleaned_results.order_by('id')[:5], start=1):
        trace = _extract_source_trace(cleaned)
        before = {}
        if cleaned.original_data:
            before = cleaned.original_data.data
        elif trace:
            before = {'Source Excel': f"R{trace.get('origine_excel', {}).get('row', '—')}C{trace.get('origine_excel', {}).get('column', '—')}"}
        samples.append({
            'row_number': _resolve_structural_row_number(cleaned, fallback=index),
            'before': before,
            'after': cleaned.data,
            'changes': cleaned.changes_made,
            'quality_score': float(cleaned.quality_score or 0),
            'validation_status': 'validated' if cleaned.is_validated else 'pending',
            'source_trace': trace,
        })
    return samples


def _extract_source_trace(cleaned):
    for change in cleaned.changes_made or []:
        if change.get('action') == 'structure_reconstruction':
            return change.get('source_trace')
    return None


def _resolve_structural_row_number(cleaned, *, fallback):
    trace = _extract_source_trace(cleaned)
    if isinstance(trace, dict) and trace.get('row_number_reconstruit') is not None:
        return int(trace['row_number_reconstruit'])
    return int(cleaned.original_data.row_number) if cleaned.original_data else int(fallback)


def _analyze_quality_improvements(job):
    """Analyze quality improvements per column"""
    from apps.nettoyage.models import CleanedData
    
    improvements = {
        'null_values_removed': 0,
        'duplicates_removed': 0,
        'format_standardized': 0,
        'values_filled': 0,
        'other_transformations': 0,
    }
    
    for cleaned in job.cleaned_results.all():
        for change in cleaned.changes_made:
            action = change.get('action', '')
            
            if 'remove' in action.lower() and 'null' in action.lower():
                improvements['null_values_removed'] += 1
            elif 'duplicate' in action.lower():
                improvements['duplicates_removed'] += 1
            elif 'standardize' in action.lower():
                improvements['format_standardized'] += 1
            elif 'fill' in action.lower():
                improvements['values_filled'] += 1
            else:
                improvements['other_transformations'] += 1
    
    return improvements


def _get_accessible_source(request, source_id):
    queryset = DataSource.objects.all()
    queryset = _organization_scoped_sources(queryset, request.user)
    return get_object_or_404(queryset, id=source_id)


def _get_accessible_job(request, job_id):
    queryset = CleaningJob.objects.select_related('source', 'rule', 'created_by')
    queryset = _organization_scoped_jobs(queryset, request.user)
    return get_object_or_404(queryset, id=job_id)


def _get_effective_job(job):
    result_job_id = (job.execution_context or {}).get('result_job_id')
    if job.rule_id is None and result_job_id:
        result_job = (
            CleaningJob.objects.select_related('source', 'rule', 'created_by')
            .filter(id=result_job_id)
            .first()
        )
        if result_job:
            return result_job
    return job
