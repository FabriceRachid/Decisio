from __future__ import annotations

import re

import pandas as pd

from .report import CleaningReport

try:
    from babel.numbers import format_currency
except Exception:  # pragma: no cover - optional dependency
    format_currency = None


def _skip_amount_normalization(report: CleaningReport) -> bool:
    for item in report.metadata.get('decision_overrides', []) or []:
        if not isinstance(item, dict):
            continue
        if item.get('action') == 'normalize_amounts' and item.get('decision') in {'keep', 'review'}:
            return True
    return False


class MontantCleaner:
    CURRENCY_PATTERN = re.compile(r'(fcfa|f\s*cfa|xof|eur|usd|gbp|€|\$|£)', re.IGNORECASE)
    NON_NEGATIVE_FIELDS = {'montant_total', 'prix_unitaire', 'quantite', 'stock_initial', 'stock_final'}
    DEFAULT_XOF_RATES = {
        'EUR': 655.957,
        'USD': 600.0,
        'GBP': 770.0,
        'GHS': 52.0,
        'NGN': 0.42,
        'XAF': 1.0,
        'GNF': 0.069,
    }

    def clean(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict], source=None) -> pd.DataFrame:
        if _skip_amount_normalization(report):
            return dataframe.copy()
        working = dataframe.copy()
        amount_fields = {'montant_total', 'prix_unitaire', 'remise', 'tva', 'montant_ht', 'montant_ttc', 'quantite', 'stock_initial', 'stock_final'}
        amount_columns = [column for column, meta in mapped_fields.items() if meta.get('standard') in amount_fields and column in working.columns]
        source_metadata = getattr(source, 'metadata', {}) or {}
        auto_convert_to_xof = bool(source_metadata.get('auto_convert_currency_to_xof'))
        conversion_rates = self._normalized_rates(source_metadata.get('xof_conversion_rates', self.DEFAULT_XOF_RATES))
        if auto_convert_to_xof:
            report.metadata['conversion_xof'] = {
                'activee': True,
                'devise_cible': 'XOF',
                'taux': conversion_rates,
            }

        for column in amount_columns:
            original = working[column].copy()
            parsed_info = working[column].apply(self._parse_amount)
            converted = parsed_info.apply(
                lambda item: self._convert_to_xof(item, conversion_rates) if auto_convert_to_xof else item['value']
            )
            converted = converted.apply(self._normalize_fcfa_value)
            changed_mask = original.astype('string') != converted.astype('string')
            if bool(changed_mask.fillna(False).any()):
                examples = []
                for index in working.index[changed_mask.fillna(False)][:3]:
                    examples.append({'avant': original.loc[index], 'apres': converted.loc[index], 'ligne': int(working.loc[index, '_row_number'])})
                report.add_correction(
                    regle='R10',
                    description=f'Normalisation des montants de la colonne {column}',
                    nombre=int(changed_mask.fillna(False).sum()),
                    exemples=examples,
                )
            non_convertible_rows = working.loc[
                parsed_info.apply(lambda item: item.get('value') is None and item.get('raw') not in (None, '')),
                '_row_number',
            ].astype(int).tolist()
            if non_convertible_rows:
                report.add_alert(
                    regle='R10',
                    severite='MOYEN',
                    message=f"Certaines valeurs de la colonne '{column}' n'ont pas pu être converties.",
                    lignes=non_convertible_rows[:10],
                )
            currencies = sorted({item['currency'] for item in parsed_info if item['currency'] not in (None, 'XOF')})
            if currencies:
                message = f"Des devises étrangères ont été détectées dans la colonne '{column}' : {', '.join(currencies)}."
                if auto_convert_to_xof:
                    message += ' Conversion automatique vers XOF appliquée.'
                report.add_alert(
                    regle='R22',
                    severite='INFO',
                    message=message,
                )
                report.metadata.setdefault('devises_detectees', {})[column] = currencies
                if auto_convert_to_xof:
                    report.metadata.setdefault('conversions_effectuees', {})[column] = [
                        {
                            'devise': currency,
                            'taux_xof': conversion_rates.get(currency),
                        }
                        for currency in currencies
                        if conversion_rates.get(currency) is not None
                    ]
            standard_field = mapped_fields[column].get('standard')
            numeric_converted = pd.to_numeric(converted, errors='coerce')
            if standard_field in self.NON_NEGATIVE_FIELDS:
                negative_rows = working.loc[(numeric_converted < 0).fillna(False), '_row_number'].astype(int).tolist()
                if negative_rows:
                    report.add_alert(
                        regle='R12',
                        severite='CRITIQUE',
                        message=f"Des valeurs négatives ont été détectées dans la colonne '{column}'.",
                        lignes=negative_rows[:10],
                    )
            if standard_field == 'montant_total':
                zero_rows = working.loc[(numeric_converted == 0).fillna(False), '_row_number'].astype(int).tolist()
                if zero_rows:
                    report.add_alert(
                        regle='R12',
                        severite='MOYEN',
                        message=f"Des montants totaux nuls ont été détectés dans la colonne '{column}'.",
                        lignes=zero_rows[:10],
                    )
            if numeric_converted.notna().sum() >= 3:
                median = float(numeric_converted.dropna().median())
                if median > 0:
                    ratio = (numeric_converted / median).abs()
                    outlier_rows = working.loc[((ratio > 10) | ((ratio < 0.1) & (numeric_converted > 0))).fillna(False), '_row_number'].astype(int).tolist()
                    if outlier_rows:
                        report.add_alert(
                            regle='R13',
                            severite='MOYEN',
                            message=f"Des montants possiblement mal échelonnés ont été détectés dans la colonne '{column}'.",
                            lignes=outlier_rows[:10],
                        )
            working[column] = converted
        self._fill_montant_total_if_possible(working, report, mapped_fields)
        return working

    def _parse_amount(self, value):
        if value in (None, ''):
            return {'value': None, 'currency': None, 'raw': value}
        if isinstance(value, (int, float)):
            return {'value': float(value), 'currency': 'XOF', 'raw': value}

        text = str(value).strip()
        original_text = text
        negative = text.startswith('(') and text.endswith(')')
        text = text.strip('()')
        detected_currencies = re.findall(self.CURRENCY_PATTERN, text)
        currency = detected_currencies[0].upper().replace(' ', '') if detected_currencies else 'XOF'
        text = self.CURRENCY_PATTERN.sub('', text)
        text = text.replace('\xa0', ' ').strip()
        multiplier = 1
        compact = text.replace(' ', '')
        suffix_match = re.search(r'(?i)(m|mn|million|mds|md|b|bn|milliard)$', compact)
        if suffix_match:
            suffix = suffix_match.group(1).lower()
            compact = re.sub(r'(?i)(m|mn|million|mds|md|b|bn|milliard)$', '', compact)
            if suffix in {'m', 'mn', 'million'}:
                multiplier = 1_000_000
            elif suffix in {'mds', 'md', 'b', 'bn', 'milliard'}:
                multiplier = 1_000_000_000
        text = compact

        if ',' in text and '.' in text:
            if text.rfind(',') > text.rfind('.'):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            if text.count(',') > 1:
                text = text.replace(',', '')
            else:
                text = text.replace('.', '').replace(',', '.')
        elif text.count('.') > 1:
            text = text.replace('.', '')

        try:
            amount = float(text) * multiplier
            return {'value': -amount if negative else amount, 'currency': currency, 'raw': original_text}
        except ValueError:
            return {'value': None, 'currency': None, 'raw': original_text}

    def _fill_montant_total_if_possible(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict]) -> None:
        reverse_mapping = {meta['standard']: column for column, meta in mapped_fields.items()}
        required = {'montant_total', 'quantite', 'prix_unitaire'}
        if not required.issubset(reverse_mapping):
            return

        amount_col = reverse_mapping['montant_total']
        qty_col = reverse_mapping['quantite']
        unit_col = reverse_mapping['prix_unitaire']
        amount = pd.to_numeric(dataframe[amount_col], errors='coerce')
        qty = pd.to_numeric(dataframe[qty_col], errors='coerce')
        unit = pd.to_numeric(dataframe[unit_col], errors='coerce')
        fill_mask = amount.isna() & qty.notna() & unit.notna()
        if not bool(fill_mask.any()):
            return
        dataframe.loc[fill_mask, amount_col] = (qty * unit)[fill_mask].round(4)
        examples = []
        for index in dataframe.index[fill_mask][:3]:
            examples.append({'avant': None, 'apres': dataframe.at[index, amount_col]})
        report.add_correction(
            regle='R11',
            description=f"Calcul automatique de {amount_col} depuis quantité × prix unitaire",
            nombre=int(fill_mask.sum()),
            exemples=examples,
        )

    def _convert_to_xof(self, parsed_item: dict, conversion_rates: dict) -> object:
        value = parsed_item['value']
        currency = parsed_item['currency']
        if currency in (None, 'XOF') or not isinstance(value, (int, float)):
            return value
        rate = conversion_rates.get(currency)
        if rate is None:
            return value
        converted = round(float(value) * float(rate))
        return converted

    def _normalize_fcfa_value(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if pd.isna(value):
                return None
            return int(round(float(value)))
        return value

    def _normalized_rates(self, conversion_rates: dict) -> dict[str, float]:
        normalized = {}
        for currency, rate in (conversion_rates or {}).items():
            try:
                normalized[str(currency).upper()] = float(rate)
            except (TypeError, ValueError):
                continue
        return normalized or self.DEFAULT_XOF_RATES.copy()
