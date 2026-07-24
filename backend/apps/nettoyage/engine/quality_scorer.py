from __future__ import annotations

import pandas as pd


class QualityScorer:
    def compute(self, dataframe: pd.DataFrame, report) -> tuple[float, dict[str, float]]:
        data_columns = [column for column in dataframe.columns if column != '_row_number']
        if not data_columns or dataframe.empty:
            detail = {
                'completude': 0.0,
                'unicite': 100.0,
                'validite': 0.0,
                'coherence': 100.0,
                'normalisation': 100.0,
            }
            return 0.0, detail

        empties = dataframe[data_columns].isna().copy()
        for column in data_columns:
            empties[column] = empties[column] | dataframe[column].astype('string').str.strip().eq('').fillna(False)

        completeness = float((1 - empties.mean().mean()) * 100)
        uniqueness = float((1 - dataframe.duplicated(subset=data_columns, keep='first').mean()) * 100)
        critical_alerts = len([alert for alert in report.alertes if alert['severite'] == 'CRITIQUE'])
        medium_alerts = len([alert for alert in report.alertes if alert['severite'] == 'MOYEN'])
        info_alerts = len([alert for alert in report.alertes if alert['severite'] == 'INFO'])
        total_rows = max(len(dataframe), 1)
        invalid_ratio = min(1.0, (critical_alerts * 1.0 + medium_alerts * 0.5 + info_alerts * 0.2) / total_rows)
        coherence = max(0.0, 100 - ((critical_alerts * 18) + (medium_alerts * 6)))
        validity = max(0.0, 100 - (invalid_ratio * 100))

        conversion_events = sum(int(correction.get('nombre', 0)) for correction in report.corrections)
        non_empty_cells = max(int((~empties).sum().sum()), 1)
        normalization = min(100.0, max(0.0, (conversion_events / non_empty_cells) * 100))
        if conversion_events == 0 and report.corrections:
            normalization = min(100.0, float(len(report.corrections) * 5))

        scores_par_colonne = self._compute_column_scores(dataframe, empties, report)
        report.metadata['score_par_colonne'] = scores_par_colonne
        report.metadata['colonnes_problematiques'] = [
            column for column, _score in sorted(scores_par_colonne.items(), key=lambda item: item[1])[:3]
        ]

        detail = {
            'completude': completeness,
            'unicite': uniqueness,
            'validite': validity,
            'coherence': coherence,
            'normalisation': normalization,
        }
        score = (
            completeness * 0.30
            + uniqueness * 0.20
            + validity * 0.25
            + coherence * 0.15
            + normalization * 0.10
        )
        return score, detail

    def _compute_column_scores(self, dataframe: pd.DataFrame, empties: pd.DataFrame, report) -> dict[str, float]:
        data_columns = [column for column in dataframe.columns if column != '_row_number']
        row_alert_index: dict[int, float] = {}
        severity_weights = {'CRITIQUE': 18.0, 'MOYEN': 8.0, 'INFO': 3.0}
        for alert in report.alertes:
            weight = severity_weights.get(alert.get('severite'), 2.0)
            for row_number in alert.get('lignes', []) or []:
                row_alert_index[int(row_number)] = max(row_alert_index.get(int(row_number), 0.0), weight)

        scores: dict[str, float] = {}
        for column in data_columns:
            score = 100.0
            empty_rate = float(empties[column].mean()) if len(empties) else 0.0
            score -= empty_rate * 45
            impacted_rows = 0
            if '_row_number' in dataframe.columns:
                impacted_rows = int(
                    dataframe['_row_number'].apply(lambda row_number: int(row_number) in row_alert_index).sum()
                )
            if len(dataframe):
                score -= (impacted_rows / len(dataframe)) * 20
            score = max(0.0, min(100.0, score))
            scores[column] = round(score, 2)
        return scores
