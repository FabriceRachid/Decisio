"""
M7: Anomaly detection — Isolation Forest on tabular ingestion/cleaned data.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
from django.contrib.auth.models import User
from django.utils import timezone
from sklearn.ensemble import IsolationForest

from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData

logger = logging.getLogger(__name__)

Backend = Literal["raw", "cleaned"]


class AnomalyDetectionError(Exception):
    """Invalid input or insufficient data for detection."""


def _user_can_access_source(user: User, source: DataSource) -> bool:
    if user.is_superuser:
        return True
    role = getattr(user.profile, "role", "viewer")
    if role == "admin":
        return True
    return source.uploaded_by_id == user.id


def _extract_numeric_matrix(
    rows: Sequence[Dict[str, Any]],
    feature_columns: Sequence[str],
) -> Tuple[np.ndarray, List[int]]:
    """Build float matrix and parallel row identifiers (ingestion row_number)."""
    X_list: List[List[float]] = []
    row_ids: List[int] = []

    for row in rows:
        rn = int(row.get("row_number", 0))
        payload = row.get("data") if isinstance(row.get("data"), dict) else {}
        vals: List[float] = []
        has_any = False
        for col in feature_columns:
            raw = payload.get(col)
            try:
                if raw is None or (isinstance(raw, str) and str(raw).strip() == ""):
                    vals.append(float("nan"))
                else:
                    vals.append(float(raw))
                    has_any = True
            except (TypeError, ValueError):
                vals.append(float("nan"))
        if has_any:
            X_list.append(vals)
            row_ids.append(rn)

    if not X_list:
        raise AnomalyDetectionError("Aucune ligne exploitable pour les colonnes demandees.")

    X = np.asarray(X_list, dtype=np.float64)
    # Imputation simple par mediane colonne (sklearn n'accepte pas NaN)
    col_med = np.nanmedian(X, axis=0)
    col_med = np.where(np.isnan(col_med), 0.0, col_med)
    inds = np.where(np.isnan(X))
    if inds[0].size:
        X[inds] = np.take(col_med, inds[1])

    if X.shape[0] < 2:
        raise AnomalyDetectionError("Au moins deux lignes sont necessaires pour Isolation Forest.")

    return X, row_ids


def _load_rows(source: DataSource, backend: Backend, max_rows: int) -> List[Dict[str, Any]]:
    if backend == "raw":
        qs = RawData.objects.filter(source=source).order_by("row_number").values("row_number", "data")[:max_rows]
        return list(qs)
    qs = (
        CleanedData.objects.filter(original_data__source=source)
        .select_related("original_data")
        .order_by("original_data__row_number")
        .values("original_data__row_number", "data")[:max_rows]
    )
    out: List[Dict[str, Any]] = []
    for item in qs:
        out.append({"row_number": item["original_data__row_number"], "data": item["data"]})
    return out


def run_isolation_forest(
    *,
    user: User,
    source_id: int,
    feature_columns: Sequence[str],
    backend: Backend = "raw",
    contamination: float = 0.05,
    max_rows: int = 5000,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Fit Isolation Forest on numeric features and return per-row scores + outlier flags.

    contamination: fraction attendue d'anomalies (borne haute sklearn ~0.5).
    """
    if not feature_columns:
        raise AnomalyDetectionError("feature_columns ne peut pas etre vide.")
    if not (0 < contamination <= 0.5):
        raise AnomalyDetectionError("contamination doit etre dans ]0, 0.5].")

    try:
        source = DataSource.objects.get(pk=source_id)
    except DataSource.DoesNotExist as exc:
        raise AnomalyDetectionError("Source introuvable.") from exc

    if not _user_can_access_source(user, source):
        raise AnomalyDetectionError("Acces refuse a cette source.")

    rows = _load_rows(source, backend, max_rows)
    if len(rows) < 2:
        raise AnomalyDetectionError("Pas assez de lignes pour l'analyse.")

    X, row_numbers = _extract_numeric_matrix(rows, feature_columns)
    n_samples, n_features = X.shape

    # Ajuster contamination si trop de points pour la contrainte sklearn
    eff_contamination = float(min(contamination, (n_samples - 1) / n_samples * 0.49))

    clf = IsolationForest(
        n_estimators=min(200, max(50, n_samples)),
        contamination=eff_contamination,
        random_state=random_state,
        bootstrap=True,
    )
    clf.fit(X)
    pred = clf.predict(X)
    raw_scores = -clf.decision_function(X)

    details: List[Dict[str, Any]] = []
    outlier_rows: List[int] = []
    outlier_indices: List[int] = []
    for i in range(n_samples):
        is_out = pred[i] == -1
        details.append(
            {
                "row_number": row_numbers[i],
                "score": round(float(raw_scores[i]), 6),
                "is_outlier": is_out,
            }
        )
        if is_out:
            outlier_rows.append(row_numbers[i])
            outlier_indices.append(i)

    # Calculer la mediane de chaque colonne pour comparer les outliers
    col_medians: Dict[str, float] = {}
    for j, col in enumerate(feature_columns):
        vals = X[:, j]
        masked = vals[~np.isnan(vals)]
        if len(masked):
            col_medians[col] = float(np.median(masked))

    # Pour chaque outlier, trouver les colonnes qui devient le plus
    outlier_details: List[Dict[str, Any]] = []
    for idx in outlier_indices:
        row_data = rows[idx].get("data", {}) if isinstance(rows[idx].get("data"), dict) else {}
        deviations = []
        for j, col in enumerate(feature_columns):
            median = col_medians.get(col)
            if median is None or median == 0:
                continue
            raw_val = row_data.get(col)
            try:
                fval = float(raw_val)
                ratio = fval / median
                if ratio > 2.5 or ratio < 0.4:
                    deviations.append({
                        "column": col,
                        "valeur": fval,
                        "mediane": round(median, 2),
                        "ratio": round(ratio, 1),
                        "direction": "supérieur" if ratio > 2.5 else "inférieur",
                        "label": f"{col}={fval} (valeur habituelle={round(median, 2)})",
                    })
            except (TypeError, ValueError):
                pass
        deviations.sort(key=lambda d: abs(d["ratio"]), reverse=True)
        outlier_details.append({
            "row_number": row_numbers[idx],
            "deviations": deviations[:3],
        })

    return {
        "source_id": source.id,
        "source_name": source.name,
        "backend": backend,
        "feature_columns": list(feature_columns),
        "n_samples": n_samples,
        "n_features": n_features,
        "contamination_requested": contamination,
        "contamination_effective": eff_contamination,
        "outlier_count": len(outlier_rows),
        "outlier_row_numbers": outlier_rows,
        "col_medians": col_medians,
        "outlier_details": outlier_details,
        "rows": details,
    }


def persist_detection_run(
    *,
    user: User,
    payload: Dict[str, Any],
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enregistre un AnomalyModel + un enregistrement Anomaly agrege (liste de row_ids).
    """
    from apps.anomalies.models import Anomaly, AnomalyModel

    source = DataSource.objects.get(pk=payload["source_id"])
    if not _user_can_access_source(user, source):
        raise AnomalyDetectionError("Acces refuse a cette source.")

    outlier_rows: List[int] = payload["outlier_row_numbers"]
    feat = payload["feature_columns"]
    version = "sklearn-if"

    name = model_name or f"IF source {source.id} {timezone.now().strftime('%Y%m%d%H%M%S')}"

    am = AnomalyModel.objects.create(
        name=name[:200],
        description="Isolation Forest — execution API",
        algorithm="isolation_forest",
        algorithm_version=version,
        training_parameters={
            "contamination_requested": payload["contamination_requested"],
            "contamination_effective": payload["contamination_effective"],
            "max_rows_cap": payload.get("max_rows_used"),
        },
        training_source=source,
        training_features=list(feat),
        training_samples=payload["n_samples"],
        created_by=user,
        is_active=True,
        last_inference_at=timezone.now(),
        inference_count=1,
    )

    max_score = max((r["score"] for r in payload["rows"] if r.get("is_outlier")), default=0.0)
    mean_score = (
        float(sum(r["score"] for r in payload["rows"] if r.get("is_outlier")) / len(outlier_rows))
        if outlier_rows
        else 0.0
    )
    score_dec = Decimal(str(round(min(max_score, 9.9999), 4))).quantize(Decimal("0.0001"))

    severity = "low"
    if len(outlier_rows) == 0:
        severity = "low"
    elif len(outlier_rows) <= max(1, payload["n_samples"] // 50):
        severity = "medium"
    elif len(outlier_rows) <= max(2, payload["n_samples"] // 20):
        severity = "high"
    else:
        severity = "critical"

    outlier_details = payload.get("outlier_details", [])
    pct = round(len(outlier_rows) / max(payload['n_samples'], 1) * 100, 1)

    # Construire des exemples concrets: "le montant (50 000) est plus eleve que d'habitude (320)"
    examples: List[str] = []
    for od in outlier_details[:2]:
        devs = od.get("deviations", [])
        if devs:
            sentence_parts = [f"ligne #{od['row_number']} :"]
            for d in devs[:2]:
                dir_word = "plus eleve" if d["direction"] == "supérieur" else "plus faible"
                sentence_parts.append(
                    f"le {d['column']} ({d['valeur']}) est {dir_word} que d'habitude ({d['mediane']})"
                )
            examples.append(", ".join(sentence_parts))

    if examples:
        example_text = "\nPar exemple :\n- " + "\n- ".join(examples)
    else:
        example_text = ""

    explanation = (
        f"{len(outlier_rows)} ligne(s) sur {payload['n_samples']} ont des valeurs anormales."
        f"{example_text}\n"
        f"Ces ecarts peuvent etre une erreur de saisie, un cas exceptionnel ou un signal a surveiller."
    )

    anomaly = Anomaly.objects.create(
        model=am,
        data_source=source,
        row_ids=outlier_rows,
        anomaly_score=score_dec,
        severity=severity,
        confidence=Decimal(str(round(min(99.99, max(0.0, 50.0 + mean_score * 20.0)), 2))),
        affected_columns=list(feat),
        contribution_scores={c: 1.0 / len(feat) for c in feat},
        explanation=explanation,
        anomaly_type="point",
        status="new",
    )

    return {"anomaly_model_id": am.id, "anomaly_id": anomaly.id}
