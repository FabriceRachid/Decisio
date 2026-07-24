from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd

from .report import CleaningReport

try:
    from thefuzz import fuzz
except Exception:  # pragma: no cover - optional dependency
    fuzz = None

SENTINELS = {
    'n/a', 'na', 'n.a.', '#n/a', '#ref!', '#valeur!', 'null', 'none', 'nil', '—', '-', '--', '...', '.',
    'à compléter', 'inconnu', 'unknown', '???', 'xxx', 'xxxxx', 'non renseigné', 'vide', 'empty', 'test', 'exemple',
}
LOWERCASE_WORDS = {'de', 'du', 'la', 'le', 'les', 'et', 'au', 'aux', 'à', 'en', 'pour'}
KNOWN_ACRONYMS = {'FCFA', 'BF', 'PME', 'ERP', 'SA', 'SARL', 'SAS', 'UEMOA'}
LOCAL_NAME_SUFFIXES = {'ouedraogo', 'ouédraogo', 'konate', 'konaté', 'sawadogo', 'traore', 'traoré', 'compaore', 'compaoré', 'diallo', 'coulibaly', 'diabate', 'diabaté', 'bamba', 'toure', 'touré', 'sylla', 'barry'}


def _skip_text_normalization(report: CleaningReport) -> bool:
    for item in report.metadata.get('decision_overrides', []) or []:
        if not isinstance(item, dict):
            continue
        if item.get('action') == 'normalize_text' and item.get('decision') in {'keep', 'review'}:
            return True
    return False


class TextCleaner:
    def clean(self, dataframe, report: CleaningReport, mapped_fields: dict[str, dict]):
        if _skip_text_normalization(report):
            return dataframe.copy()
        working = dataframe.copy()
        text_fields = {'client', 'produit', 'reference', 'categorie', 'vendeur', 'canal', 'region', 'entrepot', 'description', 'prenom', 'nom', 'civilite'}
        text_columns = [column for column, meta in mapped_fields.items() if meta.get('standard') in text_fields and column in working.columns]

        for column in text_columns:
            original = working[column].copy()
            standard_field = str(mapped_fields[column].get('standard', ''))
            cleaned = working[column].apply(lambda value: self._normalize_text(value, standard_field))
            changed_mask = original.astype('string') != cleaned.astype('string')
            if bool(changed_mask.fillna(False).any()):
                examples = []
                for index in working.index[changed_mask.fillna(False)][:3]:
                    examples.append({'avant': original.loc[index], 'apres': cleaned.loc[index], 'ligne': int(working.loc[index, '_row_number'])})
                report.add_correction(
                    regle='R14',
                    description=f'Normalisation textuelle de la colonne {column}',
                    nombre=int(changed_mask.fillna(False).sum()),
                    exemples=examples,
                )
            cleaned = cleaned.astype(object)
            cleaned = cleaned.where(pd.notna(cleaned), None)
            working[column] = cleaned
            semantic_analysis = self._semantic_duplicates(working[column], standard_field)
            if semantic_analysis['suggestions']:
                report.metadata.setdefault('dedoublonnage_semantique', []).append(
                    {
                        'colonne': column,
                        'methode': 'thefuzz.token_sort_ratio' if fuzz is not None else 'sequence_matcher',
                        'suggestions': semantic_analysis['suggestions'],
                        'valeurs_uniques_analysees': semantic_analysis['unique_count'],
                    }
                )
                report.metadata.setdefault('actions_requises', []).append(
                    {
                        'priorite': 2,
                        'type': 'VALIDATION_DEDUPLICATION',
                        'message': f"Des variantes proches ont été détectées dans '{column}'. Confirmer les fusions proposées.",
                        'data': {'colonne': column, 'clusters': semantic_analysis['suggestions']},
                    }
                )
                report.add_alert(
                    regle='R16',
                    severite='INFO',
                    message=(
                        f"Des variantes textuelles proches ont été détectées dans la colonne '{column}'. "
                        'Une validation humaine est recommandée avant fusion sémantique.'
                    ),
                )
        return working

    def _normalize_text(self, value, standard_field: str = ''):
        if value in (None, ''):
            return None
        text = unicodedata.normalize('NFC', str(value))
        text = re.sub(r'[\x00-\x1f\x7f-\x9f\u200b\u00a0\ufeff]', ' ', text)
        text = text.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'([!?.,])\1+', r'\1', text)
        normalized_sentinel = unicodedata.normalize('NFC', text).strip().casefold()
        if normalized_sentinel in SENTINELS:
            return None
        if normalized_sentinel == '0' and standard_field in {'client', 'produit', 'categorie', 'vendeur', 'region'}:
            return None
        if not text:
            return None
        words = [self._normalize_word(word, index=index, total_words=len(text.split(' '))) for index, word in enumerate(text.split(' '))]
        return ' '.join(words).rstrip('.')

    def _normalize_word(self, word: str, *, index: int, total_words: int) -> str:
        bare = word.strip()
        if not bare:
            return bare
        if bare.upper() in KNOWN_ACRONYMS:
            return bare.upper()
        lowered = bare.casefold()
        if lowered in LOCAL_NAME_SUFFIXES:
            return bare[:1].upper() + bare[1:].lower()
        if index > 0 and lowered in LOWERCASE_WORDS:
            return lowered
        return bare[:1].upper() + bare[1:].lower()

    def _semantic_duplicates(self, series, standard_field: str):
        if standard_field not in {'client', 'produit', 'categorie', 'region'}:
            return {'unique_count': int(series.dropna().nunique()), 'suggestions': []}
        values = [value for value in series.dropna().unique().tolist() if isinstance(value, str)]
        values = values[:120]
        if len(values) < 2:
            return {'unique_count': len(values), 'suggestions': []}

        frequencies = series.dropna().astype(str).value_counts().to_dict()
        candidates = []
        seen_pairs = set()
        for index, left in enumerate(values):
            for right in values[index + 1 :]:
                ratio = self._similarity(left, right)
                if ratio >= 85 and left.lower() != right.lower():
                    pair_key = tuple(sorted((left.lower(), right.lower())))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    canonical = self._canonical_value(left, right, frequencies)
                    variant = right if canonical == left else left
                    candidates.append(
                        {
                            'canonique': canonical,
                            'variante': variant,
                            'score': ratio,
                            'occurrences_canonique': int(frequencies.get(canonical, 0)),
                            'occurrences_variante': int(frequencies.get(variant, 0)),
                        }
                    )
                    if len(candidates) >= 5:
                        return {'unique_count': len(values), 'suggestions': candidates}
        return {'unique_count': len(values), 'suggestions': candidates}

    def _canonical_value(self, left: str, right: str, frequencies: dict[str, int]) -> str:
        left_frequency = int(frequencies.get(left, 0))
        right_frequency = int(frequencies.get(right, 0))
        if left_frequency != right_frequency:
            return left if left_frequency > right_frequency else right
        if len(left) != len(right):
            return left if len(left) > len(right) else right
        return left

    def _similarity(self, left: str, right: str) -> int:
        if fuzz is not None:
            return int(fuzz.token_sort_ratio(left, right))
        return int(SequenceMatcher(None, left.lower(), right.lower()).ratio() * 100)
