from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[reportMissingImports]
from django.conf import settings

from .report import CleaningReport

logger = logging.getLogger(__name__)

try:
    import chardet  # type: ignore[reportMissingImports]
except Exception:  # pragma: no cover - optional dependency
    chardet = None


class LoaderService:
    PREFERRED_SHEET_TOKENS = ('vente', 'ventes', 'données', 'donnees', 'data', 'export', 'feuil', 'sheet', 'main', 'transactions', 'sales')
    DEPRIORITIZED_SHEET_TOKENS = ('resume', 'résumé', 'summary', 'readme', 'guide', 'mode emploi', 'instructions', 'instruction', 'notes', 'param', 'config', 'dashboard', 'graph')

    def describe_source(self, source) -> dict[str, Any]:
        metadata = self._inspect_source_file(source)
        metadata['structure_candidate'] = self._detect_structure_candidate(source, metadata)
        return metadata

    def load_from_source(self, source, report: CleaningReport) -> pd.DataFrame:
        raw_rows = list(source.raw_data_rows.order_by('row_number').values('row_number', 'data'))
        if not raw_rows:
            raise ValueError('La source ne contient aucune ligne brute.')

        source_metadata = self._inspect_source_file(source)
        report.metadata.update(source_metadata)

        if source.source_type == 'excel' and source.file_path:
            reconstructed = self._load_excel_structured_source(
                source=source,
                raw_rows=raw_rows,
                report=report,
                inspection=source_metadata,
            )
            if reconstructed is not None:
                return reconstructed

        records = []
        for row in raw_rows:
            record = {'_row_number': row['row_number']}
            record.update(row['data'])
            records.append(record)

        dataframe = pd.DataFrame(records).where(pd.notnull(pd.DataFrame(records)), None)
        return dataframe

    def _inspect_source_file(self, source) -> dict:
        metadata = {
            'encodage_detecte': source.encoding,
            'separateur_detecte': source.delimiter,
            'has_header': source.has_header,
            'source_type': source.source_type,
            'checksum_md5': source.checksum_md5,
        }

        if not source.file_path:
            return metadata

        file_path = self._resolve_source_file_path(source.file_path)
        if not file_path.exists() or not file_path.is_file():
            return metadata

        try:
            if source.source_type == 'csv':
                metadata.update(self._inspect_csv(file_path))
            elif source.source_type == 'excel':
                metadata.update(self._inspect_excel(file_path))
        except Exception:
            logger.warning(
                'Unable to inspect source file metadata; default source metadata will be used.',
                extra={
                    'source_id': getattr(source, 'id', None),
                    'file_path': str(file_path),
                    'source_type': getattr(source, 'source_type', None),
                },
                exc_info=True,
            )
            return metadata
        return metadata

    def _inspect_csv(self, file_path: Path) -> dict:
        sample_bytes = file_path.read_bytes()[:102400]
        encoding = self._detect_encoding(sample_bytes)
        sample_text = sample_bytes.decode(encoding, errors='replace')
        delimiter = self._detect_delimiter(sample_text)
        lines = [line for line in sample_text.splitlines() if line.strip()][:12]
        header_row_index = self._detect_header_row_index(lines, delimiter)
        has_header = header_row_index == 0
        csv_rows = [next(csv.reader([line], delimiter=delimiter)) for line in lines]
        sample_df = pd.DataFrame(csv_rows).replace('', None)
        content_analysis = self._classify_tabular_content(sample_df, header_row_index=header_row_index)
        return {
            'encodage_detecte': encoding,
            'separateur_detecte': delimiter,
            'has_header': has_header,
            'header_row_index': header_row_index,
            'contenu_probable': content_analysis['content_type'],
            'score_exploitabilite': content_analysis['score'],
            'est_donnee_exploitable': content_analysis['is_data_like'],
            'analyse_contenu_source': content_analysis,
        }

    def _inspect_excel(self, file_path: Path) -> dict:
        workbook = pd.ExcelFile(file_path)
        sheets = workbook.sheet_names
        best_sheet = None
        best_score = -1
        sheet_summaries: list[dict[str, Any]] = []
        candidate_scores: list[dict[str, Any]] = []
        for sheet_name in sheets:
            sample = workbook.parse(sheet_name=sheet_name, nrows=50, header=None)
            metrics = self._score_excel_sheet(sheet_name, sample)
            sheet_summaries.append({
                'name': sheet_name,
                'non_empty_rows': metrics['non_empty_rows'],
                'non_empty_cols': metrics['non_empty_cols'],
                'header_row_index': metrics['header_row_index'],
                'title_like_rows': metrics['title_like_rows'],
                'candidate_header_density': metrics['candidate_header_density'],
                'content_type': metrics['content_type'],
                'is_data_like': metrics['is_data_like'],
                'score': metrics['score'],
            })
            candidate_scores.append({'name': sheet_name, 'score': metrics['score']})
            if metrics['score'] > best_score:
                best_score = metrics['score']
                best_sheet = sheet_name

        candidate_scores.sort(key=lambda item: item['score'], reverse=True)
        ambiguous_sheet_selection = False
        if len(candidate_scores) >= 2:
            ambiguous_sheet_selection = abs(candidate_scores[0]['score'] - candidate_scores[1]['score']) <= 8
        selected_sheet_summary = next((item for item in sheet_summaries if item['name'] == best_sheet), None)
        return {
            'feuilles_disponibles': sheets,
            'feuille_principale_detectee': best_sheet,
            'feuilles_analysees': sheet_summaries,
            'selection_feuille_ambigue': ambiguous_sheet_selection,
            'contenu_probable': (selected_sheet_summary or {}).get('content_type'),
            'score_exploitabilite': (selected_sheet_summary or {}).get('score'),
            'est_donnee_exploitable': bool((selected_sheet_summary or {}).get('is_data_like')),
        }

    def _detect_encoding(self, sample_bytes: bytes) -> str:
        if chardet is not None:
            detected = chardet.detect(sample_bytes)
            if detected.get('encoding'):
                detected_encoding = str(detected['encoding']).lower()
                try:
                    sample_bytes.decode(detected_encoding)
                    return detected_encoding
                except UnicodeDecodeError:
                    logger.debug('Detected encoding %s failed decoding sample; fallback order retained.', detected_encoding)
        preferred = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252', 'latin-1', 'cp1250']
        for encoding in preferred:
            try:
                sample_bytes.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        return 'utf-8'

    def _detect_delimiter(self, sample_text: str) -> str:
        try:
            detected = csv.Sniffer().sniff(sample_text, delimiters=',;\t|').delimiter
            lines = [line for line in sample_text.splitlines() if line.strip()][:10]
            if self._delimiter_score(lines, detected) > 1:
                return detected
        except Exception:
            pass

        candidates = [',', ';', '\t', '|']
        best_delimiter = ','
        best_score = -1.0
        lines = [line for line in sample_text.splitlines() if line.strip()][:10]
        for delimiter in candidates:
            score = self._delimiter_score(lines, delimiter)
            if score > best_score:
                best_score = score
                best_delimiter = delimiter
        return best_delimiter

    def _detect_header(self, lines: list[str], delimiter: str) -> bool:
        if not lines:
            return True
        first_row = [cell.strip() for cell in lines[0].split(delimiter)]
        if not first_row:
            return True
        text_like = 0
        for cell in first_row:
            if not cell:
                continue
            parsed_numeric = pd.to_numeric(cell, errors='coerce')
            if pd.isna(parsed_numeric):
                text_like += 1
        return (text_like / max(len(first_row), 1)) > 0.5

    def _detect_header_row_index(self, lines: list[str], delimiter: str) -> int:
        if not lines:
            return 0
        best_index = 0
        best_score = -1.0
        for index, line in enumerate(lines[:10]):
            cells = [cell.strip() for cell in line.split(delimiter)]
            if not cells:
                continue
            non_empty = [cell for cell in cells if cell]
            if not non_empty:
                continue
            text_like = 0
            for cell in non_empty:
                parsed_numeric = pd.to_numeric(cell, errors='coerce')
                if pd.isna(parsed_numeric):
                    text_like += 1
            score = (len(non_empty) / max(len(cells), 1)) + (text_like / max(len(non_empty), 1))
            if score > best_score:
                best_score = score
                best_index = index
        return best_index

    def _detect_excel_header_row(self, sample: pd.DataFrame) -> int:
        for index, row in sample.iterrows():
            values = [str(value).strip() for value in row.tolist() if pd.notna(value) and str(value).strip()]
            if not values:
                continue
            text_like = 0
            for value in values:
                parsed_numeric = pd.to_numeric(value, errors='coerce')
                if pd.isna(parsed_numeric):
                    text_like += 1
            if (len(values) / max(sample.shape[1], 1)) >= 0.6 and (text_like / max(len(values), 1)) >= 0.6:
                return int(index)
        return 0

    def _score_excel_sheet(self, sheet_name: str, sample: pd.DataFrame) -> dict[str, Any]:
        lower_name = sheet_name.lower()
        non_empty_rows = int(sample.dropna(how='all').shape[0])
        non_empty_cols = int(sample.dropna(axis=1, how='all').shape[1])
        header_row_index = self._detect_excel_header_row(sample)
        title_like_rows = self._count_title_like_rows(sample)
        candidate_header_density = self._header_density(sample, header_row_index)
        content_analysis = self._classify_tabular_content(sample, header_row_index=header_row_index)

        score = float(content_analysis['score'])
        if any(token in lower_name for token in self.PREFERRED_SHEET_TOKENS):
            score += 12
        if any(token in lower_name for token in self.DEPRIORITIZED_SHEET_TOKENS):
            score -= 10

        return {
            'score': round(score, 2),
            'non_empty_rows': non_empty_rows,
            'non_empty_cols': non_empty_cols,
            'header_row_index': header_row_index,
            'title_like_rows': title_like_rows,
            'candidate_header_density': round(candidate_header_density, 2),
            'content_type': content_analysis['content_type'],
            'is_data_like': content_analysis['is_data_like'],
        }

    def _count_title_like_rows(self, sample: pd.DataFrame) -> int:
        title_like = 0
        for _, row in sample.head(6).iterrows():
            values = [str(value).strip() for value in row.tolist() if pd.notna(value) and str(value).strip()]
            if not values:
                continue
            if len(values) == 1 and len(values[0]) > 8:
                title_like += 1
                continue
            if len(values) <= 2 and all(pd.isna(pd.to_numeric(value, errors='coerce')) for value in values):
                title_like += 1
        return title_like

    def _header_density(self, sample: pd.DataFrame, header_row_index: int) -> float:
        if sample.empty or header_row_index >= len(sample.index):
            return 0.0
        row = sample.iloc[header_row_index]
        values = [str(value).strip() for value in row.tolist() if pd.notna(value) and str(value).strip()]
        if not values:
            return 0.0
        return len(values) / max(sample.shape[1], 1)

    def _classify_tabular_content(self, sample: pd.DataFrame, *, header_row_index: int) -> dict[str, Any]:
        working = sample.copy()
        if working.empty:
            return {
                'content_type': 'vide',
                'score': 0.0,
                'is_data_like': False,
            }

        non_empty_rows = int(working.dropna(how='all').shape[0])
        non_empty_cols = int(working.dropna(axis=1, how='all').shape[1])
        title_like_rows = self._count_title_like_rows(working)
        header_density = self._header_density(working, header_row_index)

        header_values: list[str] = []
        if 0 <= header_row_index < len(working.index):
            header_values = [
                str(value).strip()
                for value in working.iloc[header_row_index].tolist()
                if pd.notna(value) and str(value).strip()
            ]

        data_part = working.iloc[header_row_index + 1 :] if header_row_index + 1 < len(working.index) else working.iloc[0:0]
        row_populated_counts: list[int] = []
        flat_values: list[str] = []
        narrative_like_rows = 0
        for _, row in data_part.head(25).iterrows():
            values = [str(value).strip() for value in row.tolist() if pd.notna(value) and str(value).strip()]
            if not values:
                continue
            row_populated_counts.append(len(values))
            flat_values.extend(values)
            if len(values) <= 2 and all(pd.isna(pd.to_numeric(value, errors='coerce')) for value in values):
                narrative_like_rows += 1

        average_populated_cols = (sum(row_populated_counts) / len(row_populated_counts)) if row_populated_counts else 0.0
        row_width_consistency = 0.0
        if row_populated_counts:
            spread = max(row_populated_counts) - min(row_populated_counts)
            baseline = max(sum(row_populated_counts) / len(row_populated_counts), 1)
            row_width_consistency = max(0.0, 1 - (spread / baseline))

        numeric_like_ratio = self._ratio_numeric_like(flat_values)
        date_like_ratio = self._ratio_date_like(flat_values)
        short_label_ratio = self._ratio_short_labels(header_values)
        header_uniqueness = (len({value.lower() for value in header_values}) / len(header_values)) if header_values else 0.0

        score = 0.0
        score += min(non_empty_rows * 3.0, 30.0)
        score += min(non_empty_cols * 4.0, 24.0)
        score += header_density * 16.0
        score += short_label_ratio * 12.0
        score += header_uniqueness * 10.0
        score += row_width_consistency * 18.0
        score += min(average_populated_cols * 2.0, 16.0)
        score += numeric_like_ratio * 10.0
        score += date_like_ratio * 10.0
        score -= title_like_rows * 6.0
        score -= narrative_like_rows * 5.0

        if non_empty_rows <= 2:
            score -= 30.0
        if non_empty_cols <= 1:
            score -= 20.0
        if average_populated_cols < 2:
            score -= 18.0

        if date_like_ratio >= 0.08 and numeric_like_ratio >= 0.15:
            content_type = 'tableau_transactionnel'
        elif numeric_like_ratio >= 0.55 and non_empty_cols >= 2:
            content_type = 'tableau_indicateurs'
        elif header_density >= 0.45 and average_populated_cols >= 3:
            content_type = 'jeu_de_donnees_structure'
        elif title_like_rows >= 2 or narrative_like_rows >= 2:
            content_type = 'resume_ou_notes'
        else:
            content_type = 'feuille_semistructuree'

        is_data_like = score >= 55 and content_type in {'tableau_transactionnel', 'tableau_indicateurs', 'jeu_de_donnees_structure', 'feuille_semistructuree'}

        return {
            'content_type': content_type,
            'score': round(max(score, 0.0), 2),
            'is_data_like': is_data_like,
            'header_density': round(header_density, 2),
            'header_uniqueness': round(header_uniqueness, 2),
            'average_populated_cols': round(average_populated_cols, 2),
            'row_width_consistency': round(row_width_consistency, 2),
            'numeric_like_ratio': round(numeric_like_ratio, 2),
            'date_like_ratio': round(date_like_ratio, 2),
        }

    def _ratio_numeric_like(self, values: list[str]) -> float:
        if not values:
            return 0.0
        numeric_like = 0
        for value in values:
            normalized = value.replace(' ', '').replace('\xa0', '').replace(',', '.')
            if pd.notna(pd.to_numeric(normalized, errors='coerce')):
                numeric_like += 1
        return numeric_like / len(values)

    def _ratio_date_like(self, values: list[str]) -> float:
        if not values:
            return 0.0
        date_like = 0
        for value in values:
            if pd.notna(pd.to_datetime(value, errors='coerce', dayfirst=True, format='mixed')):
                date_like += 1
        return date_like / len(values)

    def _ratio_short_labels(self, values: list[str]) -> float:
        if not values:
            return 0.0
        short_labels = 0
        for value in values:
            if 1 <= len(value) <= 40 and pd.isna(pd.to_numeric(value, errors='coerce')):
                short_labels += 1
        return short_labels / len(values)

    def _delimiter_score(self, lines: list[str], delimiter: str) -> float:
        counts = [len(line.split(delimiter)) for line in lines]
        informative = [count for count in counts if count > 1]
        if not informative:
            return -1.0
        consistency = len(informative) / max(len(counts), 1)
        width = sum(informative) / len(informative)
        spread = max(informative) - min(informative)
        return (width * 10) + (consistency * 5) - spread

    def _load_excel_structured_source(
        self,
        *,
        source,
        raw_rows: list[dict[str, Any]],
        report: CleaningReport,
        inspection: dict[str, Any],
    ) -> pd.DataFrame | None:
        file_path = self._resolve_source_file_path(source.file_path)
        if not file_path.exists() or not file_path.is_file():
            return None

        try:
            workbook = pd.ExcelFile(file_path)
            sheet_name = inspection.get('feuille_principale_detectee') or workbook.sheet_names[0]
            sheet = workbook.parse(sheet_name=sheet_name, header=None).where(pd.notnull, None)
            normalized = self._normalize_cross_tab_sheet(
                sheet,
                raw_rows=raw_rows,
                report=report,
                sheet_name=str(sheet_name),
                source_name=str(getattr(source, 'name', '') or ''),
            )
            if normalized is not None:
                return normalized
        except Exception:
            logger.warning(
                'Unable to structurally reconstruct Excel sheet; raw ingestion rows will be used.',
                extra={
                    'source_id': getattr(source, 'id', None),
                    'file_path': str(file_path),
                    'sheet_name': inspection.get('feuille_principale_detectee'),
                },
                exc_info=True,
            )
        return None

    def _detect_structure_candidate(self, source, inspection: dict[str, Any]) -> dict[str, Any]:
        candidate = {
            'detected': False,
            'type': None,
            'confidence': 0.0,
            'sheet_name': inspection.get('feuille_principale_detectee'),
        }
        if getattr(source, 'source_type', None) != 'excel' or not getattr(source, 'file_path', None):
            return candidate

        file_path = self._resolve_source_file_path(source.file_path)
        if not file_path.exists() or not file_path.is_file():
            return candidate

        try:
            workbook = pd.ExcelFile(file_path)
            sheet_name = inspection.get('feuille_principale_detectee') or workbook.sheet_names[0]
            sheet = workbook.parse(sheet_name=sheet_name, header=None).where(pd.notnull, None)
            structure = self._detect_cross_tab_structure(sheet)
            if structure is None:
                return candidate
            return {
                'detected': True,
                'type': 'tableau_croise_excel',
                'confidence': 0.92,
                'sheet_name': str(sheet_name),
                'signature': {
                    'axis_1_row': int(structure['axis_1_row']),
                    'axis_2_row': int(structure['axis_2_row']),
                    'key_row': int(structure['key_row']),
                    'data_start_row': int(structure['data_start_row']),
                    'key_column': int(structure['key_column']),
                },
            }
        except Exception:
            logger.warning(
                'Unable to pre-classify Excel structural candidate.',
                extra={
                    'source_id': getattr(source, 'id', None),
                    'file_path': str(file_path),
                },
                exc_info=True,
            )
            return candidate

    def _normalize_cross_tab_sheet(
        self,
        sheet: pd.DataFrame,
        *,
        raw_rows: list[dict[str, Any]],
        report: CleaningReport,
        sheet_name: str,
        source_name: str,
    ) -> pd.DataFrame | None:
        structure = self._detect_cross_tab_structure(sheet)
        if structure is None:
            return None

        axis_1_row = int(structure['axis_1_row'])
        axis_2_row = int(structure['axis_2_row'])
        key_row = int(structure['key_row'])
        data_start_row = int(structure['data_start_row'])
        key_column = int(structure['key_column'])

        axis_1_name = self._sanitize_header_label(sheet.iat[axis_1_row, key_column], fallback='Dimension 1')
        axis_2_name = self._sanitize_header_label(sheet.iat[axis_2_row, key_column], fallback='Dimension 2')
        key_name = self._sanitize_header_label(sheet.iat[key_row, key_column], fallback='Ligne')
        measure_name = self._infer_measure_name(source_name=source_name, sheet_name=sheet_name)

        axis_1_values = self._forward_fill_labels(sheet.iloc[axis_1_row].tolist())
        axis_2_values = [self._sanitize_cell(value) for value in sheet.iloc[axis_2_row].tolist()]

        aggregate_paths: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        trace_samples: list[dict[str, Any]] = []
        max_row_number = max(int(row['row_number']) for row in raw_rows) if raw_rows else 0
        synthetic_row_number = max_row_number + 1000

        for row_index in range(data_start_row, len(sheet.index)):
            key_value = self._sanitize_cell(sheet.iat[row_index, key_column])
            if key_value in {None, ''}:
                continue

            for column_index in range(key_column + 1, len(sheet.columns)):
                value = sheet.iat[row_index, column_index]
                cleaned_value = self._sanitize_cell(value)
                if cleaned_value in {None, ''}:
                    continue

                axis_1_value = self._sanitize_cell(axis_1_values[column_index] if column_index < len(axis_1_values) else None)
                axis_2_value = self._sanitize_cell(axis_2_values[column_index] if column_index < len(axis_2_values) else None)
                path = [part for part in [axis_1_value, axis_2_value] if part]
                if not path:
                    continue

                if self._looks_like_aggregate_path(path):
                    aggregate_paths.append(
                        {
                            'row_excel': row_index + 1,
                            'colonne_excel': column_index + 1,
                            'chemin': path,
                            'valeur': cleaned_value,
                        }
                    )
                    continue

                record = {
                    '_row_number': synthetic_row_number,
                    key_name: key_value,
                    axis_1_name: axis_1_value,
                    axis_2_name: axis_2_value,
                    measure_name: cleaned_value,
                }
                records.append(record)
                if len(trace_samples) < 8:
                    trace_samples.append(
                        {
                            'row_number_reconstruit': synthetic_row_number,
                            'origine_excel': {'row': row_index + 1, 'column': column_index + 1},
                            'chemin': {
                                key_name: key_value,
                                axis_1_name: axis_1_value,
                                axis_2_name: axis_2_value,
                            },
                            'valeur': cleaned_value,
                        }
                    )
                synthetic_row_number += 1

        if not records:
            return None

        report.metadata['structure_reconstruction'] = {
            'activee': True,
            'type': 'tableau_croise_excel',
            'feuille': sheet_name,
            'dimensions': [key_name, axis_1_name, axis_2_name],
            'mesure': measure_name,
            'lignes_reconstruites': len(records),
            'colonnes_agregees_detectees': aggregate_paths[:20],
            'traces_echantillon': trace_samples,
        }
        report.metadata.setdefault('actions_requises', []).append(
            {
                'type': 'validation_structure',
                'titre': 'Valider la reconstruction structurelle',
                'message': f"La feuille '{sheet_name}' a ete interpretee comme un tableau croise puis reconstruite en table canonique.",
            }
        )
        report.add_correction(
            regle='R30',
            description='Reconstruction structurelle d une feuille Excel semistructuree en table canonique',
            nombre=len(records),
            exemples=[
                {
                    'avant': f'Feuille {sheet_name} en format croise',
                    'apres': f'{key_name} + {axis_1_name} + {axis_2_name} + {measure_name}',
                }
            ],
        )
        return pd.DataFrame.from_records(records).where(pd.notnull, None)

    def _detect_cross_tab_structure(self, sheet: pd.DataFrame) -> dict[str, int] | None:
        if sheet.empty or len(sheet.index) < 4 or len(sheet.columns) < 4:
            return None

        row0 = [self._sanitize_cell(value) for value in sheet.iloc[0].tolist()]
        row1 = [self._sanitize_cell(value) for value in sheet.iloc[1].tolist()]
        row2 = [self._sanitize_cell(value) for value in sheet.iloc[2].tolist()]

        if row0[0] is None or row1[0] is None or row2[0] is None:
            return None
        if not self._is_header_like_row(row0) or not self._is_header_like_row(row1):
            return None

        row2_non_empty = [value for value in row2 if value not in {None, ''}]
        if len(row2_non_empty) > 2:
            return None

        sample_data = sheet.iloc[3 : min(len(sheet.index), 28), 1:]
        flat_sample = [
            self._sanitize_cell(value)
            for value in sample_data.to_numpy().flatten().tolist()
            if self._sanitize_cell(value) not in {None, ''}
        ]
        if not flat_sample:
            return None

        numeric_ratio = self._ratio_numeric_like([str(value) for value in flat_sample])
        if numeric_ratio < 0.35:
            return None

        first_column_values = [
            self._sanitize_cell(value)
            for value in sheet.iloc[3 : min(len(sheet.index), 28), 0].tolist()
        ]
        populated_first_column = [value for value in first_column_values if value not in {None, ''}]
        if len(populated_first_column) < 3:
            return None

        return {
            'axis_1_row': 0,
            'axis_2_row': 1,
            'key_row': 2,
            'data_start_row': 3,
            'key_column': 0,
        }

    def _is_header_like_row(self, values: list[Any]) -> bool:
        meaningful = [self._sanitize_cell(value) for value in values if self._sanitize_cell(value) not in {None, ''}]
        if len(meaningful) < 2:
            return False
        text_like = 0
        for value in meaningful:
            if pd.isna(pd.to_numeric(str(value), errors='coerce')):
                text_like += 1
        return (text_like / len(meaningful)) >= 0.8

    def _forward_fill_labels(self, values: list[Any]) -> list[Any]:
        filled: list[Any] = []
        current = None
        for value in values:
            cleaned = self._sanitize_cell(value)
            if cleaned not in {None, ''}:
                current = cleaned
            filled.append(current)
        return filled

    def _sanitize_header_label(self, value: Any, *, fallback: str) -> str:
        cleaned = self._sanitize_cell(value)
        if cleaned in {None, ''}:
            return fallback
        text = str(cleaned).replace('>>', ' ').replace(':', ' ')
        text = ' '.join(text.split()).strip()
        return text or fallback

    def _sanitize_cell(self, value: Any) -> Any:
        if pd.isna(value):
            return None
        if isinstance(value, str):
            stripped = ' '.join(value.replace('\xa0', ' ').split()).strip()
            return stripped or None
        return value

    def _looks_like_aggregate_path(self, path: list[Any]) -> bool:
        joined = ' '.join(str(part).lower() for part in path if part not in {None, ''})
        return 'total' in joined

    def _infer_measure_name(self, *, source_name: str, sheet_name: str) -> str:
        lowered = f'{source_name} {sheet_name}'.lower()
        if 'sale' in lowered or 'vente' in lowered:
            return 'Sales'
        if 'amount' in lowered or 'montant' in lowered:
            return 'Montant'
        return 'Valeur'

    def _resolve_source_file_path(self, file_path: str | Path | None) -> Path:
        if not file_path:
            return Path('')

        candidate = Path(file_path)
        if candidate.exists() and candidate.is_file():
            return candidate

        media_root = Path(getattr(settings, 'MEDIA_ROOT', ''))
        if media_root:
            media_candidate = media_root / candidate
            if media_candidate.exists() and media_candidate.is_file():
                return media_candidate

        return candidate
