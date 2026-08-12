from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re
from typing import Any
import unicodedata

import pandas as pd
from django.contrib.auth.models import User

from apps.authentication.models import Organization
from apps.ingestion.models import DataSource
from apps.nettoyage.models import CleaningJob


@dataclass
class ColumnSuggestion:
    column: str
    dtype: str
    samples: list[Any] = field(default_factory=list)
    null_ratio: float = 0.0
    unique_ratio: float = 0.0


@dataclass
class MetricSuggestion:
    label: str
    measure_column: str
    aggregation: str
    description: str


class KPIAutoService:
    COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
        "montant_total": ("montant_total", "amount", "totalamount", "salesamount", "sales", "montant", "total"),
        "montant_entree": ("montant_entree", "encaissement", "creditamount", "incomingamount", "paidamount"),
        "montant_sortie": ("montant_sortie", "decaissement", "debitamount", "outgoingamount", "expenseamount"),
        "date": ("date", "orderdate", "transactiondate", "date_commande", "date_facture"),
        "produit": ("produit", "product", "productname", "englishproductname", "article", "item"),
        "client": ("client", "customer", "customername", "fullname", "firstname", "nom"),
        "client_id": ("client_id", "id_client", "customerkey", "customeralternatekey", "emailaddress"),
        "quantite": ("quantite", "quantity", "qty", "qte"),
        "prix_unitaire": ("prix_unitaire", "unitprice", "listprice", "standardcost", "prix"),
        "stock_final": ("stock_final", "endingstock", "finalstock", "stock"),
        "prix_achat": ("prix_achat", "purchaseprice", "unitcost", "cout_achat"),
        "categorie": ("categorie", "category", "productcategory", "englishproductcategoryname"),
        "region": ("region", "stateprovince", "salesterritoryregion"),
        "pays": ("pays", "country", "countryregionname", "englishcountryregionname"),
        "ville": ("ville", "city"),
        "id_commande": ("id_commande", "order_id", "orderid", "commande_id", "invoice_id"),
        "revenu_annuel": ("revenu_annuel", "yearlyincome"),
        "date_naissance": ("date_naissance", "birthdate"),
        "date_premier_achat": ("date_premier_achat", "datefirstpurchase"),
    }

    DOMAIN_SIGNAL_WEIGHTS: dict[str, dict[str, int]] = {
        "sales": {"montant_total": 5, "id_commande": 4, "date": 3, "produit": 3, "client": 2, "quantite": 2},
        "customers": {"client_id": 5, "date_naissance": 4, "date_premier_achat": 4, "revenu_annuel": 4, "client": 2},
        "inventory": {"stock_final": 5, "prix_achat": 4},
        "finance": {"montant_entree": 5, "montant_sortie": 5, "date": 2},
        "products": {"produit": 5, "prix_unitaire": 4, "categorie": 4},
        "geography": {"region": 5, "pays": 4, "ville": 3},
    }

    AGGREGATION_SUGGESTIONS = {
        "montant_total": "sum",
        "montant_entree": "sum",
        "montant_sortie": "sum",
        "revenu_annuel": "mean",
        "prix_unitaire": "mean",
        "prix_achat": "mean",
        "stock_final": "sum",
        "quantite": "sum",
    }

    def _normalize_column_name(self, name: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(name))
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = normalized.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    def _latest_validated_job(self, source: DataSource) -> CleaningJob | None:
        jobs = (
            CleaningJob.objects.filter(source=source, status="completed")
            .prefetch_related("cleaned_results")
            .order_by("-completed_at", "-created_at")
        )
        for job in jobs:
            total = job.cleaned_results.count()
            if total and job.cleaned_results.filter(is_validated=True).count() == total:
                return job
        return None

    def _load_validated_frame(self, source: DataSource) -> tuple[pd.DataFrame, CleaningJob | None]:
        # Check if source has sheet relations → use joined view
        if source.sheet_relations.filter(is_active=True).exists():
            from apps.ingestion.services import build_joined_view
            result = build_joined_view(source)
            rows = result.get('rows', [])
            frame = pd.DataFrame(rows)
            if frame.empty:
                raise ValueError("Aucune donnée jointe n'est disponible pour cette source.")
            return frame, None

        job = self._latest_validated_job(source)
        if job is None:
            raise ValueError("Cette source ne possède pas de nettoyage validé exploitable pour M4.")

        rows = list(
            job.cleaned_results.filter(is_validated=True)
            .order_by("original_data__row_number", "id")
            .values_list("data", flat=True)
        )
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise ValueError("Aucune donnée validée n'est disponible pour cette source.")
        return frame, job

    def _apply_aliases(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        rename_map = {column: self._normalize_column_name(column) for column in working.columns}
        working = working.rename(columns=rename_map)
        for target, aliases in self.COLUMN_ALIASES.items():
            if target in working.columns:
                continue
            for alias in aliases:
                normalized_alias = self._normalize_column_name(alias)
                if normalized_alias in working.columns:
                    working[target] = working[normalized_alias]
                    break
        return working

    def _prepare_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = self._apply_aliases(frame)
        for column in ("date", "date_naissance", "date_premier_achat"):
            if column in working.columns:
                working[column] = pd.to_datetime(working[column], errors="coerce")
        for column in ("montant_total", "stock_final", "prix_achat", "revenu_annuel", "montant_entree", "montant_sortie", "quantite", "prix_unitaire"):
            if column in working.columns:
                working[column] = pd.to_numeric(working[column], errors="coerce")
        return working

    def _detect_domain_profile(self, frame: pd.DataFrame) -> dict[str, Any]:
        columns = set(frame.columns)
        scores: dict[str, int] = {}
        matched_signals: dict[str, list[str]] = {}

        for domain, weighted_signals in self.DOMAIN_SIGNAL_WEIGHTS.items():
            matched = [signal for signal in weighted_signals if signal in columns]
            matched_signals[domain] = matched
            scores[domain] = sum(weighted_signals[signal] for signal in matched)

        best_domain = "generic"
        best_score = 0
        for domain, score in scores.items():
            if score > best_score:
                best_domain = domain
                best_score = score

        confidence = "faible"
        if best_score >= 10:
            confidence = "forte"
        elif best_score >= 6:
            confidence = "moyenne"

        if best_score < 4:
            best_domain = "generic"
            confidence = "faible"

        return {
            "domain": best_domain,
            "scores": scores,
            "matched_signals": matched_signals,
            "confidence": confidence,
        }

    def _classify_columns(self, frame: pd.DataFrame) -> dict[str, list[ColumnSuggestion]]:
        numeric_cols: list[ColumnSuggestion] = []
        categorical_cols: list[ColumnSuggestion] = []
        date_cols: list[ColumnSuggestion] = []
        id_cols: list[ColumnSuggestion] = []

        for column in frame.columns:
            series = frame[column].dropna()
            total = len(frame)
            null_ratio = 1 - (len(series) / total) if total > 0 else 0
            unique_ratio = series.nunique() / len(series) if len(series) > 0 else 0
            samples = series.head(3).to_list()

            if column in ("date", "date_naissance", "date_premier_achat") or (
                "date" in column and pd.api.types.is_datetime64_any_dtype(series)
            ):
                date_cols.append(ColumnSuggestion(
                    column=column, dtype="date",
                    samples=[str(s) for s in samples],
                    null_ratio=round(null_ratio, 4),
                    unique_ratio=round(unique_ratio, 4),
                ))
            elif pd.api.types.is_numeric_dtype(series):
                numeric_cols.append(ColumnSuggestion(
                    column=column, dtype="numeric",
                    samples=samples,
                    null_ratio=round(null_ratio, 4),
                    unique_ratio=round(unique_ratio, 4),
                ))
            elif self._is_numeric_like(series):
                numeric_cols.append(ColumnSuggestion(
                    column=column, dtype="numeric",
                    samples=samples,
                    null_ratio=round(null_ratio, 4),
                    unique_ratio=round(unique_ratio, 4),
                ))
            elif column in ("client_id", "id_commande", "id") or column.endswith("_id"):
                id_cols.append(ColumnSuggestion(
                    column=column, dtype="id",
                    samples=samples,
                    null_ratio=round(null_ratio, 4),
                    unique_ratio=round(unique_ratio, 4),
                ))
            else:
                categorical_cols.append(ColumnSuggestion(
                    column=column, dtype="categorical",
                    samples=samples,
                    null_ratio=round(null_ratio, 4),
                    unique_ratio=round(unique_ratio, 4),
                ))

        return {
            "numeric": numeric_cols,
            "categorical": categorical_cols,
            "date": date_cols,
            "id": id_cols,
        }

    def _is_numeric_like(self, series: pd.Series) -> bool:
        """Detect columns whose values look numeric even if stored as strings.

        Handles plain floats stored as strings ('14122.61'), comma as decimal
        separator ('1 234,56') and comma as thousands separator ('17,524.02').
        """
        if len(series) == 0:
            return False
        non_null = series.dropna()
        if len(non_null) == 0:
            return False
        text = non_null.astype(str).str.strip()
        if text.str.len().eq(0).mean() > 0.5:
            return False

        strategies = ["identity", "comma_to_dot", "comma_thousands"]
        compact = text.map(lambda v: re.sub(r"[\s\u00a0\u202f]+", "", v).strip())
        for strategy in strategies:
            if strategy == "identity":
                variants = compact
            elif strategy == "comma_to_dot":
                variants = compact.str.replace(",", ".")
            else:
                variants = compact.str.replace(",", "", regex=False)
            converted = pd.to_numeric(variants, errors="coerce")
            if converted.notna().mean() >= 0.9:
                return True
        return False

    def _suggest_metrics(self, columns: dict[str, list[ColumnSuggestion]], domain: str) -> list[MetricSuggestion]:
        suggestions: list[MetricSuggestion] = []

        for col in columns["numeric"]:
            preferred_agg = self.AGGREGATION_SUGGESTIONS.get(col.column, "sum")

            agg_labels = {
                "sum": "Total",
                "mean": "Moyenne",
                "count": "Nombre",
            }
            agg_label = agg_labels.get(preferred_agg, preferred_agg.upper())

            suggestions.append(MetricSuggestion(
                label=f"{agg_label} - {col.column}",
                measure_column=col.column,
                aggregation=preferred_agg,
                description=f"Calculer le {agg_label.lower()} de {col.column}",
            ))

        if columns["date"]:
            use_date_col = columns["date"][0].column
            for col in columns["numeric"]:
                preferred_agg = self.AGGREGATION_SUGGESTIONS.get(col.column, "sum")
                suggestions.append(MetricSuggestion(
                    label=f"{col.column} par mois",
                    measure_column=col.column,
                    aggregation=preferred_agg,
                    description=f"Évolution mensuelle de {col.column}",
                ))

        return suggestions

    def detect_and_suggest(self, *, source: DataSource) -> dict[str, Any]:
        frame, _ = self._load_validated_frame(source)
        prepared = self._prepare_frame(frame)
        domain_profile = self._detect_domain_profile(prepared)

        columns = self._classify_columns(prepared)
        suggestions = self._suggest_metrics(columns, domain_profile["domain"])

        return {
            "source_id": source.id,
            "source_name": source.name,
            "domain_profile": domain_profile,
            "columns": {
                "numeric": [self._col_to_dict(c) for c in columns["numeric"]],
                "categorical": [self._col_to_dict(c) for c in columns["categorical"]],
                "date": [self._col_to_dict(c) for c in columns["date"]],
                "id": [self._col_to_dict(c) for c in columns["id"]],
            },
            "suggestions": [
                {"label": s.label, "measure_column": s.measure_column, "aggregation": s.aggregation, "description": s.description}
                for s in suggestions
            ],
            "period_label": date.today().strftime("%B %Y"),
        }

    def _col_to_dict(self, col: ColumnSuggestion) -> dict[str, Any]:
        return {
            "name": col.column,
            "type": col.dtype,
            "samples": col.samples,
            "null_ratio": col.null_ratio,
            "unique_ratio": col.unique_ratio,
        }
