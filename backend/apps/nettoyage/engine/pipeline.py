from __future__ import annotations

import pandas as pd

from .coherence_checker import CoherenceChecker
from .context_checker import ContextChecker
from .date_cleaner import DateCleaner
from .loader_service import LoaderService
from .mapping_service import MappingService
from .ml_cleaner import MLCleaner
from .montant_cleaner import MontantCleaner
from .quality_scorer import QualityScorer
from .report import CleaningReport
from .structural_cleaner import StructuralCleaner
from .text_cleaner import TextCleaner


class NettoyagePipeline:
    def __init__(self, *, source, user_id: int | None = None):
        self.source = source
        self.user_id = user_id
        self.loader = LoaderService()
        self.mapper = MappingService()
        self.ml_cleaner = MLCleaner()
        self.structural = StructuralCleaner()
        self.date_cleaner = DateCleaner()
        self.montant_cleaner = MontantCleaner()
        self.text_cleaner = TextCleaner()
        self.coherence_checker = CoherenceChecker()
        self.context_checker = ContextChecker()
        self.quality_scorer = QualityScorer()

    def analyze_source(self, *, decision_overrides: list[dict] | None = None) -> tuple[pd.DataFrame, dict]:
        report = self._new_report(
            row_count=self.source.row_count or 0,
            column_count=self.source.column_count or 0,
            decision_overrides=decision_overrides,
        )
        dataframe = self.loader.load_from_source(self.source, report)
        if not report.lignes_initiales:
            report.lignes_initiales = len(dataframe)
        if not report.colonnes_initiales:
            report.colonnes_initiales = len([column for column in dataframe.columns if column != '_row_number'])
        return self.run_dataframe(dataframe, report=report)

    def analyze_prepared_dataframe(
        self,
        dataframe: pd.DataFrame,
        *,
        decision_overrides: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> tuple[pd.DataFrame, dict]:
        report = self._new_report(
            row_count=len(dataframe),
            column_count=len([column for column in dataframe.columns if column != '_row_number']),
            decision_overrides=decision_overrides,
        )
        if metadata:
            report.metadata.update(metadata)
        return self.run_dataframe(dataframe, report=report)

    def run_dataframe(self, dataframe: pd.DataFrame, report: CleaningReport | None = None) -> tuple[pd.DataFrame, dict]:
        report = report or self._new_report(
            row_count=len(dataframe),
            column_count=len([column for column in dataframe.columns if column != '_row_number']),
        )

        working = dataframe.copy()
        report.metadata.setdefault('integrations', {})
        working = self.ml_cleaner.clean(working, report)
        mapping = self.mapper.map(working, report)
        working = self.structural.clean(working, report, mapping)
        working = self.date_cleaner.clean(working, report, mapping)
        working = self.montant_cleaner.clean(working, report, mapping, source=self.source)
        working = self.text_cleaner.clean(working, report, mapping)
        working = self.coherence_checker.check(working, report, mapping)
        self.context_checker.check(working, report, self.source, mapping)
        report.metadata.setdefault(
            'reversibilite',
            {
                'rollback_disponible': True,
                'source_brute_preservee': True,
                'source_id': str(self.source.id),
                'mode': 'relecture_depuis_donnees_brutes',
            },
        )
        score, score_detail = self.quality_scorer.compute(working, report)
        report.finalize(
            lignes_finales=len(working),
            colonnes_finales=len([column for column in working.columns if column != '_row_number']),
            score_qualite=score,
            score_detail=score_detail,
        )
        return working, report.to_dict()

    def _new_report(self, *, row_count: int, column_count: int, decision_overrides: list[dict] | None = None) -> CleaningReport:
        return CleaningReport(
            fichier_id=str(self.source.id),
            nom_fichier=self.source.name,
            lignes_initiales=row_count,
            colonnes_initiales=column_count,
            metadata={
                'hash_md5': getattr(self.source, 'checksum_md5', None),
                'user_id': str(self.user_id) if self.user_id is not None else None,
                'decision_overrides': decision_overrides or [],
            },
        )
