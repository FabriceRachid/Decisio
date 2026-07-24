from __future__ import annotations

import pandas as pd  # pyright: ignore[reportMissingModuleSource]
from importlib import import_module
import logging

from .report import CleaningReport

logger = logging.getLogger(__name__)

try:
    babel_numbers = import_module('babel.numbers')
    format_currency = getattr(babel_numbers, 'format_currency', None)
except Exception:  # pragma: no cover - optional dependency
    format_currency = None
    logger.debug('Optional dependency babel.numbers is unavailable; FCFA formatting fallback is enabled.')


class ContextChecker:
    FCFA_THRESHOLDS = {
        'prix_unitaire': {'min': 50, 'max': 5_000_000},
        'montant_total': {'max': 500_000_000},
        'quantite': {'max': 10_000},
    }

    def check(self, dataframe, report: CleaningReport, source, mapped_fields: dict[str, dict]) -> None:
        if source.checksum_md5:
            report.metadata['checksum_md5'] = source.checksum_md5
            duplicates = source.__class__.objects.filter(checksum_md5=source.checksum_md5).exclude(id=source.id)
            if duplicates.exists():
                last_duplicate = duplicates.order_by('-created_at').first()
                report.add_alert(
                    regle='R25',
                    severite='INFO',
                    message=f"Un fichier identique a déjà été importé le {last_duplicate.created_at.strftime('%d/%m/%Y à %H:%M')}.",
                )
        if source.parent_source_id:
            report.add_alert(
                regle='R25',
                severite='INFO',
                message='Cette source est une version dérivée d’un import antérieur.',
            )
        self._check_fcfa_ranges(dataframe, report, mapped_fields)

    def _check_fcfa_ranges(self, dataframe, report: CleaningReport, mapped_fields: dict[str, dict]) -> None:
        reverse_mapping = {meta['standard']: column for column, meta in mapped_fields.items()}
        for standard_field, thresholds in self.FCFA_THRESHOLDS.items():
            column = reverse_mapping.get(standard_field)
            if not column or column not in dataframe.columns:
                continue
            values = pd.to_numeric(dataframe[column], errors='coerce')
            too_low_rows = []
            too_high_rows = []
            if 'min' in thresholds:
                too_low_rows = dataframe.loc[(values < thresholds['min']).fillna(False), '_row_number'].astype(int).tolist()
            if 'max' in thresholds:
                too_high_rows = dataframe.loc[(values > thresholds['max']).fillna(False), '_row_number'].astype(int).tolist()

            if too_low_rows:
                report.add_alert(
                    regle='R23',
                    severite='MOYEN',
                    message=(
                        f"Des valeurs de '{standard_field}' sont inférieures au seuil FCFA attendu "
                        f"({self._format_xof(thresholds['min'])})."
                    ),
                    lignes=too_low_rows[:10],
                )
            if too_high_rows:
                report.add_alert(
                    regle='R23',
                    severite='MOYEN',
                    message=(
                        f"Des valeurs de '{standard_field}' dépassent le seuil FCFA attendu "
                        f"({self._format_xof(thresholds['max'])})."
                    ),
                    lignes=too_high_rows[:10],
                )

    def _format_xof(self, value: int | float) -> str:
        if value is None:
            return '0 XOF'
        if format_currency is not None:
            try:
                return format_currency(value, 'XOF', locale='fr_FR')
            except Exception:
                logger.debug('Currency formatter failed, fallback FCFA formatting applied.', exc_info=True)
        return f"{int(value):,}".replace(',', ' ') + ' FCFA'
