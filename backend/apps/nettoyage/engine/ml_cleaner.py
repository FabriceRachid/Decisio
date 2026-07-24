from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from typing import Any

import pandas as pd

from .report import CleaningReport


class MLCleaner:
    """
    Lightweight optional profiling layer for MVP.

    It never becomes mandatory for the cleaning pipeline:
    - if optional libraries are installed, enrich the report
    - if they are absent or fail to load, the deterministic pipeline still runs
    """

    def __init__(self) -> None:
        self._availability = {
            'cleanlab': find_spec('cleanlab') is not None,
            'klib': find_spec('klib') is not None,
            'dataprep_ai': find_spec('dataprep_ai') is not None,
        }

    def clean(self, dataframe: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        data_columns = [column for column in dataframe.columns if column != '_row_number']
        summary = self._build_summary(dataframe, data_columns)
        libraries = {
            name: {
                'available': available,
                'version': self._safe_version(name),
            }
            for name, available in self._availability.items()
        }

        report.metadata.setdefault('integrations', {})
        report.metadata['integrations']['profilage_auto'] = {
            'active': any(self._availability.values()),
            'libraries': libraries,
            'summary': summary,
            'issues': self._detect_issues(dataframe, data_columns),
        }
        report.metadata['couche_1_ml'] = {
            'cleanlab': {
                'active': self._availability['cleanlab'],
                'lignes_analysees': len(dataframe),
            },
            'klib': {
                'active': self._availability['klib'],
                'doublons_detectes': summary['duplicate_rows'],
            },
            'dataprep': {
                'active': self._availability['dataprep_ai'],
                'colonnes_profilees': len(data_columns),
            },
        }
        return dataframe

    def _build_summary(self, dataframe: pd.DataFrame, data_columns: list[str]) -> dict[str, Any]:
        duplicate_rows = int(dataframe.duplicated(subset=data_columns, keep='first').sum()) if data_columns else 0
        missing_cells = 0
        if data_columns:
            for column in data_columns:
                missing_cells += int(dataframe[column].isna().sum())
                missing_cells += int(
                    dataframe[column]
                    .astype(str)
                    .str.strip()
                    .eq('')
                    .sum()
                )
        total_cells = max(len(dataframe) * max(len(data_columns), 1), 1)
        return {
            'rows': len(dataframe),
            'columns': len(data_columns),
            'duplicate_rows': duplicate_rows,
            'missing_value_rate': round(missing_cells / total_cells, 4),
        }

    def _detect_issues(self, dataframe: pd.DataFrame, data_columns: list[str]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not data_columns:
            return issues

        duplicate_mask = dataframe.duplicated(subset=data_columns, keep='first')
        duplicate_rows = dataframe.loc[duplicate_mask, '_row_number'].astype(int).tolist() if '_row_number' in dataframe.columns else []
        if duplicate_rows:
            issues.append(
                {
                    'source': 'klib',
                    'type': 'duplicate_rows',
                    'message': 'Des doublons exacts ont été détectés dans le jeu de données.',
                    'rows': duplicate_rows[:10],
                }
            )

        for column in data_columns:
            series = dataframe[column]
            missing_rate = float(series.isna().mean()) if len(series) else 0.0
            if series.dtype == object:
                missing_rate = max(
                    missing_rate,
                    float(series.astype(str).str.strip().eq('').mean()) if len(series) else 0.0,
                )
            if missing_rate >= 0.2:
                issues.append(
                    {
                        'source': 'dataprep_ai' if self._availability['dataprep_ai'] else 'profilage_auto',
                        'type': 'high_missing_rate',
                        'column': column,
                        'message': f"La colonne '{column}' a un taux de valeurs manquantes élevé ({round(missing_rate * 100, 2)}%).",
                        'rows': [],
                    }
                )
        return issues

    def _safe_version(self, package_name: str) -> str | None:
        if not self._availability.get(package_name):
            return None
        try:
            return version(package_name)
        except PackageNotFoundError:
            return None
        except Exception:
            return None
