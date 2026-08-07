from django.urls import path

from apps.ingestion.views import (
    DataSourceDetailView,
    DataSourceListView,
    DataSourcePreviewView,
    DataSourceUploadView,
    DataSourceAsyncUploadView,
    RawDataListView,
    IngestionJobListView,
    IngestionJobView,
    ImportTemplateListView,
    SheetRelationListView,
    SheetRelationCreateView,
    SheetRelationDetailView,
    SuggestRelationsView,
    JoinedViewView,
)


urlpatterns = [
    path('templates/', ImportTemplateListView.as_view(), name='ingestion_template_list'),
    path('sources/', DataSourceListView.as_view(), name='ingestion_source_list'),
    path('sources/<int:pk>/', DataSourceDetailView.as_view(), name='ingestion_source_detail'),
    path('sources/<int:pk>/raw-data/', RawDataListView.as_view(), name='ingestion_source_raw_data'),
    path('sources/<int:pk>/relations/', SheetRelationListView.as_view(), name='ingestion_source_relations'),
    path('sources/<int:pk>/relations/create/', SheetRelationCreateView.as_view(), name='ingestion_source_relation_create'),
    path('sources/<int:source_pk>/relations/<int:pk>/', SheetRelationDetailView.as_view(), name='ingestion_source_relation_detail'),
    path('sources/<int:pk>/suggest-relations/', SuggestRelationsView.as_view(), name='ingestion_source_suggest_relations'),
    path('sources/<int:pk>/joined-view/', JoinedViewView.as_view(), name='ingestion_source_joined_view'),
    path('sources/preview/', DataSourcePreviewView.as_view(), name='ingestion_source_preview'),
    path('sources/upload/', DataSourceUploadView.as_view(), name='ingestion_source_upload'),
    path('sources/async-upload/', DataSourceAsyncUploadView.as_view(), name='ingestion_source_async_upload'),
    path('datasources/', DataSourceListView.as_view(), name='ingestion_datasource_list_legacy'),
    path('datasources/<int:pk>/', DataSourceDetailView.as_view(), name='ingestion_datasource_detail_legacy'),
    path('datasources/<int:pk>/raw_data/', RawDataListView.as_view(), name='ingestion_datasource_raw_data_legacy'),
    path('jobs/', IngestionJobListView.as_view(), name='ingestion_job_list'),
    path('jobs/<int:pk>/', IngestionJobView.as_view(), name='ingestion_job_detail'),
]
