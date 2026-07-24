from __future__ import annotations

import re

import pandas as pd
from django.utils import timezone

from .report import CleaningReport

try:
    import dateparser
except Exception:  # pragma: no cover - optional dependency
    dateparser = None


def _skip_date_normalization(report: CleaningReport) -> bool:
    for item in report.metadata.get('decision_overrides', []) or []:
        if not isinstance(item, dict):
            continue
        if item.get('action') == 'normalize_dates' and item.get('decision') in {'keep', 'review'}:
            return True
    return False


class DateCleaner:
    EXCEL_SERIAL_MIN = 1000
    EXCEL_SERIAL_MAX = 100000
    MINIMUM_DATE = pd.Timestamp('2000-01-01')
    MONTH_LOOKUP = {
        'janvier': 1,
        'january': 1,
        'jan': 1,
        'fevrier': 2,
        'février': 2,
        'february': 2,
        'feb': 2,
        'mars': 3,
        'march': 3,
        'avr': 4,
        'avril': 4,
        'april': 4,
        'mai': 5,
        'may': 5,
        'juin': 6,
        'june': 6,
        'juillet': 7,
        'july': 7,
        'aout': 8,
        'août': 8,
        'august': 8,
        'aug': 8,
        'septembre': 9,
        'september': 9,
        'sep': 9,
        'octobre': 10,
        'october': 10,
        'oct': 10,
        'novembre': 11,
        'november': 11,
        'nov': 11,
        'decembre': 12,
        'décembre': 12,
        'december': 12,
        'dec': 12,
    }

    def clean(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict]) -> pd.DataFrame:
        if _skip_date_normalization(report):
            return dataframe.copy()
        working = dataframe.copy()
        date_columns = [column for column, meta in mapped_fields.items() if str(meta.get('standard', '')).startswith('date') and column in working.columns]
        future_limit = pd.Timestamp(timezone.now().date()) + pd.Timedelta(days=365)
        for column in date_columns:
            original = working[column].copy()
            converted = working[column].apply(self._parse_date_value)
            converted_dt = pd.to_datetime(converted, errors='coerce')
            changed_mask = original.astype('string') != converted.astype('string')
            invalid_mask = original.notna() & converted.isna()
            impossible_rows = working.loc[invalid_mask, '_row_number'].astype(int).tolist()
            if impossible_rows:
                report.add_alert(
                    regle='R07',
                    severite='MOYEN',
                    message=f"Certaines dates de la colonne '{column}' sont invalides ou impossibles.",
                    lignes=impossible_rows[:10],
                )
            is_delivery_column = str(mapped_fields[column].get('standard')) == 'date_livraison'
            future_rows = working.loc[(converted_dt > future_limit).fillna(False), '_row_number'].astype(int).tolist()
            if future_rows and not is_delivery_column:
                report.add_alert(
                    regle='R08',
                    severite='MOYEN',
                    message=f"Des dates futures suspectes ont été détectées dans la colonne '{column}'.",
                    lignes=future_rows[:10],
                )
            too_old_rows = working.loc[(converted_dt < self.MINIMUM_DATE).fillna(False), '_row_number'].astype(int).tolist()
            if too_old_rows:
                report.add_alert(
                    regle='R07',
                    severite='MOYEN',
                    message=f"Des dates anormalement anciennes ont été détectées dans la colonne '{column}'.",
                    lignes=too_old_rows[:10],
                )

            if str(mapped_fields[column].get('standard')) == 'date' and converted_dt.notna().sum() >= 2:
                missing_rows = working.loc[converted_dt.isna() & original.notna() & original.astype('string').str.strip().ne(''), '_row_number'].astype(int).tolist()
                if missing_rows:
                    report.add_alert(
                        regle='R09',
                        severite='INFO',
                        message=f"Des dates n'ont pas pu être normalisées dans la colonne '{column}' et restent à vérifier.",
                        lignes=missing_rows[:10],
                    )
            if bool(changed_mask.fillna(False).any()):
                examples = []
                for index in working.index[changed_mask.fillna(False)][:3]:
                    examples.append({'avant': original.loc[index], 'apres': converted.loc[index], 'ligne': int(working.loc[index, '_row_number'])})
                report.add_correction(
                    regle='R06',
                    description=f'Normalisation des dates de la colonne {column}',
                    nombre=int(changed_mask.fillna(False).sum()),
                    exemples=examples,
                )
            converted = converted.astype(object)
            converted = converted.where(pd.notna(converted), None)
            working[column] = converted
        self._check_date_sequences(working, report, mapped_fields)
        return working

    def _parse_date_value(self, value):
        if value in (None, ''):
            return None
        text_value = str(value).strip()
        if text_value == '':
            return None
        text_value = re.sub(r'\b1er\b', '1', text_value, flags=re.IGNORECASE)
        excel_serial = self._parse_excel_serial(value)
        if excel_serial is not None:
            return excel_serial

        parsed = pd.to_datetime(text_value, errors='coerce', dayfirst=True, format='mixed')
        if pd.notna(parsed):
            return parsed.date().isoformat()

        if dateparser is not None:
            parsed_alt = dateparser.parse(
                text_value,
                settings={'DATE_ORDER': 'DMY', 'PREFER_DAY_OF_MONTH': 'first'},
                languages=['fr', 'en'],
            )
            if parsed_alt is not None:
                return parsed_alt.date().isoformat()

        manual = self._parse_with_manual_patterns(text_value)
        if manual is not None:
            return manual
        return None

    def _parse_excel_serial(self, value) -> str | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            serial = float(value)
            if serial.is_integer() and self.EXCEL_SERIAL_MIN <= serial <= self.EXCEL_SERIAL_MAX:
                return (pd.Timestamp('1899-12-30') + pd.to_timedelta(serial, unit='D')).date().isoformat()

        text_value = str(value).strip()
        if re.fullmatch(r'\d{4,6}', text_value):
            serial = float(text_value)
            if self.EXCEL_SERIAL_MIN <= serial <= self.EXCEL_SERIAL_MAX:
                return (pd.Timestamp('1899-12-30') + pd.to_timedelta(serial, unit='D')).date().isoformat()
        return None

    def _parse_with_manual_patterns(self, value: str) -> str | None:
        compact_match = re.fullmatch(r'(\d{4})(\d{2})(\d{2})', value)
        if compact_match:
            year, month, day = compact_match.groups()
            return self._safe_iso_date(int(year), int(month), int(day))

        dmy_match = re.fullmatch(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})', value)
        if dmy_match:
            day, month, year = dmy_match.groups()
            year_value = int(year)
            if len(year) == 2:
                year_value = 1900 + year_value if year_value >= 50 else 2000 + year_value
            return self._safe_iso_date(year_value, int(month), int(day))

        ymd_match = re.fullmatch(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', value)
        if ymd_match:
            year, month, day = ymd_match.groups()
            return self._safe_iso_date(int(year), int(month), int(day))

        literal_match = re.fullmatch(r'(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{2,4})', value.strip(), flags=re.IGNORECASE)
        if literal_match:
            day, month_label, year = literal_match.groups()
            normalized_month = month_label.strip().lower()
            month = self.MONTH_LOOKUP.get(normalized_month)
            if month is not None:
                year_value = int(year)
                if len(year) == 2:
                    year_value = 1900 + year_value if year_value >= 50 else 2000 + year_value
                return self._safe_iso_date(year_value, month, int(day))
        return None

    def _safe_iso_date(self, year: int, month: int, day: int) -> str | None:
        try:
            return pd.Timestamp(year=year, month=month, day=day).date().isoformat()
        except Exception:
            return None

    def _check_date_sequences(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict]) -> None:
        reverse_mapping = {meta['standard']: column for column, meta in mapped_fields.items()}

        if {'date_commande', 'date_livraison'}.issubset(reverse_mapping):
            order_col = reverse_mapping['date_commande']
            delivery_col = reverse_mapping['date_livraison']
            order_dates = pd.to_datetime(dataframe[order_col], errors='coerce')
            delivery_dates = pd.to_datetime(dataframe[delivery_col], errors='coerce')
            invalid = dataframe.loc[(delivery_dates < order_dates).fillna(False), '_row_number'].astype(int).tolist()
            if invalid:
                report.add_alert(
                    regle='R19',
                    severite='MOYEN',
                    message='Des dates de livraison anterieures aux dates de commande ont ete detectees.',
                    lignes=invalid[:10],
                )

        if {'date_paiement', 'date_commande'}.issubset(reverse_mapping):
            payment_col = reverse_mapping['date_paiement']
            reference_col = reverse_mapping['date_commande']
            payment_dates = pd.to_datetime(dataframe[payment_col], errors='coerce')
            reference_dates = pd.to_datetime(dataframe[reference_col], errors='coerce')
            invalid = dataframe.loc[(payment_dates < reference_dates).fillna(False), '_row_number'].astype(int).tolist()
            if invalid:
                report.add_alert(
                    regle='R19',
                    severite='MOYEN',
                    message='Des dates de paiement anterieures aux dates de reference ont ete detectees.',
                    lignes=invalid[:10],
                )
