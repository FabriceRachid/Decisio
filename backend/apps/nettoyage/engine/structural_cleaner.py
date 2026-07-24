from __future__ import annotations

import pandas as pd

from .report import CleaningReport

EMPTY_SENTINELS = {'', ' ', 'N/A', 'n/a', 'NA', '-', '—', '#', None}


def _missing_mask(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    mask = dataframe[columns].isna().copy()
    for column in columns:
        mask[column] = mask[column] | dataframe[column].astype('string').str.strip().isin({item for item in EMPTY_SENTINELS if isinstance(item, str)}).fillna(False)
    return mask


def _has_decision(report: CleaningReport, action: str, decision: str) -> bool:
    for item in report.metadata.get('decision_overrides', []) or []:
        if not isinstance(item, dict):
            continue
        if item.get('action') == action and item.get('decision') == decision:
            return True
    return False


class StructuralCleaner:
    def clean(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict]) -> pd.DataFrame:
        working = dataframe.copy()
        data_columns = [column for column in working.columns if column != '_row_number']
        if not data_columns:
            return working
        report.metadata.setdefault('structural_analysis', {})

        missing = _missing_mask(working, data_columns)

        empty_rows = working.loc[missing.all(axis=1), '_row_number'].astype(int).tolist()
        if empty_rows:
            working = working.loc[~missing.all(axis=1)].reset_index(drop=True)
            report.add_correction(
                regle='R01',
                description='Suppression des lignes entièrement vides',
                nombre=len(empty_rows),
                exemples=[{'avant': f'Ligne {row_no}', 'apres': 'supprimée'} for row_no in empty_rows[:3]],
            )

        quasi_empty_columns = []
        quasi_empty_details = []
        for column in data_columns:
            fill_rate = 1 - float(missing[column].mean())
            if fill_rate < 0.05:
                quasi_empty_columns.append(column)
                quasi_empty_details.append({'column': column, 'fill_rate': round(fill_rate, 4)})
                report.add_alert(
                    regle='R02',
                    severite='MOYEN',
                    message=f"La colonne '{column}' est remplie à seulement {round(fill_rate * 100, 1)}%.",
                )
        if quasi_empty_details:
            report.metadata['structural_analysis']['quasi_empty_columns'] = quasi_empty_details

        sparse_rows = []
        row_missing_rate = missing.mean(axis=1)
        for index, missing_rate in row_missing_rate.items():
            if missing_rate > 0.8 and missing_rate < 1:
                sparse_rows.append(
                    {
                        'row_number': int(working.at[index, '_row_number']),
                        'missing_rate': round(float(missing_rate), 4),
                    }
                )
        if sparse_rows:
            report.metadata['structural_analysis']['sparse_rows'] = sparse_rows[:200]
            report.add_alert(
                regle='R02B',
                severite='MOYEN',
                message=f"{len(sparse_rows)} lignes sont presque vides et peuvent etre supprimees apres validation utilisateur.",
                lignes=[item['row_number'] for item in sparse_rows[:20]],
            )

        parasite_columns = [column for column in quasi_empty_columns if column.lower().startswith(('unnamed', 'column ', 'col_'))]
        if parasite_columns:
            working = working.drop(columns=parasite_columns, errors='ignore')
            report.add_correction(
                regle='R05',
                description='Suppression des colonnes parasites quasi vides',
                nombre=len(parasite_columns),
                exemples=[{'avant': column, 'apres': 'supprimée'} for column in parasite_columns[:3]],
            )

        if not (_has_decision(report, 'exact_duplicates', 'keep') or _has_decision(report, 'exact_duplicates', 'review')):
            dedupe_columns = [column for column in working.columns if column != '_row_number']
            duplicate_mask = working.duplicated(subset=dedupe_columns, keep='first')
            duplicate_rows = working.loc[duplicate_mask, '_row_number'].astype(int).tolist()
            if duplicate_rows:
                working = working.loc[~duplicate_mask].reset_index(drop=True)
                report.add_correction(
                    regle='R03',
                    description='Suppression des doublons exacts',
                    nombre=len(duplicate_rows),
                    exemples=[{'avant': f'Ligne {row_no}', 'apres': 'supprimée'} for row_no in duplicate_rows[:3]],
                )

        self._detect_partial_duplicates(working, report, mapped_fields)
        return working

    def _detect_partial_duplicates(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict]) -> None:
        reverse_mapping = {meta['standard']: column for column, meta in mapped_fields.items()}
        candidate_keys = []
        if 'id_commande' in reverse_mapping:
            candidate_keys.append([reverse_mapping['id_commande']])
        if {'date', 'client', 'montant_total'}.issubset(reverse_mapping):
            candidate_keys.append([reverse_mapping['date'], reverse_mapping['client'], reverse_mapping['montant_total']])

        for key_columns in candidate_keys:
            if not all(column in dataframe.columns for column in key_columns):
                continue
            duplicated = dataframe[dataframe.duplicated(subset=key_columns, keep=False)]
            if duplicated.empty:
                continue
            conflict_rows = duplicated['_row_number'].astype(int).head(10).tolist()
            report.add_alert(
                regle='R04',
                severite='INFO',
                message=f"{len(duplicated)} lignes partagent une même clé métier et doivent être revues par M3.",
                lignes=conflict_rows,
            )
            break
