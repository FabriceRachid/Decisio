from django.urls import path

from apps.nettoyage.structure_views import (
    ApplyPlanView,
    CorrectionExamplesView,
    CorrectionValidateView,
    ExecuteAfterReviewView,
    PlanPreviewView,
    StructuralDetectView,
    StructuralRunDetailView,
    StructuralRunListView,
)

urlpatterns = [
    path(
        'sources/<int:source_id>/structural-detect/',
        StructuralDetectView.as_view(),
        name='structural_detect',
    ),
    path(
        'sources/<int:source_id>/apply-plan/',
        ApplyPlanView.as_view(),
        name='apply_plan',
    ),
    path(
        'sources/<int:source_id>/plan-preview/',
        PlanPreviewView.as_view(),
        name='plan_preview',
    ),
    path(
        'sources/<int:source_id>/execute-after-review/',
        ExecuteAfterReviewView.as_view(),
        name='execute_after_review',
    ),
    path(
        'structural-runs/',
        StructuralRunListView.as_view(),
        name='structural_run_list',
    ),
    path(
        'structural-runs/<int:run_id>/',
        StructuralRunDetailView.as_view(),
        name='structural_run_detail',
    ),
    path(
        'structural-runs/<int:run_id>/validate/',
        CorrectionValidateView.as_view(),
        name='structural_run_validate',
    ),
    path(
        'correction-examples/',
        CorrectionExamplesView.as_view(),
        name='correction_examples',
    ),
]
