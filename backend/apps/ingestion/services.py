import hashlib
from io import BytesIO
import csv
import json
from pathlib import Path
from datetime import date, datetime, time

import pandas as pd
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils import timezone

from apps.ingestion.models import DataSource, DataSourceSheet, RawData


class IngestionError(Exception):
    """Raised when an uploaded file cannot be ingested."""


ERP_IMPORT_TEMPLATES = {
    'erp_sales_export': {
        'label': 'ERP Sales Export',
        'description': 'Sales invoices or ERP sales journal exports.',
        'dataset_type': 'sales',
        'required_columns': ['document_no', 'customer_code', 'document_date', 'amount', 'currency'],
        'key_columns': ['document_no'],
        'column_aliases': {
            'document_no': ['document_no', 'doc_no', 'invoice_no', 'invoice_number', 'document number'],
            'customer_code': ['customer_code', 'customer', 'customer_id', 'client_code', 'client'],
            'document_date': ['document_date', 'date', 'invoice_date', 'posting_date'],
            'amount': ['amount', 'net_amount', 'total_amount', 'value'],
            'currency': ['currency', 'currency_code', 'devise'],
        },
        'business_rules': [
            {'type': 'required_non_empty', 'column': 'document_no', 'severity': 'error'},
            {'type': 'required_non_empty', 'column': 'customer_code', 'severity': 'error'},
            {'type': 'required_non_empty', 'column': 'document_date', 'severity': 'error'},
            {'type': 'positive_number', 'column': 'amount', 'severity': 'warning'},
            {'type': 'allowed_values', 'column': 'currency', 'values': ['USD', 'EUR', 'XOF', 'GBP'], 'severity': 'warning'},
            {'type': 'date_parseable', 'column': 'document_date', 'severity': 'warning'},
        ],
    },
    'erp_inventory_export': {
        'label': 'ERP Inventory Export',
        'description': 'Inventory stock snapshots by product and warehouse.',
        'dataset_type': 'inventory',
        'required_columns': ['sku', 'warehouse_code', 'stock_quantity'],
        'key_columns': ['sku', 'warehouse_code'],
        'column_aliases': {
            'sku': ['sku', 'item_code', 'product_code', 'article'],
            'warehouse_code': ['warehouse_code', 'warehouse', 'depot', 'store_code'],
            'stock_quantity': ['stock_quantity', 'quantity', 'qty', 'on_hand'],
            'stock_value': ['stock_value', 'inventory_value', 'value'],
        },
        'business_rules': [
            {'type': 'required_non_empty', 'column': 'sku', 'severity': 'error'},
            {'type': 'required_non_empty', 'column': 'warehouse_code', 'severity': 'error'},
            {'type': 'non_negative_number', 'column': 'stock_quantity', 'severity': 'warning'},
            {'type': 'non_negative_number', 'column': 'stock_value', 'severity': 'warning'},
        ],
    },
    'erp_customer_master': {
        'label': 'ERP Customer Master',
        'description': 'Customer master data exports.',
        'dataset_type': 'customer_master',
        'required_columns': ['customer_code', 'customer_name', 'country'],
        'key_columns': ['customer_code'],
        'column_aliases': {
            'customer_code': ['customer_code', 'customer', 'customer_id', 'client_code'],
            'customer_name': ['customer_name', 'customer_label', 'client_name', 'name'],
            'country': ['country', 'country_code', 'pays'],
            'status': ['status', 'state', 'customer_status'],
        },
        'business_rules': [
            {'type': 'required_non_empty', 'column': 'customer_code', 'severity': 'error'},
            {'type': 'required_non_empty', 'column': 'customer_name', 'severity': 'error'},
            {'type': 'allowed_values', 'column': 'status', 'values': ['active', 'inactive', 'prospect'], 'severity': 'warning', 'case_insensitive': True},
        ],
    },
    'erp_supplier_master': {
        'label': 'ERP Supplier Master',
        'description': 'Supplier or vendor master exports.',
        'dataset_type': 'supplier_master',
        'required_columns': ['supplier_code', 'supplier_name', 'country'],
        'key_columns': ['supplier_code'],
        'column_aliases': {
            'supplier_code': ['supplier_code', 'vendor_code', 'supplier', 'vendor'],
            'supplier_name': ['supplier_name', 'vendor_name', 'name'],
            'country': ['country', 'country_code', 'pays'],
            'payment_terms': ['payment_terms', 'terms', 'payment_term'],
        },
        'business_rules': [
            {'type': 'required_non_empty', 'column': 'supplier_code', 'severity': 'error'},
            {'type': 'required_non_empty', 'column': 'supplier_name', 'severity': 'error'},
        ],
    },
    'erp_gl_entries': {
        'label': 'ERP GL Entries',
        'description': 'General ledger journal or accounting entry exports.',
        'dataset_type': 'gl_entries',
        'required_columns': ['entry_no', 'account_code', 'posting_date', 'debit', 'credit'],
        'key_columns': ['entry_no', 'account_code'],
        'column_aliases': {
            'entry_no': ['entry_no', 'journal_no', 'piece_no', 'entry_number'],
            'account_code': ['account_code', 'gl_account', 'account', 'compte'],
            'posting_date': ['posting_date', 'date', 'entry_date'],
            'debit': ['debit', 'debit_amount'],
            'credit': ['credit', 'credit_amount'],
            'currency': ['currency', 'currency_code', 'devise'],
        },
        'business_rules': [
            {'type': 'required_non_empty', 'column': 'entry_no', 'severity': 'error'},
            {'type': 'required_non_empty', 'column': 'account_code', 'severity': 'error'},
            {'type': 'date_parseable', 'column': 'posting_date', 'severity': 'warning'},
            {'type': 'non_negative_number', 'column': 'debit', 'severity': 'warning'},
            {'type': 'non_negative_number', 'column': 'credit', 'severity': 'warning'},
        ],
    },
}


def preview_uploaded_file(*, user, uploaded_file, source_type, delimiter, encoding, has_header, required_columns, key_columns, template_id, column_mapping):
    file_bytes = _get_uploaded_file_bytes(uploaded_file)

    is_excel = source_type == 'excel' or (
        uploaded_file.name and uploaded_file.name.lower().endswith(('.xlsx', '.xls', '.xlsm'))
    )

    if is_excel:
        try:
            all_sheet_analyses = _analyze_file_bytes_multi_sheet(
                user=user, filename=uploaded_file.name, file_bytes=file_bytes,
                source_type='excel', delimiter=delimiter, encoding=encoding,
                has_header=has_header, required_columns=required_columns,
                key_columns=key_columns, template_id=template_id,
                column_mapping=column_mapping,
            )
        except Exception:
            all_sheet_analyses = None

        if all_sheet_analyses and len(all_sheet_analyses) > 1:
            sheets_preview = []
            for sheet_name, sheet_analysis in all_sheet_analyses.items():
                sheets_preview.append({
                    'sheet_name': sheet_name,
                    'row_count': sheet_analysis['row_count'],
                    'column_count': sheet_analysis['column_count'],
                    'columns': sheet_analysis['columns'],
                    'rows': sheet_analysis['rows'][:10],
                    'quality_score': sheet_analysis.get('metadata', {}).get('quality_score', 0),
                    'content_type': sheet_analysis.get('metadata', {}).get('content_type', ''),
                    'validation_errors': sheet_analysis['validation_errors'],
                    'row_validation_results': sheet_analysis['row_validation_results'],
                })

            first_analysis = list(all_sheet_analyses.values())[0]
            return {
                'filename': first_analysis['filename'],
                'source_type': 'excel',
                'delimiter': delimiter,
                'encoding': encoding,
                'checksum_md5': first_analysis['checksum_md5'],
                'file_size_bytes': first_analysis['file_size_bytes'],
                'row_count': sum(s['row_count'] for s in sheets_preview),
                'column_count': max(s['column_count'] for s in sheets_preview),
                'rows': sheets_preview[0]['rows'],
                'columns': sheets_preview[0]['columns'],
                'metadata': first_analysis['metadata'],
                'validation_errors': [],
                'row_validation_results': sheets_preview[0]['row_validation_results'],
                'sample_rows': sheets_preview[0]['rows'][:10],
                'can_import': True,
                'multi_sheet': True,
                'sheet_count': len(sheets_preview),
                'sheets': sheets_preview,
            }

    analysis = _analyze_file_bytes(
        user=user,
        filename=uploaded_file.name,
        file_bytes=file_bytes,
        source_type=source_type,
        delimiter=delimiter,
        encoding=encoding,
        has_header=has_header,
        required_columns=required_columns,
        key_columns=key_columns,
        template_id=template_id,
        column_mapping=column_mapping,
    )
    return _build_preview_response(analysis)


def list_import_templates():
    templates = []
    for template_id, config in ERP_IMPORT_TEMPLATES.items():
        templates.append({
            'id': template_id,
            'label': config['label'],
            'description': config.get('description'),
            'dataset_type': config.get('dataset_type'),
            'required_columns': config.get('required_columns', []),
            'key_columns': config.get('key_columns', []),
            'business_rules': config.get('business_rules', []),
        })
    return sorted(templates, key=lambda item: item['label'])


def ingest_uploaded_file(*, user, uploaded_file, name, source_type, delimiter, encoding, has_header, description, tags, retention_days, required_columns, key_columns, strict_validation, template_id, column_mapping, existing_file_path=None):
    file_bytes = _get_uploaded_file_bytes(uploaded_file)

    # Check if this is an Excel file (multi-sheet support)
    is_excel = source_type == 'excel' or (
        uploaded_file.name and uploaded_file.name.lower().endswith(('.xlsx', '.xls', '.xlsm'))
    )

    if is_excel:
        try:
            all_sheet_analyses = _analyze_file_bytes_multi_sheet(
                user=user, filename=uploaded_file.name, file_bytes=file_bytes,
                source_type='excel', delimiter=delimiter, encoding=encoding,
                has_header=has_header, required_columns=required_columns,
                key_columns=key_columns, template_id=template_id,
                column_mapping=column_mapping,
            )
        except IngestionError:
            # Fallback to single-sheet analysis
            all_sheet_analyses = None

        if all_sheet_analyses and len(all_sheet_analyses) > 1:
            return _ingest_multi_sheet(
                user=user, uploaded_file=uploaded_file, name=name,
                file_bytes=file_bytes, all_sheet_analyses=all_sheet_analyses,
                has_header=has_header, description=description, tags=tags,
                retention_days=retention_days, strict_validation=strict_validation,
            )

    # Single-sheet path (CSV, JSON, single-sheet Excel fallback)
    analysis = _analyze_file_bytes(
        user=user, filename=uploaded_file.name, file_bytes=file_bytes,
        source_type=source_type, delimiter=delimiter, encoding=encoding,
        has_header=has_header, required_columns=required_columns,
        key_columns=key_columns, template_id=template_id,
        column_mapping=column_mapping,
    )

    if strict_validation and any(error['severity'] == 'error' for error in analysis['validation_errors']):
        raise IngestionError('Strict validation failed. Resolve reported errors before importing.')

    if existing_file_path:
        relative_path = existing_file_path
    else:
        media_root = Path(settings.MEDIA_ROOT)
        storage = FileSystemStorage(location=media_root / 'ingestion_uploads')
        stored_name = storage.save(uploaded_file.name, ContentFile(file_bytes))
        relative_path = str(Path('ingestion_uploads') / stored_name)

    source = DataSource.objects.create(
        name=name,
        source_type=analysis['source_type'],
        file_path=relative_path,
        file_size_bytes=analysis['file_size_bytes'],
        row_count=analysis['row_count'],
        column_count=analysis['column_count'],
        delimiter=analysis['delimiter'],
        encoding=analysis['encoding'],
        has_header=has_header,
        uploaded_by=user,
        status='completed' if not any(error['severity'] == 'error' for error in analysis['validation_errors']) else 'failed',
        metadata=analysis['metadata'],
        validation_errors=analysis['validation_errors'],
        checksum_md5=analysis['checksum_md5'],
        retention_days=retention_days,
        description=description,
        tags=tags,
        lineage_info={
            'source_filename': uploaded_file.name,
            'ingestion_mode': 'api_upload',
        },
        processed_at=timezone.now(),
    )

    raw_rows = []
    start_row_number = 2 if has_header else 1
    row_issues = {item['row_number']: item for item in analysis['row_validation_results']}
    for offset, row in enumerate(analysis['rows']):
        row_number = start_row_number + offset
        row_result = row_issues.get(row_number, {'status': 'valid', 'messages': []})
        raw_rows.append(
            RawData(
                source=source,
                sheet_name='',
                row_number=row_number,
                data=row,
                data_hash=_hash_row(row),
                validation_status=row_result['status'],
                validation_messages=row_result['messages'],
                is_sample=offset < 10,
            )
        )

    RawData.objects.bulk_create(raw_rows)
    return source


def _ingest_multi_sheet(*, user, uploaded_file, name, file_bytes, all_sheet_analyses, has_header, description, tags, retention_days, strict_validation):
    """
    Ingest all sheets from a multi-sheet Excel file.
    Creates one DataSource with multiple DataSourceSheet records.
    """
    media_root = Path(settings.MEDIA_ROOT)
    storage = FileSystemStorage(location=media_root / 'ingestion_uploads')
    stored_name = storage.save(uploaded_file.name, ContentFile(file_bytes))
    relative_path = str(Path('ingestion_uploads') / stored_name)

    # Use the first sheet's analysis for DataSource metadata
    first_analysis = next(iter(all_sheet_analyses.values()))
    total_rows = sum(a['row_count'] for a in all_sheet_analyses.values())

    has_errors = False
    all_validation_errors = []
    for sheet_name, a in all_sheet_analyses.items():
        for error in a.get('validation_errors', []):
            all_validation_errors.append({**error, 'sheet_name': sheet_name})
            if error.get('severity') == 'error':
                has_errors = True

    source = DataSource.objects.create(
        name=name,
        source_type='excel',
        file_path=relative_path,
        file_size_bytes=first_analysis['file_size_bytes'],
        row_count=total_rows,
        column_count=first_analysis['column_count'],
        delimiter=first_analysis['delimiter'],
        encoding=first_analysis['encoding'],
        has_header=has_header,
        uploaded_by=user,
        status='failed' if (strict_validation and has_errors) else 'completed',
        metadata={
            'sheet_count': len(all_sheet_analyses),
            'sheet_names': list(all_sheet_analyses.keys()),
            'is_multi_sheet': True,
        },
        validation_errors=all_validation_errors,
        checksum_md5=first_analysis['checksum_md5'],
        retention_days=retention_days,
        description=description,
        tags=tags,
        lineage_info={
            'source_filename': uploaded_file.name,
            'ingestion_mode': 'api_upload',
            'multi_sheet': True,
        },
        processed_at=timezone.now(),
    )

    all_raw_rows = []
    for sheet_idx, (sheet_name, analysis) in enumerate(all_sheet_analyses.items()):
        # Create DataSourceSheet record
        DataSourceSheet.objects.create(
            source=source,
            sheet_name=sheet_name,
            sheet_index=sheet_idx,
            row_count=analysis['row_count'],
            column_count=analysis['column_count'],
            column_names=analysis['columns'],
            is_active=True,
            quality_score=analysis['metadata'].get('quality_score'),
            content_type=analysis['metadata'].get('content_type', ''),
            metadata=analysis['metadata'],
        )

        start_row_number = 2 if has_header else 1
        row_issues = {item['row_number']: item for item in analysis['row_validation_results']}
        for offset, row in enumerate(analysis['rows']):
            row_number = start_row_number + offset
            row_result = row_issues.get(row_number, {'status': 'valid', 'messages': []})
            all_raw_rows.append(
                RawData(
                    source=source,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    data=row,
                    data_hash=_hash_row(row),
                    validation_status=row_result['status'],
                    validation_messages=row_result['messages'],
                    is_sample=offset < 10,
                )
            )

    RawData.objects.bulk_create(all_raw_rows)
    return source


def _analyze_file_bytes(*, user, filename, file_bytes, source_type, delimiter, encoding, has_header, required_columns, key_columns, template_id, column_mapping):
    try:
        template_config = _resolve_template_config(template_id)
        dataframe, detected_source_type, detected_delimiter, detected_encoding = _load_dataframe(
            filename=filename,
            source_bytes=file_bytes,
            source_type=source_type,
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
        )
        dataframe = _normalize_dataframe_columns(dataframe)
        dataframe, resolved_mapping = _apply_column_mapping(dataframe, template_config=template_config, column_mapping=column_mapping)

        resolved_required_columns = _merge_unique(template_config.get('required_columns', []), required_columns)
        resolved_key_columns = _merge_unique(template_config.get('key_columns', []), key_columns)
        dataframe = dataframe.where(pd.notnull(dataframe), None)
        rows = [_normalize_row(row) for row in dataframe.to_dict(orient='records')]
        columns = [str(column) for column in dataframe.columns]
        checksum_md5 = hashlib.md5(file_bytes).hexdigest()
        row_hashes = [_hash_row(row) for row in rows]

        duplicate_rows_within_file = _duplicate_indexes(row_hashes)
        duplicate_file_sources = list(
            DataSource.objects.filter(checksum_md5=checksum_md5)
            .exclude(uploaded_by=user)
            .values('id', 'name', 'uploaded_by__username', 'created_at')[:5]
        )
        duplicate_file_sources = _normalize_json_value(duplicate_file_sources)
        duplicate_rows_by_key = _duplicate_key_rows(rows, resolved_key_columns)
        validation_errors = _build_validation_errors(
            columns=columns,
            rows=rows,
            required_columns=resolved_required_columns,
            key_columns=resolved_key_columns,
            duplicate_rows_within_file=duplicate_rows_within_file,
            duplicate_rows_by_key=duplicate_rows_by_key,
            duplicate_file_sources=duplicate_file_sources,
            template_config=template_config,
            resolved_mapping=resolved_mapping,
        )
        row_validation_results = _build_row_validation_results(
            rows=rows,
            has_header=has_header,
            required_columns=resolved_required_columns,
            duplicate_rows_by_key=duplicate_rows_by_key,
            business_rules=template_config.get('business_rules', []),
        )

        metadata = {
            'columns': columns,
            'dtypes': {str(column): str(dtype) for column, dtype in dataframe.dtypes.items()},
            'preview_row_count': min(len(rows), 10),
            'schema_profile': _build_schema_profile(dataframe),
            'duplicate_summary': {
                'file_checksum_match_count': len(duplicate_file_sources),
                'duplicate_row_count': len(duplicate_rows_within_file),
                'duplicate_key_count': len(duplicate_rows_by_key),
            },
            'validation_summary': {
                'error_count': len([item for item in validation_errors if item['severity'] == 'error']),
                'warning_count': len([item for item in validation_errors if item['severity'] == 'warning']),
            },
            'required_columns': resolved_required_columns,
            'key_columns': resolved_key_columns,
            'template': {
                'id': template_id,
                'label': template_config.get('label') if template_config else None,
                'dataset_type': template_config.get('dataset_type') if template_config else None,
            },
            'column_mapping': resolved_mapping,
        }

        return {
            'filename': filename,
            'source_type': detected_source_type,
            'delimiter': detected_delimiter,
            'encoding': detected_encoding,
            'checksum_md5': checksum_md5,
            'file_size_bytes': len(file_bytes),
            'row_count': len(rows),
            'column_count': len(columns),
            'rows': rows,
            'columns': columns,
            'metadata': metadata,
            'validation_errors': validation_errors,
            'row_validation_results': row_validation_results,
            'sample_rows': row_validation_results[:10],
        }
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(_build_file_read_error_message(filename, source_type)) from exc


def _load_dataframe(*, filename, source_bytes, source_type, delimiter, encoding, has_header):
    header = 0 if has_header else None
    candidate_types = _ordered_source_type_candidates(filename, source_bytes, source_type)
    last_error = None

    for candidate_type in candidate_types:
        try:
            if candidate_type == 'csv':
                dataframe, resolved_delimiter, resolved_encoding = _read_csv_dataframe(
                    source_bytes=source_bytes,
                    delimiter=delimiter,
                    encoding=encoding,
                    header=header,
                )
                return dataframe, 'csv', resolved_delimiter, resolved_encoding

            if candidate_type == 'json':
                dataframe = _read_json_dataframe(source_bytes=source_bytes, encoding=encoding)
                return dataframe, 'json', delimiter, encoding

            if candidate_type == 'excel':
                dataframe = pd.read_excel(BytesIO(source_bytes), header=header)
                return dataframe, 'excel', delimiter, encoding
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    raise IngestionError(f'Unsupported source_type: {source_type}')


def _load_all_excel_sheets(source_bytes, has_header=True):
    """
    Load all sheets from an Excel file.
    Returns dict: {sheet_name: DataFrame}
    """
    header = 0 if has_header else None
    excel_file = pd.ExcelFile(BytesIO(source_bytes))
    sheets = {}
    for sheet_name in excel_file.sheet_names:
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header)
            if df is not None and not df.empty:
                sheets[sheet_name] = df
        except Exception:
            continue
    return sheets


def _score_excel_sheet(df):
    """
    Score an Excel sheet for data quality (0-100).
    Reuses logic from nettoyage/loader_service.py.
    """
    if df is None or df.empty:
        return 0, 'vide'

    non_empty_rows = int(df.dropna(how='all').shape[0])
    non_empty_cols = int(df.dropna(how='all', axis=1).shape[1])
    total_cells = df.shape[0] * df.shape[1]
    populated_cells = int(df.notna().sum().sum())
    populated_ratio = populated_cells / total_cells if total_cells > 0 else 0

    # Numeric ratio
    numeric_cols = df.select_dtypes(include=['number']).shape[1]
    numeric_ratio = numeric_cols / non_empty_cols if non_empty_cols > 0 else 0

    # Row width consistency
    row_lengths = df.notna().sum(axis=1)
    if len(row_lengths) > 1:
        consistency = 1 - (row_lengths.std() / row_lengths.mean()) if row_lengths.mean() > 0 else 0
        consistency = max(0, min(1, consistency))
    else:
        consistency = 0.5

    score = 0
    score += min(non_empty_rows * 2, 25)
    score += min(non_empty_cols * 4, 24)
    score += populated_ratio * 16
    score += consistency * 18
    score += numeric_ratio * 10
    score += min(3, df.shape[0] // 10)  # bonus for having data rows

    # Classify content type
    if numeric_ratio >= 0.4 and non_empty_cols >= 2:
        content_type = 'tableau_indicateurs'
    elif populated_ratio >= 0.4 and non_empty_cols >= 3:
        content_type = 'jeu_de_donnees_structure'
    elif non_empty_rows <= 3:
        content_type = 'resume_ou_notes'
    else:
        content_type = 'feuille_semistructuree'

    is_data_like = score >= 50 and content_type != 'vide'

    if not is_data_like:
        score = min(score, 30)

    return round(score, 1), content_type


def _analyze_file_bytes_multi_sheet(*, user, filename, file_bytes, source_type, delimiter, encoding, has_header, required_columns, key_columns, template_id, column_mapping):
    """
    Analyze an Excel file and return per-sheet analysis.
    Returns: {sheet_name: analysis_dict} for Excel, or single analysis for other types.
    """
    candidate_types = _ordered_source_type_candidates(filename, file_bytes, source_type)

    # Only Excel gets multi-sheet treatment
    is_excel = any(t == 'excel' for t in candidate_types)

    if not is_excel:
        # Non-Excel: normal single analysis
        analysis = _analyze_file_bytes(
            user=user, filename=filename, file_bytes=file_bytes,
            source_type=source_type, delimiter=delimiter, encoding=encoding,
            has_header=has_header, required_columns=required_columns,
            key_columns=key_columns, template_id=template_id,
            column_mapping=column_mapping,
        )
        return {'__single__': analysis}

    # Excel multi-sheet
    try:
        all_sheets = _load_all_excel_sheets(file_bytes, has_header=has_header)
    except Exception as exc:
        raise IngestionError(f'Cannot read Excel file: {exc}') from exc

    if not all_sheets:
        raise IngestionError('Excel file contains no readable sheets')

    checksum_md5 = hashlib.md5(file_bytes).hexdigest()
    template_config = _resolve_template_config(template_id)

    results = {}
    for sheet_name, dataframe in all_sheets.items():
        try:
            dataframe = _normalize_dataframe_columns(dataframe)
            dataframe, resolved_mapping = _apply_column_mapping(
                dataframe, template_config=template_config, column_mapping=column_mapping
            )
            dataframe = dataframe.where(pd.notnull(dataframe), None)
            rows = [_normalize_row(row) for row in dataframe.to_dict(orient='records')]
            columns = [str(col) for col in dataframe.columns]
            row_hashes = [_hash_row(row) for row in rows]

            row_validation_results = []
            for offset, row in enumerate(rows):
                row_number = (2 if has_header else 1) + offset
                messages = []
                status = 'valid'
                if required_columns:
                    for col in required_columns:
                        if col not in row or row[col] is None:
                            messages.append(f'Missing required column: {col}')
                            status = 'warning'
                if key_columns:
                    key_vals = [row.get(k) for k in key_columns if k in row]
                    if not any(key_vals):
                        messages.append('Empty key column(s)')
                        status = 'warning'
                row_validation_results.append({'row_number': row_number, 'data': row, 'status': status, 'messages': messages})

            quality_score, content_type = _score_excel_sheet(pd.DataFrame(rows) if rows else None)

            results[sheet_name] = {
                'filename': filename,
                'source_type': 'excel',
                'file_size_bytes': len(file_bytes),
                'row_count': len(rows),
                'column_count': len(columns),
                'delimiter': delimiter,
                'encoding': encoding,
                'columns': columns,
                'rows': rows,
                'row_validation_results': row_validation_results,
                'validation_errors': [],
                'checksum_md5': checksum_md5,
                'metadata': {
                    'sheet_name': sheet_name,
                    'quality_score': quality_score,
                    'content_type': content_type,
                    'dtypes': {col: str(dataframe[col].dtype) for col in dataframe.columns if col in dataframe.columns},
                },
            }
        except Exception:
            continue

    return results


def _hash_row(row):
    payload = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
def _normalize_scalar_value(value):
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    # Convert pandas/numpy scalar objects (e.g. int64/float64/bool_) to native Python types.
    if hasattr(value, 'item') and callable(value.item):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')

    return value


def _normalize_json_value(value):
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            normalized[str(key)] = _normalize_json_value(item)
        return normalized

    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]

    return _normalize_scalar_value(value)


def _normalize_row(row):
    return {str(key): _normalize_json_value(value) for key, value in row.items()}


def _get_uploaded_file_bytes(uploaded_file):
    file_bytes = uploaded_file.read()
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    return file_bytes


def _ordered_source_type_candidates(filename, source_bytes, requested_source_type):
    candidates = []
    detected_from_bytes = _infer_source_type_from_bytes(source_bytes)
    detected_from_filename = _infer_source_type_from_filename(filename)

    def add(candidate):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(detected_from_bytes)

    # If the file explicitly looks like Excel/JSON by extension or request,
    # do not silently downgrade it to CSV text when parsing fails.
    if not detected_from_bytes and (requested_source_type in {'excel', 'json'} or detected_from_filename in {'excel', 'json'}):
        add(requested_source_type)
        add(detected_from_filename)
        return candidates

    add(requested_source_type)
    add(detected_from_filename)
    add('csv')
    add('excel')
    add('json')
    return candidates


def _infer_source_type_from_filename(filename):
    normalized = str(filename).lower()
    if normalized.endswith('.csv'):
        return 'csv'
    if normalized.endswith('.xlsx') or normalized.endswith('.xls'):
        return 'excel'
    if normalized.endswith('.json'):
        return 'json'
    return None


def _infer_source_type_from_bytes(source_bytes):
    if source_bytes.startswith(b'PK\x03\x04'):
        return 'excel'
    if source_bytes.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return 'excel'

    stripped = source_bytes.lstrip()
    if stripped.startswith(b'{') or stripped.startswith(b'['):
        return 'json'

    return None


def _read_csv_dataframe(*, source_bytes, delimiter, encoding, header):
    candidate_encodings = [encoding, 'utf-8', 'utf-8-sig', 'cp1252', 'latin-1']
    resolved_encoding = None
    decoded_content = None
    last_error = None

    for candidate_encoding in candidate_encodings:
        if not candidate_encoding or candidate_encoding == resolved_encoding:
            continue
        try:
            decoded_content = source_bytes.decode(candidate_encoding)
            resolved_encoding = candidate_encoding
            break
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    if decoded_content is None or resolved_encoding is None:
        if last_error:
            raise last_error
        raise IngestionError('Impossible de detecter l encodage du CSV.')

    _validate_csv_like_content(decoded_content)
    candidate_delimiters = _build_candidate_delimiters(decoded_content, delimiter)
    last_parse_error = None

    for candidate_delimiter in candidate_delimiters:
        try:
            dataframe = pd.read_csv(
                BytesIO(decoded_content.encode(resolved_encoding)),
                delimiter=candidate_delimiter,
                encoding=resolved_encoding,
                header=header,
            )
            if _looks_like_tabular_csv(decoded_content, dataframe, candidate_delimiter):
                return dataframe, candidate_delimiter, resolved_encoding
        except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
            last_parse_error = exc
            continue

    if last_parse_error:
        raise last_parse_error
    raise IngestionError('Le CSV n a pas pu etre interprete avec un separateur valide.')


def _detect_csv_delimiter(decoded_content, fallback_delimiter):
    sample = '\n'.join(decoded_content.splitlines()[:5]).strip()
    if not sample:
        return fallback_delimiter

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;|\t')
        return dialect.delimiter
    except csv.Error:
        return fallback_delimiter


def _build_candidate_delimiters(decoded_content, fallback_delimiter):
    detected = _detect_csv_delimiter(decoded_content, fallback_delimiter)
    ordered = [detected, fallback_delimiter, ',', ';', '\t', '|']
    seen = set()
    candidates = []
    for item in ordered:
        if not item or item in seen:
            continue
        seen.add(item)
        candidates.append(item)
    return candidates


def _validate_csv_like_content(decoded_content):
    if '\x00' in decoded_content:
        raise IngestionError('Le contenu ne ressemble pas a un CSV texte valide.')

    visible_lines = [line for line in decoded_content.splitlines() if line.strip()]
    if not visible_lines:
        raise IngestionError('Le CSV est vide ou illisible.')

    return None


def _looks_like_tabular_csv(decoded_content, dataframe, delimiter):
    visible_lines = [line for line in decoded_content.splitlines() if line.strip()]
    sample = visible_lines[:5]
    if dataframe.empty and len(dataframe.columns) <= 1 and len(sample) > 1:
        return False

    if len(dataframe.columns) > 1:
        return True

    if len(sample) <= 1:
        return True

    if dataframe.shape[0] >= 1 and len(dataframe.columns) == 1:
        return True

    return any(delimiter in line for line in sample)


def _read_json_dataframe(*, source_bytes, encoding):
    source_stream = BytesIO(source_bytes)
    try:
        return pd.read_json(source_stream)
    except ValueError:
        content = source_bytes.decode(encoding)
        lines = [json.loads(line) for line in content.splitlines() if line.strip()]
        return pd.DataFrame(lines)


def _build_schema_profile(dataframe):
    profile = []
    for column in dataframe.columns:
        series = dataframe[column]
        non_null = series.dropna()
        sample_values = non_null.head(5).tolist()
        normalized_samples = [str(value) for value in sample_values]
        profile.append({
            'name': str(column),
            'dtype': str(series.dtype),
            'null_count': int(series.isna().sum()),
            'non_null_count': int(non_null.shape[0]),
            'unique_count': int(non_null.nunique(dropna=True)),
            'sample_values': normalized_samples,
        })
    return profile


def _build_validation_errors(*, columns, rows, required_columns, key_columns, duplicate_rows_within_file, duplicate_rows_by_key, duplicate_file_sources, template_config, resolved_mapping):
    errors = []
    column_set = set(columns)
    missing_required = [column for column in required_columns if column not in column_set]
    if missing_required:
        errors.append({
            'severity': 'error',
            'code': 'missing_required_columns',
            'message': f"Missing required columns: {', '.join(missing_required)}",
            'details': {'missing_columns': missing_required},
        })

    if duplicate_file_sources:
        errors.append({
            'severity': 'warning',
            'code': 'duplicate_file_detected',
            'message': 'A file with the same checksum already exists.',
            'details': {'matches': duplicate_file_sources},
        })

    if duplicate_rows_within_file:
        errors.append({
            'severity': 'warning',
            'code': 'duplicate_rows_detected',
            'message': 'Duplicate rows were detected within the uploaded file.',
            'details': {'row_numbers': duplicate_rows_within_file[:20], 'count': len(duplicate_rows_within_file)},
        })

    if key_columns and duplicate_rows_by_key:
        errors.append({
            'severity': 'warning',
            'code': 'duplicate_key_rows_detected',
            'message': f"Duplicate key combinations detected for columns: {', '.join(key_columns)}",
            'details': {'row_numbers': sorted(duplicate_rows_by_key.keys())[:20], 'count': len(duplicate_rows_by_key)},
        })

    if not rows:
        errors.append({
            'severity': 'error',
            'code': 'empty_dataset',
            'message': 'The uploaded file does not contain any data rows.',
            'details': {},
        })

    if template_config:
        errors.append({
            'severity': 'info',
            'code': 'template_applied',
            'message': f"Template applied: {template_config['label']}",
            'details': {'column_mapping': resolved_mapping},
        })

    return errors


def _build_row_validation_results(*, rows, has_header, required_columns, duplicate_rows_by_key, business_rules):
    results = []
    start_row_number = 2 if has_header else 1
    for offset, row in enumerate(rows):
        row_number = start_row_number + offset
        messages = []

        missing_values = [column for column in required_columns if row.get(column) in (None, '')]
        if missing_values:
            messages.append({
                'code': 'missing_required_values',
                'message': f"Missing values for required columns: {', '.join(missing_values)}",
            })

        if row_number in duplicate_rows_by_key:
            messages.append({
                'code': 'duplicate_key',
                'message': 'Duplicate key combination detected for this row.',
            })

        messages.extend(_apply_business_rules(row, business_rules))

        results.append({
            'row_number': row_number,
            'data': row,
            'status': _resolve_row_status(messages),
            'messages': messages,
        })

    return results


def _duplicate_indexes(values):
    seen = {}
    duplicates = []
    for index, value in enumerate(values, start=1):
        if value in seen:
            duplicates.append(index)
            if seen[value] not in duplicates:
                duplicates.append(seen[value])
        else:
            seen[value] = index
    return sorted(set(duplicates))


def _duplicate_key_rows(rows, key_columns):
    if not key_columns:
        return {}

    seen = {}
    duplicates = {}
    for index, row in enumerate(rows, start=2):
        key = tuple(row.get(column) for column in key_columns)
        if any(item in (None, '') for item in key):
            continue
        if key in seen:
            duplicates[index] = key
            duplicates.setdefault(seen[key], key)
        else:
            seen[key] = index
    return duplicates


def _build_preview_response(analysis):
    return {
        'filename': analysis['filename'],
        'source_type': analysis['source_type'],
        'delimiter': analysis['delimiter'],
        'encoding': analysis['encoding'],
        'checksum_md5': analysis['checksum_md5'],
        'file_size_bytes': analysis['file_size_bytes'],
        'row_count': analysis['row_count'],
        'column_count': analysis['column_count'],
        'rows': analysis['rows'][:10],
        'columns': analysis['columns'],
        'metadata': analysis['metadata'],
        'validation_errors': analysis['validation_errors'],
        'row_validation_results': analysis['row_validation_results'],
        'sample_rows': analysis['sample_rows'],
        'can_import': not any(error['severity'] == 'error' for error in analysis['validation_errors']),
    }


def _resolve_template_config(template_id):
    if not template_id:
        return {}
    if template_id not in ERP_IMPORT_TEMPLATES:
        raise IngestionError(f'Unknown template_id: {template_id}')
    return ERP_IMPORT_TEMPLATES[template_id]


def _normalize_dataframe_columns(dataframe):
    dataframe = dataframe.copy()
    dataframe.columns = [_canonicalize_column_name(column) for column in dataframe.columns]
    return dataframe


def _apply_column_mapping(dataframe, *, template_config, column_mapping):
    dataframe = dataframe.copy()
    resolved_mapping = {}
    reverse_mapping = {}

    for source_column, target_column in (column_mapping or {}).items():
        normalized_source = _canonicalize_column_name(source_column)
        normalized_target = _canonicalize_column_name(target_column)
        reverse_mapping[normalized_source] = normalized_target

    for canonical_name, aliases in template_config.get('column_aliases', {}).items():
        normalized_canonical = _canonicalize_column_name(canonical_name)
        for alias in aliases:
            normalized_alias = _canonicalize_column_name(alias)
            reverse_mapping.setdefault(normalized_alias, normalized_canonical)

    new_columns = []
    used_columns = set()
    for original_column in dataframe.columns:
        mapped_column = reverse_mapping.get(original_column, original_column)
        final_column = mapped_column
        if final_column in used_columns:
            suffix = 2
            while f'{final_column}_{suffix}' in used_columns:
                suffix += 1
            final_column = f'{final_column}_{suffix}'
        used_columns.add(final_column)
        new_columns.append(final_column)
        if original_column != final_column:
            resolved_mapping[original_column] = final_column

    dataframe.columns = new_columns
    return dataframe, resolved_mapping


def _canonicalize_column_name(value):
    return str(value).strip().lower().replace(' ', '_').replace('-', '_')


def _merge_unique(base_values, extra_values):
    merged = []
    for value in list(base_values) + list(extra_values):
        normalized = _canonicalize_column_name(value)
        if normalized not in merged:
            merged.append(normalized)
    return merged


def _apply_business_rules(row, business_rules):
    messages = []
    for rule in business_rules:
        column = rule.get('column')
        if column not in row:
            continue
        value = row.get(column)
        severity = rule.get('severity', 'warning')
        rule_type = rule.get('type')

        if rule_type == 'required_non_empty' and value in (None, ''):
            messages.append(_rule_message(severity, 'required_non_empty', column, f'Column "{column}" must not be empty.'))

        elif rule_type == 'positive_number' and value not in (None, ''):
            numeric = _to_float(value)
            if numeric is None or numeric <= 0:
                messages.append(_rule_message(severity, 'positive_number', column, f'Column "{column}" must be a positive number.'))

        elif rule_type == 'non_negative_number' and value not in (None, ''):
            numeric = _to_float(value)
            if numeric is None or numeric < 0:
                messages.append(_rule_message(severity, 'non_negative_number', column, f'Column "{column}" must be a non-negative number.'))

        elif rule_type == 'allowed_values' and value not in (None, ''):
            allowed_values = rule.get('values', [])
            case_insensitive = rule.get('case_insensitive', False)
            if case_insensitive:
                allowed_normalized = {str(item).lower() for item in allowed_values}
                value_normalized = str(value).lower()
                if value_normalized not in allowed_normalized:
                    messages.append(_rule_message(severity, 'allowed_values', column, f'Column "{column}" has an unexpected value "{value}".'))
            elif value not in allowed_values:
                messages.append(_rule_message(severity, 'allowed_values', column, f'Column "{column}" has an unexpected value "{value}".'))

        elif rule_type == 'date_parseable' and value not in (None, ''):
            parsed_date = pd.to_datetime(value, errors='coerce')
            if pd.isna(parsed_date):
                messages.append(_rule_message(severity, 'date_parseable', column, f'Column "{column}" must contain a valid date.'))

    return messages


def _rule_message(severity, code, column, message):
    return {
        'severity': severity,
        'code': code,
        'column': column,
        'message': message,
    }


def _resolve_row_status(messages):
    if any(item.get('severity') == 'error' for item in messages):
        return 'invalid'
    if messages:
        return 'warning'
    return 'valid'


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_file_read_error_message(filename, source_type):
    if source_type == 'csv':
        return (
            f'CSV invalide pour "{filename}". '
            'Verifie le separateur, l encodage et la structure des colonnes.'
        )
    if source_type == 'excel':
        return (
            f'Fichier Excel corrompu ou illisible pour "{filename}". '
            'Verifie que le classeur .xls/.xlsx est valide et non endommage.'
        )
    if source_type == 'json':
        return (
            f'JSON invalide pour "{filename}". '
            'Verifie que le contenu est bien un JSON lisible.'
        )
    return (
        f'Impossible de lire "{filename}". '
        'Verifie que le format du fichier correspond bien a son extension.'
    )


def suggest_relations(source):
    """
    Analyze sheets in a multi-sheet DataSource and suggest possible relationships.
    Returns a list of dicts: {from_sheet, from_column, to_sheet, to_column, confidence, match_ratio, reason}
    """
    # Get sheet names from DB or metadata fallback
    db_sheet_names = list(DataSourceSheet.objects.filter(source=source).order_by('sheet_index').values_list('sheet_name', flat=True))
    meta_sheet_names = (source.metadata or {}).get('sheet_names', [])
    all_sheet_names = db_sheet_names if db_sheet_names else meta_sheet_names

    if len(all_sheet_names) < 2:
        return []

    sheet_dataframes = {}
    for sheet_name in all_sheet_names:
        raw_rows = RawData.objects.filter(source=source, sheet_name=sheet_name).order_by('row_number')[:500]
        if not raw_rows.exists():
            continue
        rows = [r.data for r in raw_rows]
        if rows:
            sheet_dataframes[sheet_name] = pd.DataFrame(rows)

    if len(sheet_dataframes) < 2:
        return []

    suggestions = []
    sheet_names = list(sheet_dataframes.keys())

    for i, name_a in enumerate(sheet_names):
        df_a = sheet_dataframes[name_a]
        cols_a = set(df_a.columns)

        for j, name_b in enumerate(sheet_names):
            if i >= j:
                continue
            df_b = sheet_dataframes[name_b]
            cols_b = set(df_b.columns)

            for col_a in cols_a:
                for col_b in cols_b:
                    suggestion = _evaluate_pair(name_a, df_a, col_a, name_b, df_b, col_b)
                    if suggestion:
                        suggestions.append(suggestion)

                    suggestion_rev = _evaluate_pair(name_b, df_b, col_b, name_a, df_a, col_a)
                    if suggestion_rev:
                        suggestions.append(suggestion_rev)

    suggestions.sort(key=lambda s: s['confidence'], reverse=True)

    seen = set()
    unique = []
    for s in suggestions:
        key = (s['from_sheet'], s['from_column'], s['to_sheet'], s['to_column'])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _evaluate_pair(from_name, df_from, from_col, to_name, df_to, to_col):
    """Evaluate if from_col in sheet_from could be a FK to to_col in sheet_to.
    
    Scoring strategy: VALUE OVERLAP is the primary signal (not column names).
    Two columns with completely different names but 100% value overlap
    should still be detected as a strong relationship.
    """
    vals_from = df_from[from_col].dropna()
    vals_to = df_to[to_col].dropna()

    if len(vals_from) == 0 or len(vals_to) == 0:
        return None

    from_set = set(vals_from.astype(str).unique())
    to_set = set(vals_to.astype(str).unique())

    if not from_set or not to_set:
        return None

    matched = from_set & to_set
    match_ratio = len(matched) / len(from_set) if from_set else 0

    if match_ratio < 0.5:
        return None

    confidence = 0.0
    reasons = []

    # === PRIMARY SIGNAL: VALUE OVERLAP ===
    # This is the most important factor — noms importent peu ici
    is_subset = from_set.issubset(to_set)
    is_superset = to_set.issubset(from_set)
    is_equal = from_set == to_set

    if is_equal:
        confidence += 0.55
        reasons.append(f'{match_ratio:.0%} value match (identical sets)')
    elif is_subset:
        # FK → PK pattern: all values from 'from' exist in 'to'
        confidence += 0.50
        reasons.append(f'{match_ratio:.0%} value coverage (subset)')
    elif is_superset:
        confidence += 0.45
        reasons.append(f'{match_ratio:.0%} value coverage (superset)')
    elif match_ratio >= 0.95:
        confidence += 0.45
        reasons.append(f'{match_ratio:.0%} value coverage')
    elif match_ratio >= 0.80:
        confidence += 0.35
        reasons.append(f'{match_ratio:.0%} value coverage')
    elif match_ratio >= 0.60:
        confidence += 0.20
        reasons.append(f'{match_ratio:.0%} value coverage')
    else:
        confidence += 0.10
        reasons.append(f'{match_ratio:.0%} value coverage')

    # === SECONDARY: CARDINALITY MATCH ===
    # Same number of unique values = strong structural hint
    from_count = len(from_set)
    to_count = len(to_set)
    if from_count == to_count:
        confidence += 0.15
        reasons.append('same cardinality')
    elif from_count > 0 and to_count > 0:
        ratio = min(from_count, to_count) / max(from_count, to_count)
        if ratio >= 0.8:
            confidence += 0.10
            reasons.append(f'similar cardinality ({from_count} vs {to_count})')

    # === BONUS: NAME SIMILARITY ===
    # Bonus — not required for detection
    from_lower = from_col.lower().strip()
    to_lower = to_col.lower().strip()

    if from_lower == to_lower:
        confidence += 0.15
        reasons.append('same column name')
    elif from_lower in to_lower or to_lower in from_lower:
        confidence += 0.10
        reasons.append('column name overlap')
    else:
        # Simple Levenshtein-like check
        dist = _simple_edit_distance(from_lower, to_lower)
        max_len = max(len(from_lower), len(to_lower))
        if max_len > 0 and dist <= 3 and dist / max_len < 0.4:
            confidence += 0.05
            reasons.append(f'similar names (dist={dist})')

    # === BONUS: TYPE COMPATIBILITY ===
    try:
        from_numeric = pd.to_numeric(vals_from, errors='coerce').dropna()
        to_numeric = pd.to_numeric(vals_to, errors='coerce').dropna()
        if len(from_numeric) > 0 and len(to_numeric) > 0:
            confidence += 0.05
            reasons.append('numeric type match')
    except Exception:
        pass

    if confidence < 0.3:
        return None

    return {
        'from_sheet': from_name,
        'from_column': from_col,
        'to_sheet': to_name,
        'to_column': to_col,
        'confidence': round(min(confidence, 1.0), 2),
        'match_ratio': round(match_ratio, 2),
        'reason': ' + '.join(reasons),
    }


def _simple_edit_distance(s1, s2):
    """Simple Levenshtein distance for short strings."""
    if len(s1) > 30 or len(s2) > 30:
        return 99
    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def build_joined_view(source, sheet_names=None, relation_ids=None):
    """
    Build a unified view by joining sheets based on defined relations.
    Returns: {columns: [...], rows: [...], relations_used: [...], join_stats: {...}}
    """
    from apps.ingestion.models import SheetRelation

    relations = SheetRelation.objects.filter(source=source, is_active=True)
    if relation_ids:
        relations = relations.filter(id__in=relation_ids)

    if not relations.exists():
        return _build_flat_view(source, sheet_names)

    sheets_to_load = sheet_names or list(
        relations.values_list('from_sheet', flat=True).union(
            relations.values_list('to_sheet', flat=True)
        )
    )

    sheet_dataframes = {}
    for sheet_name in sheets_to_load:
        raw_rows = RawData.objects.filter(source=source, sheet_name=sheet_name).order_by('row_number')
        if raw_rows.exists():
            df = pd.DataFrame([r.data for r in raw_rows])
            df['_sheet_name'] = sheet_name
            df['_row_id'] = raw_rows.values_list('id', flat=True)
            df['_row_number'] = raw_rows.values_list('row_number', flat=True)
            sheet_dataframes[sheet_name] = df

    if not sheet_dataframes:
        return {'columns': [], 'rows': [], 'relations_used': [], 'join_stats': {}}

    relations_used = []
    join_stats = {'matched': 0, 'unmatched_source': 0, 'unmatched_target': 0}

    sorted_rels = sorted(relations, key=lambda r: _topological_sort_key(r, relations))

    result_df = None
    for rel in sorted_rels:
        df_from = sheet_dataframes.get(rel.from_sheet)
        df_to = sheet_dataframes.get(rel.to_sheet)

        if df_from is None or df_to is None:
            continue

        left = result_df if result_df is not None and rel.from_sheet in (result_df['_sheet_name'].unique() if '_sheet_name' in result_df.columns else []) else df_from

        merged = left.merge(
            df_to,
            left_on=rel.from_column,
            right_on=rel.to_column,
            how='left',
            suffixes=('', f'_{rel.to_sheet}'),
            indicator=True,
        )

        matched_count = (merged['_merge'] == 'both').sum()
        unmatched_source = (merged['_merge'] == 'left_only').sum()
        join_stats['matched'] += int(matched_count)
        join_stats['unmatched_source'] += int(unmatched_source)

        merged.drop(columns=['_merge'], inplace=True)
        result_df = merged
        relations_used.append(f'{rel.from_sheet}.{rel.from_column} → {rel.to_sheet}.{rel.to_column}')

    if result_df is None:
        return {'columns': [], 'rows': [], 'relations_used': [], 'join_stats': {}}

    display_cols = [c for c in result_df.columns if not c.startswith('_merge')]
    rows = result_df[display_cols].fillna('').to_dict(orient='records')

    return {
        'columns': display_cols,
        'rows': rows,
        'relations_used': relations_used,
        'join_stats': join_stats,
        'total_rows': len(rows),
    }


def _build_flat_view(source, sheet_names=None):
    """Fallback: concatenate all rows without joins."""
    qs = RawData.objects.filter(source=source)
    if sheet_names:
        qs = qs.filter(sheet_name__in=sheet_names)

    rows_data = list(qs.values_list('data', flat=True).order_by('sheet_name', 'row_number'))
    if not rows_data:
        return {'columns': [], 'rows': [], 'relations_used': [], 'join_stats': {}}

    all_cols = set()
    for row in rows_data:
        all_cols.update(row.keys())
    columns = sorted(all_cols)

    return {
        'columns': columns,
        'rows': rows_data,
        'relations_used': [],
        'join_stats': {'total_rows': len(rows_data)},
        'total_rows': len(rows_data),
    }


def _topological_sort_key(relation, all_relations):
    """Simple topological sort: target sheets come before source sheets."""
    targets = set(r.to_sheet for r in all_relations)
    if relation.from_sheet in targets:
        return 0
    return 1
