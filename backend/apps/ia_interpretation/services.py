"""
M6 — Interprétation KPI via Groq API (Llama 3.3 70B par défaut).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.kpi.models import KPI

logger = logging.getLogger(__name__)


class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime, Decimal, and other non-serializable types."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if hasattr(obj, '__float__'):
            return float(obj)
        return super().default(obj)


def safe_json_dumps(obj, **kwargs):
    """JSON dumps with safe encoding for datetime/Decimal."""
    return json.dumps(obj, cls=SafeJSONEncoder, ensure_ascii=False, **kwargs)

SYSTEM_PROMPT = """Tu es Decisio AI, un analyste data intelligent et conversationnel pour une PME francophone.

## Ton rôle
Tu es un compagnon de données complet. L'utilisateur peut te parler de ses KPIs, de ses fichiers, de ses colonnes, de ses tendances, ou simplement discuter de ses données.

## Règles fondamentales
- Réponds en français clair, ton professionnel mais chaleureux.
- NE JAMAIS inventer de valeurs, de tendances ou de données non fournies.
- Si une info manque, dis-le explicitement.
- Structures tes réponses avec des titres Markdown (## Titre), des listes à puces, des tableaux.
- NE JAMAIS utiliser d'astérisques (*) pour la mise en forme.
- Sois concis mais complet. Va à l'essentiel.

## Tu reçois trois types de contexte

### 1. Données KPI (si disponibles)
Des KPIs avec leurs valeurs, breakdowns, historiques. Utilise-les pour :
- Expliquer les chiffres et leur signification business
- Détecter anomalies (variance > 20%, écarts target, tendances)
- Comparer les dimensions (régions, produits, etc.)
- Proposer des actions concrètes

### 2. Contexte d'un widget spécifique (si l'utilisateur clique "Analyser")
Un widget précis avec sa mesure, agrégation, dimension et ses données.
Concentre-toi sur CE widget : explique les résultats, identifie forces/faiblesses, propose des actions.

### 3. Métadonnées de données brutes (si l'utilisateur pose une question sur ses données)
La structure du fichier : colonnes, types, échantillons. Utilise-les pour :
- Décrire ce que contient le fichier
- Expliquer ce que signifie chaque colonne
- Suggérer des analyses pertinentes
- Répondre à des questions comme "qu'est-ce que mon fichier contient ?"

## Comment répondre
- Si on te pose une question sur un KPI → analyse les chiffres fournis
- Si on te demande d'expliquer une colonne → utilise les métadonnées et échantillons
- Si on te demande "qu'est-ce que j'ai dans mes données ?" → décris la structure et le contenu
- Si on te pose une question générale → réponds avec les données disponibles
- Si on te demande un conseil → donne des recommandations actionnables
- Quand tu detects une anomalie → signale-la avec "Alerte" et explique l'impact
"""


class KPIInterpretationError(Exception):
    """Erreur métier (pas de clé API, pas de KPI, etc.)."""


def _visible_kpis_queryset(user):
    qs = KPI.objects.filter(is_active=True).select_related("owner").order_by("-updated_at")
    if user.is_superuser:
        return qs
    return qs.filter(Q(is_public=True) | Q(owner=user)).distinct()


def _serialize_kpi_snapshot(kpi: KPI, *, enrichi: bool = False) -> Dict[str, Any]:
    recent_calcs = list(kpi.calculations.order_by("-period_end")[:5])
    latest = recent_calcs[0] if recent_calcs else None

    latest_data = None
    if latest:
        latest_data = {
            "period_label": latest.period_label,
            "value": float(latest.calculated_value),
            "previous_value": float(latest.previous_value) if latest.previous_value is not None else None,
            "variance_percent": float(latest.variance_percent) if latest.variance_percent is not None else None,
            "status": latest.status,
            "anomaly_detected": latest.anomaly_detected,
            "data_quality_score": float(latest.data_quality_score) if latest.data_quality_score is not None else None,
            "rows_processed": latest.rows_processed,
            "breakdown": latest.breakdown if latest.breakdown else None,
        }

    history = []
    for calc in recent_calcs:
        history.append({
            "period_label": calc.period_label,
            "value": float(calc.calculated_value),
            "status": calc.status,
        })

    anomaly_signals = []
    if latest:
        var = latest.variance_percent
        if var is not None and abs(float(var)) > 20:
            anomaly_signals.append(f"Variance elevee : {float(var):+.1f}%")
        if kpi.target_value is not None and float(latest.calculated_value) > 0:
            ecart = (float(latest.calculated_value) - float(kpi.target_value)) / float(kpi.target_value) * 100
            if abs(ecart) > 15:
                anomaly_signals.append(f"Ecart target : {ecart:+.1f}%")
        if latest.anomaly_detected:
            anomaly_signals.append("Anomaly statistique detectee (Z-score)")
        if len(history) >= 3:
            vals = [h["value"] for h in history]
            if all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
                anomaly_signals.append("Tendance baissiere continue sur les 3 dernieres periodes")
            elif all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
                anomaly_signals.append("Tendance haussiere continue sur les 3 dernieres periodes")
        if latest.breakdown and isinstance(latest.breakdown, list):
            if len(latest.breakdown) >= 2:
                bvals = [b.get("value", 0) for b in latest.breakdown if isinstance(b, dict)]
                if bvals:
                    bmax, bmin = max(bvals), min(bvals)
                    if bmax > 0 and bmin / bmax < 0.1:
                        anomaly_signals.append("Forte disparite entre dimensions dans le breakdown")

    result = {
        "id": kpi.id,
        "code": kpi.code,
        "name": kpi.name,
        "description": kpi.description or "",
        "category": kpi.category,
        "unit": kpi.unit,
        "frequency": kpi.frequency,
        "target_value": float(kpi.target_value) if kpi.target_value is not None else None,
        "latest_calculation": latest_data,
        "recent_history": history,
        "anomaly_signals": anomaly_signals,
    }

    if enrichi:
        result["definition"] = {
            "description": kpi.description or "Non definie",
            "formula": kpi.formula or "Non definie",
            "formula_type": kpi.formula_type or "unknown",
            "source_table": kpi.source_table or "nettoyage_cleaneddata",
            "measure_column": kpi.measure_column or "non precise",
            "dimension_columns": kpi.dimension_columns or [],
            "aggregation_method": kpi.aggregation_method or "SUM",
            "filter_conditions": kpi.filter_conditions or {},
            "warning_threshold": float(kpi.warning_threshold) if kpi.warning_threshold is not None else None,
            "critical_threshold": float(kpi.critical_threshold) if kpi.critical_threshold is not None else None,
            "operator": kpi.operator,
            "target_value": float(kpi.target_value) if kpi.target_value is not None else None,
        }

    return result


def build_kpi_context_for_user(
    *,
    user,
    kpi_ids: Optional[List[int]] = None,
    max_kpis: int = 15,
    enrichi: bool = False,
) -> tuple[List[Dict[str, Any]], List[KPI]]:
    qs = _visible_kpis_queryset(user)
    if kpi_ids:
        qs = qs.filter(id__in=kpi_ids)
    kpis = list(qs[:max_kpis])
    if not kpis:
        raise KPIInterpretationError("Aucun KPI disponible pour cette requete (filtre ou droits).")
    payload = [_serialize_kpi_snapshot(k, enrichi=enrichi) for k in kpis]
    return payload, kpis


def get_kpis_by_source(user, source_id: int) -> List[Dict[str, Any]]:
    from apps.dashboard.models import Widget
    from apps.kpi.services import M4WorkbenchService

    widgets = Widget.objects.filter(
        data_source_id=source_id,
        data_source_type="kpi",
        is_active=True,
        dashboard__created_by=user,
    ).order_by("position_y", "position_x")

    results = []
    workbench = M4WorkbenchService(user)

    for widget in widgets:
        config = widget.configuration or {}
        measure = config.get("measure") or config.get("mesure") or ""
        aggregation = config.get("aggregation", "sum")
        group_by = config.get("group_by", [])
        source_table = config.get("source_table", "nettoyage_cleaneddata")

        calc_config = {
            "measure": measure,
            "mesure": measure,
            "aggregation": aggregation,
            "group_by": group_by,
            "source_table": source_table,
            "source_id": source_id,
        }

        try:
            result = workbench.calculate_metric(calc_config)
        except Exception:
            logger.debug("Widget %s calculation failed, skipping", widget.id)
            continue

        results.append({
            "widget_id": widget.id,
            "title": widget.title or config.get("nom_kpi") or measure,
            "measure": measure,
            "aggregation": aggregation,
            "group_by": group_by,
            "value": result.get("value", 0),
            "formatted_value": result.get("formatted_value", "0"),
            "rows_processed": result.get("rows_processed", 0),
            "breakdown": result.get("breakdown", []),
            "chart_type": widget.widget_type,
            "semantic_type": config.get("semantic_type", "other"),
        })

    return results


def build_kpi_context_by_source(
    *,
    user,
    source_id: int,
    widget_ids: Optional[List[int]] = None,
    max_kpis: int = 5,
) -> List[Dict[str, Any]]:
    from apps.dashboard.models import Widget
    from apps.kpi.services import M4WorkbenchService

    widgets = Widget.objects.filter(
        data_source_id=source_id,
        data_source_type="kpi",
        is_active=True,
        dashboard__created_by=user,
    )

    if widget_ids:
        widgets = widgets.filter(id__in=widget_ids)

    widgets = widgets.order_by("position_y", "position_x")[:max_kpis]

    if not widgets:
        raise KPIInterpretationError(
            "Aucun KPI disponible pour cette source. Créez un dashboard d'abord."
        )

    workbench = M4WorkbenchService(user)
    payload = []

    for widget in widgets:
        config = widget.configuration or {}
        measure = config.get("measure") or config.get("mesure") or ""
        aggregation = config.get("aggregation", "sum")
        group_by = config.get("group_by", [])
        source_table = config.get("source_table", "nettoyage_cleaneddata")

        calc_config = {
            "measure": measure,
            "mesure": measure,
            "aggregation": aggregation,
            "group_by": group_by,
            "source_table": source_table,
            "source_id": source_id,
        }

        try:
            result = workbench.calculate_metric(calc_config)
        except Exception:
            logger.debug("Widget %s calculation failed, skipping", widget.id)
            continue

        anomaly_signals = []
        value = result.get("value", 0)
        breakdown = result.get("breakdown", [])

        # Truncate breakdown: keep top 5 + bottom 3 only
        if breakdown and isinstance(breakdown, list) and len(breakdown) > 8:
            sorted_b = sorted(breakdown, key=lambda x: x.get("value", 0), reverse=True)
            breakdown = sorted_b[:5] + sorted_b[-3:]

        if breakdown and isinstance(breakdown, list) and len(breakdown) >= 2:
            bvals = [b.get("value", 0) for b in breakdown if isinstance(b, dict)]
            if bvals:
                bmax, bmin = max(bvals), min(bvals)
                if bmax > 0 and bmin / bmax < 0.1:
                    anomaly_signals.append("Forte disparite entre dimensions")

        payload.append({
            "id": widget.id,
            "name": widget.title or config.get("nom_kpi") or measure,
            "measure": measure,
            "aggregation": aggregation,
            "category": config.get("semantic_type", "other"),
            "value": value,
            "status": "on_target",
            "breakdown": breakdown,
            "anomaly_signals": anomaly_signals,
        })

    return payload


def build_data_context_for_source(*, source_id: int, max_sample_rows: int = 5) -> Dict[str, Any]:
    """Build context about raw data structure for a source (columns, types, samples)."""
    from django.db import transaction
    from apps.ingestion.models import DataSource, RawData
    from apps.nettoyage.models import CleanedData

    source = DataSource.objects.filter(pk=source_id).first()
    if not source:
        return {}

    context: Dict[str, Any] = {
        "source_name": source.name,
        "source_type": source.source_type,
        "row_count": source.row_count,
        "column_count": source.column_count,
        "status": source.status,
        "description": source.description or "",
    }

    # Get columns from metadata
    meta = source.metadata or {}
    columns = meta.get("columns") or meta.get("schema") or []
    if columns:
        context["columns"] = columns[:50]

    # Get sample rows — use savepoint so a failure doesn't corrupt the outer transaction
    try:
        with transaction.atomic():
            cleaned_jobs = list(
                CleanedData.objects.filter(job__data_source=source)
                .order_by("-cleaned_at")
                .values_list("job_id", flat=True)[:1]
            )
            if cleaned_jobs:
                samples = list(
                    CleanedData.objects.filter(job_id=cleaned_jobs[0])
                    .order_by("id")[:max_sample_rows]
                    .values_list("data", flat=True)
                )
                context["sample_rows"] = samples
    except Exception:
        pass

    # Fallback: get sample from raw data
    if "sample_rows" not in context:
        try:
            with transaction.atomic():
                raw_samples = list(
                    RawData.objects.filter(source=source)
                    .order_by("row_number")[:max_sample_rows]
                    .values_list("data", flat=True)
                )
                context["sample_rows"] = raw_samples
        except Exception:
            pass

    return context


def interpret_kpis_with_groq(
    *,
    user,
    question: str,
    kpi_context: List[Dict[str, Any]],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    conversation_history: Optional[str] = None,
    widget_context: Optional[str] = None,
    data_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_key = getattr(settings, "GROQ_API_KEY", "") or ""
    if not api_key.strip():
        raise KPIInterpretationError(
            "GROQ_API_KEY n est pas configuree. Ajoutez-la dans l environnement pour activer l interpretation."
        )

    model_name = (model or getattr(settings, "GROQ_KPI_MODEL", "openai/gpt-oss-120b") or "openai/gpt-oss-120b").strip()

    from groq import Groq

    client = Groq(api_key=api_key)

    # Build user content with all context layers
    parts = [f"Question :\n{question.strip()}\n"]

    if conversation_history:
        parts.append(f"Historique :\n{conversation_history}\n")

    if widget_context:
        parts.append(f"Contexte widget :\n{widget_context}\n")

    if kpi_context:
        kpi_json = safe_json_dumps(kpi_context, indent=2)
        # Truncate KPI data if too large (keep under ~8000 chars for KPIs)
        if len(kpi_json) > 8000:
            kpi_json = kpi_json[:8000] + "\n... (tronqué)"
        parts.append(f"Données KPI :\n{kpi_json}\n")

    if data_context:
        data_json = safe_json_dumps(data_context, indent=2)
        # Truncate data context if too large (keep under ~4000 chars)
        if len(data_json) > 4000:
            data_json = data_json[:4000] + "\n... (tronqué)"
        parts.append(f"Métadonnées source :\n{data_json}\n")

    user_content = "\n".join(parts)

    # Safety cap: truncate total to ~14000 chars (~10K tokens, under Groq free tier 12K TPM)
    if len(user_content) > 14000:
        user_content = user_content[:14000] + "\n\n... (contexte tronqué pour respecter la limite de tokens)"

    started = time.perf_counter()
    try:
        completion = client.chat.completions.create(
            model=model_name,
            temperature=0.5,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
    except Exception as exc:
        logger.exception("Groq KPI interpretation failed")
        raise KPIInterpretationError(f"Appel Groq impossible : {exc}") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    choice = completion.choices[0] if completion.choices else None
    text = (choice.message.content or "").strip() if choice and choice.message else ""

    usage = completion.usage
    tokens = None
    if usage:
        tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)

    return {
        "text": text,
        "model": model_name,
        "tokens_used": tokens,
        "processing_time_ms": elapsed_ms,
        "raw_id": completion.id,
    }


def persist_ai_analysis(
    *,
    user,
    question: str,
    kpi_context: List[Dict[str, Any]],
    result: Dict[str, Any],
    primary_kpi: Optional[KPI] = None,
) -> int:
    from apps.ia_interpretation.models import AIAnalysis

    row = AIAnalysis.objects.create(
        analysis_type="summary",
        prompt=question[:50000],
        context_data={"kpis": kpi_context},
        model_provider="groq",
        model_name=result["model"],
        model_parameters={"temperature": 0.5, "max_tokens": 4000},
        response=result["text"],
        tokens_used=result.get("tokens_used"),
        processing_time_ms=result.get("processing_time_ms"),
        status="completed",
        requested_by=user,
        completed_at=timezone.now(),
        kpi=primary_kpi,
    )
    return row.id
