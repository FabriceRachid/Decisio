"""M6 URL routing."""

from django.urls import path

from apps.ia_interpretation.views import InterpretKpisView, SourceKPIsView, AIHistoryView

urlpatterns = [
    path("interpret-kpis/", InterpretKpisView.as_view(), name="ia-interpret-kpis"),
    path("sources/<int:source_id>/kpis/", SourceKPIsView.as_view(), name="ia-source-kpis"),
    path("history/", AIHistoryView.as_view(), name="ia-history"),
]
