from django.urls import path, include

from apps.nettoyage.views import (
    CleaningApplyView,
    CleaningApplyAsyncView,
    CleaningComparisonView,
    CleaningJobDetailView,
    CleaningJobListView,
    CleaningJobReplayView,
    CleaningJobValidationView,
    CleaningJobExportView,
    CleaningPipelineDetailView,
    CleaningPipelineListCreateView,
    CleaningPreviewView,
    CleaningRuleDetailView,
    CleaningRuleListCreateView,
    CleaningSuggestionView,
)


urlpatterns = [
    # Rules endpoints
    path('rules/', CleaningRuleListCreateView.as_view(), name='cleaning_rule_list'),
    path('rules/<int:pk>/', CleaningRuleDetailView.as_view(), name='cleaning_rule_detail'),
    
    # Pipelines endpoints
    path('pipelines/', CleaningPipelineListCreateView.as_view(), name='cleaning_pipeline_list'),
    path('pipelines/<int:pk>/', CleaningPipelineDetailView.as_view(), name='cleaning_pipeline_detail'),
    
    # Jobs endpoints
    path('jobs/', CleaningJobListView.as_view(), name='cleaning_job_list'),
    path('jobs/<int:job_id>/', CleaningJobDetailView.as_view(), name='cleaning_job_detail'),
    path('jobs/<int:job_id>/comparison/', CleaningComparisonView.as_view(), name='cleaning_job_comparison'),
    path('jobs/<int:job_id>/replay/', CleaningJobReplayView.as_view(), name='cleaning_job_replay'),
    path('jobs/<int:job_id>/validate/', CleaningJobValidationView.as_view(), name='cleaning_job_validate'),
    path('jobs/<int:job_id>/export/', CleaningJobExportView.as_view(), name='cleaning_job_export'),
    
    # Source-based endpoints
    path('sources/<int:source_id>/suggestions/', CleaningSuggestionView.as_view(), name='cleaning_suggestions'),
    path('sources/<int:source_id>/preview/', CleaningPreviewView.as_view(), name='cleaning_preview'),
    path('sources/<int:source_id>/apply/', CleaningApplyView.as_view(), name='cleaning_apply'),
    path('sources/<int:source_id>/apply-async/', CleaningApplyAsyncView.as_view(), name='cleaning_apply_async'),

    # Intelligent structural detection endpoints
    path('structure/', include('apps.nettoyage.structure_urls')),
]
