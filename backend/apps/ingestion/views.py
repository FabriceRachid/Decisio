from rest_framework import generics, status, filters
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from pathlib import Path
from django.conf import settings
from django.http import Http404
import uuid
import logging

from apps.authentication.permissions import CanReadData, CanWriteData
from apps.ingestion.models import DataSource, IngestionJob, RawData
from apps.ingestion.serializers import (
    DataSourceDetailSerializer,
    DataSourceListSerializer,
    DataSourcePreviewSerializer,
    DataSourceUploadSerializer,
    IngestionJobSerializer,
    RawDataSerializer,
    DataSourceUpdateSerializer,
)
from apps.ingestion.services import IngestionError, ingest_uploaded_file, preview_uploaded_file
from apps.ingestion.services import list_import_templates
from apps.ingestion.tasks import process_ingestion_async

logger = logging.getLogger(__name__)


def _organization_scoped_sources(queryset, user):
    if user.is_superuser:
        return queryset

    profile = getattr(user, 'profile', None)
    organization_id = getattr(profile, 'organization_id', None)
    if organization_id:
        return queryset.filter(uploaded_by__profile__organization_id=organization_id)

    return queryset.filter(uploaded_by=user)


def _filter_jobs_for_user(queryset, user):
    """Restrict async ingestion jobs to the requesting organization when available."""
    if user.is_superuser:
        return queryset

    profile = getattr(user, 'profile', None)
    organization_id = getattr(profile, 'organization_id', None)
    if organization_id:
        return queryset.filter(
            Q(requested_by__profile__organization_id=organization_id)
            | Q(source__uploaded_by__profile__organization_id=organization_id)
        ).distinct()

    return queryset.filter(Q(requested_by=user) | Q(source__uploaded_by=user)).distinct()


class RawDataPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class ImportTemplateListView(APIView):
    """
    List available ERP import presets.
    GET /api/ingestion/templates/
    """

    permission_classes = [CanReadData]

    def get(self, request):
        return Response({'results': list_import_templates()}, status=status.HTTP_200_OK)


class DataSourceListView(generics.ListAPIView):
    """
    List uploaded data sources visible to the current user with filtering.
    GET /api/ingestion/sources/
    
    Query parameters:
    - status: pending, processing, completed, failed
    - source_type: csv, excel, api, database, json
    - tags: filter by tags (JSON array)
    - created_after: filter by creation date (ISO format)
    - uploaded_by: username (admin only)
    """

    serializer_class = DataSourceListSerializer
    permission_classes = [CanReadData]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'source_type', 'created_at']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['created_at', 'name', 'row_count']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = DataSource.objects.select_related('uploaded_by').filter(is_archived=False).order_by('-created_at')
        
        # Filter by tags if provided
        tags = self.request.query_params.getlist('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=tag)
        
        # Admins can inspect any uploader explicitly inside their visible scope.
        if self.request.user.is_superuser or self.request.user.profile.role == 'admin':
            uploaded_by = self.request.query_params.get('uploaded_by')
            queryset = _organization_scoped_sources(queryset, self.request.user)
            if uploaded_by:
                queryset = queryset.filter(uploaded_by__username=uploaded_by)
                return queryset
            return queryset

        return _organization_scoped_sources(queryset, self.request.user)


class DataSourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a single data source.
    GET /api/ingestion/sources/<id>/
    PUT /api/ingestion/sources/<id>/
    PATCH /api/ingestion/sources/<id>/
    DELETE /api/ingestion/sources/<id>/
    """

    permission_classes = [CanReadData]
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DataSourceUpdateSerializer
        return DataSourceDetailSerializer

    def get_queryset(self):
        queryset = DataSource.objects.select_related('uploaded_by').prefetch_related('raw_data_rows')
        return _organization_scoped_sources(queryset, self.request.user)
    
    def update(self, request, *args, **kwargs):
        """Update source metadata (name, description, tags, retention)"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Check if user owns the source or is admin
        if instance.uploaded_by != request.user and not (request.user.is_superuser or request.user.profile.role == 'admin'):
            return Response(
                {'detail': 'You do not have permission to update this source.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(DataSourceDetailSerializer(instance).data, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """Soft-delete source by archiving it"""
        instance = self.get_object()
        
        # Check if user owns the source or is admin
        if instance.uploaded_by != request.user and not (request.user.is_superuser or request.user.profile.role == 'admin'):
            return Response(
                {'detail': 'You do not have permission to delete this source.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Soft delete - just archive
        instance.is_archived = True
        instance.save()
        
        return Response(
            {'message': f'Source {instance.name} has been archived.'},
            status=status.HTTP_204_NO_CONTENT
        )


class DataSourceUploadView(APIView):
    """
    Upload and ingest a source file synchronously.
    POST /api/ingestion/sources/upload/
    
    Returns 201 with DataSource details.
    For large files, use async_upload instead.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [CanWriteData]

    def post(self, request):
        serializer = DataSourceUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            source = ingest_uploaded_file(
                user=request.user,
                uploaded_file=serializer.validated_data['file'],
                name=serializer.validated_data['name'],
                source_type=serializer.validated_data['source_type'],
                delimiter=serializer.validated_data['delimiter'],
                encoding=serializer.validated_data['encoding'],
                has_header=serializer.validated_data['has_header'],
                description=serializer.validated_data.get('description'),
                tags=serializer.validated_data.get('tags', []),
                retention_days=serializer.validated_data['retention_days'],
                required_columns=serializer.validated_data.get('required_columns', []),
                key_columns=serializer.validated_data.get('key_columns', []),
                strict_validation=serializer.validated_data['strict_validation'],
                template_id=serializer.validated_data.get('template_id'),
                column_mapping=serializer.validated_data.get('column_mapping', {}),
            )
        except IngestionError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = DataSourceDetailSerializer(source)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class DataSourceAsyncUploadView(APIView):
    """
    Upload and ingest a source file asynchronously.
    POST /api/ingestion/sources/async-upload/
    
    Returns 202 Accepted with job ID for polling.
    Client should poll /ingestion/jobs/<job_id>/ for status.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [CanWriteData]

    def post(self, request):
        serializer = DataSourceUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Save file temporarily
        uploaded_file = serializer.validated_data['file']
        media_root = Path(settings.MEDIA_ROOT)
        storage = FileSystemStorage(location=media_root / 'ingestion_uploads')
        stored_name = storage.save(uploaded_file.name, ContentFile(uploaded_file.read()))

        # Create job record
        job = IngestionJob.objects.create(
            celery_task_id=str(uuid.uuid4()),
            status='queued',
            requested_by=request.user,
        )

        task_kwargs = {
            'job_id': job.id,
            'user_id': request.user.id,
            'file_path': str(Path('ingestion_uploads') / stored_name),
            'source_name': serializer.validated_data['name'],
            'source_type': serializer.validated_data['source_type'],
            'delimiter': serializer.validated_data['delimiter'],
            'encoding': serializer.validated_data['encoding'],
            'has_header': serializer.validated_data['has_header'],
            'description': serializer.validated_data.get('description'),
            'tags': serializer.validated_data.get('tags', []),
            'retention_days': serializer.validated_data['retention_days'],
            'required_columns': serializer.validated_data.get('required_columns', []),
            'key_columns': serializer.validated_data.get('key_columns', []),
            'strict_validation': serializer.validated_data['strict_validation'],
            'template_id': serializer.validated_data.get('template_id'),
            'column_mapping': serializer.validated_data.get('column_mapping', {}),
        }

        try:
            task = process_ingestion_async.delay(**task_kwargs)
        except Exception as exc:
            logger.exception('Failed to enqueue ingestion job #%s, falling back to sync mode.', job.id)
            try:
                file_full_path = media_root / 'ingestion_uploads' / stored_name
                with open(file_full_path, 'rb') as handle:
                    file_bytes = handle.read()

                source = ingest_uploaded_file(
                    user=request.user,
                    uploaded_file=SimpleUploadedFile(
                        name=uploaded_file.name,
                        content=file_bytes,
                        content_type=getattr(uploaded_file, 'content_type', 'application/octet-stream'),
                    ),
                    name=serializer.validated_data['name'],
                    source_type=serializer.validated_data['source_type'],
                    delimiter=serializer.validated_data['delimiter'],
                    encoding=serializer.validated_data['encoding'],
                    has_header=serializer.validated_data['has_header'],
                    description=serializer.validated_data.get('description'),
                    tags=serializer.validated_data.get('tags', []),
                    retention_days=serializer.validated_data['retention_days'],
                    required_columns=serializer.validated_data.get('required_columns', []),
                    key_columns=serializer.validated_data.get('key_columns', []),
                    strict_validation=serializer.validated_data['strict_validation'],
                    template_id=serializer.validated_data.get('template_id'),
                    column_mapping=serializer.validated_data.get('column_mapping', {}),
                )
            except IngestionError as ingestion_exc:
                job.status = 'failed'
                job.error_message = str(ingestion_exc)
                job.save(update_fields=['status', 'error_message'])
                return Response({'error': str(ingestion_exc)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as fallback_exc:
                logger.exception('Unexpected sync fallback failure for ingestion job #%s.', job.id)
                job.status = 'failed'
                job.error_message = str(fallback_exc)
                job.save(update_fields=['status', 'error_message'])
                return Response(
                    {'error': str(fallback_exc) or 'Une erreur inattendue est survenue pendant l import.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            job.status = 'completed'
            job.progress_percent = 100
            job.source = source
            job.error_message = None
            job.save(update_fields=['status', 'progress_percent', 'source', 'error_message'])
        else:
            job.celery_task_id = task.id
            job.save(update_fields=['celery_task_id'])

        serializer = IngestionJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class RawDataListView(generics.ListAPIView):
    """
    List raw rows for a specific data source visible to the current user.
    GET /api/ingestion/datasources/<id>/raw_data/
    """

    serializer_class = RawDataSerializer
    permission_classes = [CanReadData]
    pagination_class = RawDataPagination

    def get_queryset(self):
        source_queryset = DataSource.objects.filter(pk=self.kwargs['pk'])
        source_queryset = _organization_scoped_sources(source_queryset, self.request.user)

        if not source_queryset.exists():
            raise Http404('Data source not found.')

        queryset = RawData.objects.select_related('source', 'source__uploaded_by').filter(
            source_id=self.kwargs['pk']
        )
        validation_status = self.request.query_params.get('status')
        if validation_status:
            queryset = queryset.filter(validation_status=validation_status)
        return queryset.order_by('row_number')


class IngestionJobListView(generics.ListAPIView):
    """
    List async ingestion jobs visible to the current user.
    GET /api/ingestion/jobs/
    """

    serializer_class = IngestionJobSerializer
    permission_classes = [CanReadData]

    def get_queryset(self):
        queryset = IngestionJob.objects.select_related('requested_by', 'source', 'source__uploaded_by')
        return _filter_jobs_for_user(queryset, self.request.user).order_by('-created_at')


class IngestionJobView(generics.RetrieveAPIView):
    """
    Check status of an async ingestion job.
    GET /api/ingestion/jobs/<job_id>/
    """
    serializer_class = IngestionJobSerializer
    permission_classes = [CanReadData]
    lookup_field = 'pk'

    def get_queryset(self):
        queryset = IngestionJob.objects.select_related('requested_by', 'source', 'source__uploaded_by')
        return _filter_jobs_for_user(queryset, self.request.user)


class DataSourcePreviewView(APIView):
    """
    Analyze a source file before import.
    POST /api/ingestion/sources/preview/
    """

    parser_classes = [MultiPartParser, FormParser]
    # File preview does not persist data; allow read-capable users.
    permission_classes = [CanReadData]

    def post(self, request):
        serializer = DataSourcePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = preview_uploaded_file(
                user=request.user,
                uploaded_file=serializer.validated_data['file'],
                source_type=serializer.validated_data['source_type'],
                delimiter=serializer.validated_data['delimiter'],
                encoding=serializer.validated_data['encoding'],
                has_header=serializer.validated_data['has_header'],
                required_columns=serializer.validated_data.get('required_columns', []),
                key_columns=serializer.validated_data.get('key_columns', []),
                template_id=serializer.validated_data.get('template_id'),
                column_mapping=serializer.validated_data.get('column_mapping', {}),
            )
        except IngestionError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)
