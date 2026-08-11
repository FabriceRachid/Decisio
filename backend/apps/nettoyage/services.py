import re
import time

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.utils import timezone

# Optional fuzzy matching support (non-fatal if missing)
try:
    from thefuzz import fuzz
except Exception:
    fuzz = None

from apps.ingestion.models import DataSource
from apps.nettoyage.engine import NettoyagePipeline
from apps.nettoyage.models import CleanedData, CleaningJob, CleaningPipeline, CleaningRule


class CleaningError(Exception):
    """Raised when cleaning cannot proceed."""


def _run_intelligent_engine(*, source, user=None, decision_overrides=None):
    user_id = getattr(user, 'id', None)
    cleaned_dataframe, cleaning_report = NettoyagePipeline(source=source, user_id=user_id).analyze_source(
        decision_overrides=decision_overrides or [],
    )
    return cleaned_dataframe, cleaning_report


def preview_cleaning(*, source, user, pipeline_id, rule_ids, include_all_auto_rules, quality_gate, decision_overrides=None):
    pipeline, rules, effective_quality_gate = _resolve_execution_plan(
        source=source,
        user=user,
        pipeline_id=pipeline_id,
        rule_ids=rule_ids,
        include_all_auto_rules=include_all_auto_rules,
        quality_gate=quality_gate,
    )
    default_pipeline = _select_default_pipeline(source) if not pipeline else None
    original_dataframe = _load_source_dataframe(source)
    if rule_ids and not include_all_auto_rules and not pipeline_id and not decision_overrides:
        result = _apply_rules(dataframe=original_dataframe, rules=rules, quality_gate=effective_quality_gate)
        _, cleaning_report = _run_intelligent_engine(source=source, user=user, decision_overrides=decision_overrides or [])
    else:
        cleaned_dataframe, cleaning_report = _run_intelligent_engine(source=source, user=user, decision_overrides=decision_overrides or [])
        cleaned_dataframe, cleaning_report = _apply_engine_decisions(
            cleaned_dataframe=cleaned_dataframe,
            cleaning_report=cleaning_report,
            decision_overrides=decision_overrides or [],
        )
        result = _build_engine_preview_result(
            original_dataframe=original_dataframe,
            cleaned_dataframe=cleaned_dataframe,
            cleaning_report=cleaning_report,
            quality_gate=effective_quality_gate,
        )

    return {
        'source_id': source.id,
        'source_name': source.name,
        'pipeline': _serialize_pipeline(pipeline) if pipeline else None,
        'recommended_pipeline': _serialize_pipeline(default_pipeline) if default_pipeline else None,
        'rules_applied': [_serialize_rule(rule) for rule in rules],
        'summary': result['summary'],
        'column_profile': result['column_profile'],
        'sample_rows': result['sample_rows'],
        'diff_samples': result['diff_samples'],
        'validation_issues': result['validation_issues'],
        'business_summary': _build_business_summary(result['summary'], result['validation_issues']),
        'quality_gate': effective_quality_gate,
        'cleaning_report': cleaning_report,
    }


def apply_cleaning(*, source, user, pipeline_id, rule_ids, include_all_auto_rules, quality_gate, decision_overrides=None):
    pipeline, rules, effective_quality_gate = _resolve_execution_plan(
        source=source,
        user=user,
        pipeline_id=pipeline_id,
        rule_ids=rule_ids,
        include_all_auto_rules=include_all_auto_rules,
        quality_gate=quality_gate,
    )
    dataframe = _load_source_dataframe(source)

    if not rules:
        raise CleaningError(
            _build_no_rules_message(
                source=source,
                pipeline=pipeline,
                rule_ids=rule_ids,
                include_all_auto_rules=include_all_auto_rules,
            )
        )

    started_at = timezone.now()
    start_time = time.perf_counter()
    with transaction.atomic():
        job = CleaningJob.objects.create(
            source=source,
            created_by=user,
            rule=rules[0] if rules else None,
            status='running',
            total_rows=len(dataframe),
            started_at=started_at,
            execution_context={
                'source_id': source.id,
                'pipeline': _serialize_pipeline(pipeline) if pipeline else None,
                'rule_ids': [item.id for item in rules],
                'resolved_rules': [_serialize_rule(item) for item in rules],
                'include_all_auto_rules': include_all_auto_rules,
                'quality_gate': effective_quality_gate,
                'decision_overrides': decision_overrides or [],
                'mode': 'engine_pipeline',
            },
        )

        try:
            has_structural_rules = pipeline is not None and rules and any(
                r.rule_type in ('unpivot', 'cell_level_transformation', 'remove_empty_rows', 'drop_columns_by_missing_threshold', 'validate_format', 'rename_columns', 'extract_subtables', 'fix_ambiguous_chars', 'extract_labeled_fields', 'split_value_unit', 'explode_delimited_list')
                for r in rules
            )
            use_rules_path = has_structural_rules or (rule_ids and not include_all_auto_rules and not pipeline_id and not decision_overrides)
            if use_rules_path:
                legacy_result = _apply_rules(
                    dataframe=dataframe,
                    rules=rules,
                    quality_gate=effective_quality_gate,
                )
                cleaned_dataframe = legacy_result['dataframe']
                validation_issues = legacy_result['validation_issues']
                cleaning_report = {
                    'mapping': {'colonnes_mappees': [], 'colonnes_non_mappees': []},
                    'corrections': [],
                    'alertes': [
                        {
                            'regle': issue.get('rule'),
                            'severite': issue.get('code'),
                            'message': issue.get('message'),
                            'lignes': issue.get('row_numbers', []),
                        }
                        for issue in validation_issues
                    ],
                    'score_detail': {},
                    'metadata': {
                        'mode_application': 'structural_rules' if has_structural_rules else 'rules_only',
                        'resume_executif': {
                            'statut': 'SUCCES',
                            'problemes_principaux': [],
                            'corrections_principales': [],
                            'impact_lignes': {
                                'initiales': len(dataframe),
                                'finales': len(cleaned_dataframe),
                                'ecart': len(dataframe) - len(cleaned_dataframe),
                            },
                        },
                    },
                    'lignes_initiales': len(dataframe),
                    'lignes_finales': len(cleaned_dataframe),
                    'colonnes_initiales': len([column for column in dataframe.columns if column != '_row_number']),
                    'colonnes_finales': len([column for column in cleaned_dataframe.columns if column != '_row_number']),
                    'score_qualite': _average_quality_score(cleaned_dataframe),
                    'statut': 'SUCCES',
                    'duree_traitement_ms': 0,
                }
            else:
                cleaned_dataframe, cleaning_report = _run_intelligent_engine(
                    source=source,
                    user=user,
                    decision_overrides=decision_overrides or [],
                )
                cleaned_dataframe, cleaning_report = _apply_engine_decisions(
                    cleaned_dataframe=cleaned_dataframe,
                    cleaning_report=cleaning_report,
                    decision_overrides=decision_overrides or [],
                )
                validation_issues = _extract_validation_issues_from_engine_report(cleaning_report)
            quality_gate_failure = _evaluate_quality_gate(
                dataframe=cleaned_dataframe,
                validation_issues=validation_issues,
                quality_gate=effective_quality_gate,
            )
            if quality_gate_failure:
                raise CleaningError(quality_gate_failure)

            quality_scores = _calculate_quality_scores(cleaned_dataframe)
            changes_by_row = _build_changes_by_row_from_dataframes(dataframe, cleaned_dataframe)
            _persist_cleaned_results(
                job=job,
                source=source,
                dataframe=cleaned_dataframe,
                quality_scores=quality_scores,
                changes_by_row=changes_by_row,
                cleaning_report=cleaning_report,
            )

            rows_processed = len(cleaned_dataframe)
            rows_skipped = 0
            rows_failed = 0
            rows_affected = _count_rows_affected(changes_by_row, dataframe, cleaned_dataframe)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            job.status = 'completed'
            job.rows_processed = rows_processed
            job.rows_affected = rows_affected
            job.rows_skipped = rows_skipped
            job.rows_failed = rows_failed
            job.progress_percent = 100
            job.completed_at = timezone.now()
            job.duration_ms = duration_ms
            job.error_message = None
            job.execution_context = {
                **(job.execution_context or {}),
                'cleaning_report': _json_safe(cleaning_report),
            }
            job.save()

        except CleaningError as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job.status = 'failed'
            job.rows_processed = 0
            job.rows_failed = len(dataframe)
            job.progress_percent = 0
            job.completed_at = timezone.now()
            job.duration_ms = duration_ms
            job.error_message = str(exc)
            job.save()
            raise
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job.status = 'failed'
            job.rows_processed = 0
            job.rows_failed = len(dataframe)
            job.progress_percent = 0
            job.completed_at = timezone.now()
            job.duration_ms = duration_ms
            job.error_message = str(exc)
            job.save()
            raise CleaningError(str(exc)) from exc

    cleaned_results = job.cleaned_results.select_related('original_data').order_by('original_data__row_number')

    return {
        'source_id': source.id,
        'source_name': source.name,
        'job_id': job.id,
        'pipeline': _serialize_pipeline(pipeline) if pipeline else None,
        'rules_applied': [_serialize_rule(rule) for rule in rules],
        'summary': {
            'rows_processed': job.rows_processed,
            'rows_affected': job.rows_affected,
            'rows_skipped': job.rows_skipped,
            'rows_failed': job.rows_failed,
        },
        'business_summary': _build_business_summary(
            {
                'row_count': len(cleaned_dataframe),
                'column_count': len([column for column in cleaned_dataframe.columns if column != '_row_number']),
                'rows_processed': job.rows_processed,
                'rows_affected': job.rows_affected,
                'rows_skipped': job.rows_skipped,
                'rows_failed': job.rows_failed,
                'missing_value_rate': _summarize_dataframe(cleaned_dataframe)['missing_value_rate'],
            },
            _extract_validation_issues_from_engine_report(cleaning_report),
        ),
        'quality_gate': effective_quality_gate,
        'sample_rows': [
            {
                'row_number': item.original_data.row_number if item.original_data else None,
                'data': item.data,
                'changes_made': item.changes_made,
                'quality_score': float(item.quality_score or 0),
            }
            for item in cleaned_results[:10]
        ],
        'cleaning_report': cleaning_report,
    }


def apply_cleaning_multi_sheet(*, source, user, pipeline_id, rule_ids, include_all_auto_rules, quality_gate, decision_overrides=None):
    """
    Apply cleaning to all sheets of a multi-sheet Excel source.
    Returns per-sheet results.
    """
    sheets_df = _load_all_sheets_as_dataframes(source)
    if len(sheets_df) <= 1:
        return apply_cleaning(
            source=source, user=user, pipeline_id=pipeline_id,
            rule_ids=rule_ids, include_all_auto_rules=include_all_auto_rules,
            quality_gate=quality_gate, decision_overrides=decision_overrides,
        )

    pipeline, rules, effective_quality_gate = _resolve_execution_plan(
        source=source, user=user, pipeline_id=pipeline_id,
        rule_ids=rule_ids, include_all_auto_rules=include_all_auto_rules,
        quality_gate=quality_gate,
    )

    if not rules:
        raise CleaningError(
            _build_no_rules_message(
                source=source, pipeline=pipeline,
                rule_ids=rule_ids, include_all_auto_rules=include_all_auto_rules,
            )
        )

    sheet_results = {}
    total_affected = 0
    total_processed = 0

    for sheet_name, dataframe in sheets_df.items():
        started_at = timezone.now()
        start_time = time.perf_counter()
        with transaction.atomic():
            job = CleaningJob.objects.create(
                source=source,
                created_by=user,
                rule=rules[0] if rules else None,
                status='running',
                total_rows=len(dataframe),
                started_at=started_at,
                execution_context={
                    'source_id': source.id,
                    'sheet_name': sheet_name,
                    'pipeline': _serialize_pipeline(pipeline) if pipeline else None,
                    'rule_ids': [item.id for item in rules],
                    'resolved_rules': [_serialize_rule(item) for item in rules],
                    'include_all_auto_rules': include_all_auto_rules,
                    'quality_gate': effective_quality_gate,
                    'decision_overrides': decision_overrides or [],
                    'mode': 'multi_sheet_engine_pipeline',
                },
            )

            try:
                if rule_ids and not include_all_auto_rules and not pipeline_id and not decision_overrides:
                    legacy_result = _apply_rules(dataframe=dataframe, rules=rules, quality_gate=effective_quality_gate)
                    cleaned_dataframe = legacy_result['dataframe']
                    validation_issues = legacy_result['validation_issues']
                    cleaning_report = {
                        'mapping': {'colonnes_mappees': [], 'colonnes_non_mappees': []},
                        'corrections': [],
                        'alertes': [
                            {'regle': issue.get('rule'), 'severite': issue.get('code'), 'message': issue.get('message'), 'lignes': issue.get('row_numbers', [])}
                            for issue in validation_issues
                        ],
                        'score_detail': {},
                        'metadata': {
                            'mode_application': 'rules_only',
                            'lignes_initiales': len(dataframe),
                            'lignes_finales': len(cleaned_dataframe),
                            'score_qualite': _average_quality_score(cleaned_dataframe),
                            'statut': 'SUCCES',
                        },
                    }
                else:
                    cleaned_dataframe, cleaning_report = _run_intelligent_engine(
                        source=source, user=user, decision_overrides=decision_overrides or [],
                    )
                    cleaned_dataframe, cleaning_report = _apply_engine_decisions(
                        cleaned_dataframe=cleaned_dataframe, cleaning_report=cleaning_report,
                        decision_overrides=decision_overrides or [],
                    )
                    validation_issues = _extract_validation_issues_from_engine_report(cleaning_report)

                quality_scores = _calculate_quality_scores(cleaned_dataframe)
                changes_by_row = _build_changes_by_row_from_dataframes(dataframe, cleaned_dataframe)
                _persist_cleaned_results(
                    job=job, source=source, dataframe=cleaned_dataframe,
                    quality_scores=quality_scores, changes_by_row=changes_by_row,
                    cleaning_report=cleaning_report,
                )

                rows_affected = _count_rows_affected(changes_by_row, dataframe, cleaned_dataframe)
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                job.status = 'completed'
                job.rows_processed = len(cleaned_dataframe)
                job.rows_affected = rows_affected
                job.progress_percent = 100
                job.completed_at = timezone.now()
                job.duration_ms = duration_ms
                job.execution_context = {**(job.execution_context or {}), 'cleaning_report': _json_safe(cleaning_report)}
                job.save()

                total_affected += rows_affected
                total_processed += len(cleaned_dataframe)

                sheet_results[sheet_name] = {
                    'status': 'completed',
                    'job_id': job.id,
                    'rows_initial': len(dataframe),
                    'rows_final': len(cleaned_dataframe),
                    'rows_affected': rows_affected,
                    'duration_ms': duration_ms,
                    'quality_scores': quality_scores,
                    'business_summary': _build_business_summary(
                        {'row_count': len(cleaned_dataframe), 'column_count': len([c for c in cleaned_dataframe.columns if c != '_row_number']),
                         'rows_processed': len(cleaned_dataframe), 'rows_affected': rows_affected, 'rows_skipped': 0, 'rows_failed': 0,
                         'missing_value_rate': _summarize_dataframe(cleaned_dataframe)['missing_value_rate']},
                        validation_issues,
                    ),
                    'cleaning_report': cleaning_report,
                }
            except (CleaningError, Exception) as exc:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                job.status = 'failed'
                job.rows_processed = 0
                job.rows_failed = len(dataframe)
                job.completed_at = timezone.now()
                job.duration_ms = duration_ms
                job.error_message = str(exc)
                job.save()
                sheet_results[sheet_name] = {'status': 'failed', 'error': str(exc), 'rows_initial': len(dataframe)}

    return {
        'source_id': source.id,
        'source_name': source.name,
        'multi_sheet': True,
        'sheet_count': len(sheet_results),
        'total_rows_processed': total_processed,
        'total_rows_affected': total_affected,
        'sheets': sheet_results,
    }


def suggest_cleaning(*, source):
    has_sheets = source.sheets.exists()
    if has_sheets:
        sheets_df = _load_all_sheets_as_dataframes(source)
        dataframe = next(iter(sheets_df.values()), None)
    else:
        dataframe = _load_source_dataframe(source)
    if dataframe is None or dataframe.empty:
        return {'suggestions': [], 'detected_issues': [], 'summary': {}}
    data_columns = _data_columns(dataframe)
    missing_matrix = _missing_like_matrix(dataframe, data_columns)
    suggestions = []
    detected_issues = []
    _, cleaning_report = _run_intelligent_engine(source=source)

    empty_row_numbers = []
    if data_columns:
        empty_row_numbers = dataframe.loc[missing_matrix.all(axis=1), '_row_number'].astype(int).tolist()
    if empty_row_numbers:
        detected_issues.append({
            'code': 'empty_rows_detected',
            'message': f'{len(empty_row_numbers)} empty or whitespace-only rows were detected.',
            'row_numbers': empty_row_numbers[:20],
        })
        suggestions.append({
            'rule_type': 'remove_empty_rows',
            'reason': 'Remove rows that do not contain usable values.',
            'suggested_parameters': {},
            'priority': 10,
        })

    for column in data_columns:
        series = dataframe[column]
        missing_rate = float(missing_matrix[column].mean()) if len(series) else 0
        if missing_rate >= 0.2:
            detected_issues.append({
                'code': 'high_missing_rate',
                'column': column,
                'message': f'Column "{column}" has a missing-value rate of {round(missing_rate * 100, 2)}%.',
            })
            suggestions.append({
                'rule_type': 'fill_mode',
                'column_names': [column],
                'reason': 'Fill repeated categorical gaps with the most common value.',
                'suggested_parameters': {},
                'priority': 8,
            })
        whitespace_mask = (
            series.notna()
            & ~_string_empty_mask(series)
            & series.astype('string').ne(series.astype('string').str.strip())
        )
        if bool(whitespace_mask.any()):
            suggestions.append({
                'rule_type': 'standardize',
                'column_names': [column],
                'reason': 'Trim and standardize text values with leading or trailing whitespace.',
                'suggested_parameters': {'mode': 'trim'},
                'priority': 7,
            })

        duplicate_ratio = series.astype(str).value_counts(normalize=True, dropna=True)
        if not duplicate_ratio.empty and duplicate_ratio.iloc[0] > 0.9 and len(series) > 3:
            detected_issues.append({
                'code': 'low_cardinality_column',
                'column': column,
                'message': f'Column "{column}" is dominated by one repeated value and may need validation.',
            })

    duplicate_count = int(dataframe.duplicated(subset=data_columns, keep='first').sum()) if data_columns else 0
    if duplicate_count:
        detected_issues.append({
            'code': 'duplicate_rows_detected',
            'message': f'{duplicate_count} duplicate rows were detected.',
        })
        suggestions.append({
            'rule_type': 'remove_duplicates',
            'column_names': data_columns,
            'reason': 'Remove exact duplicate rows before downstream analysis.',
            'suggested_parameters': {},
            'priority': 9,
        })

    recommended_pipeline = _select_default_pipeline(source)
    engine_detected_issues = _extract_detected_issues_from_engine_report(cleaning_report)
    engine_suggestions = _extract_suggestions_from_engine_report(cleaning_report)

    # Fuzzy mapping suggestions: if the source includes a canonical column list in metadata,
    # propose best fuzzy matches for unmapped columns. This is best-effort and must not
    # interrupt the pipeline if thefuzz is not available.
    fuzzy_suggestions = {}
    try:
        canonical_columns = source.metadata.get('canonical_columns') if getattr(source, 'metadata', None) else []
        if canonical_columns and fuzz:
            source_cols = _data_columns(dataframe)
            fuzzy_suggestions = _fuzzy_suggest_matches(source_cols, canonical_columns)
    except Exception:
        fuzzy_suggestions = {}

    return {
        'source_id': source.id,
        'source_name': source.name,
        'recommended_pipeline': _serialize_pipeline(recommended_pipeline) if recommended_pipeline else None,
        'detected_issues': _merge_detected_issues(detected_issues, engine_detected_issues),
        'suggested_rules': _deduplicate_suggestions(suggestions + engine_suggestions),
        'business_summary': _build_suggestion_summary(_merge_detected_issues(detected_issues, engine_detected_issues)),
        'mapping': cleaning_report.get('mapping', {'colonnes_mappees': [], 'colonnes_non_mappees': []}),
        'fuzzy_mapping_suggestions': fuzzy_suggestions,
        'alertes': cleaning_report.get('alertes', []),
        'score_detail': cleaning_report.get('score_detail', {}),
        'cleaning_report': cleaning_report,
    }


def get_cleaning_job_detail(*, job):
    cleaned_results = list(
        job.cleaned_results.select_related('original_data', 'validated_by').order_by('original_data__row_number')[:20]
    )
    validated_count = job.cleaned_results.filter(is_validated=True).count()
    total_count = job.cleaned_results.count()
    issue_counts = {}
    for item in cleaned_results:
        for change in item.changes_made:
            action = change.get('action', 'updated')
            issue_counts[action] = issue_counts.get(action, 0) + 1

    return {
        'job': {
            'id': job.id,
            'status': job.status,
            'source_id': job.source_id,
            'source_name': job.source.name,
            'rule_id': job.rule_id,
            'rule_name': job.rule.name if job.rule else None,
            'created_at': job.created_at,
            'completed_at': job.completed_at,
            'export_path': job.export_path,
            'execution_context': job.execution_context,
        },
        'validation_summary': {
            'validated_rows': validated_count,
            'pending_rows': max(total_count - validated_count, 0),
            'validation_rate': round((validated_count / total_count) * 100, 2) if total_count else 0,
        },
        'change_summary': issue_counts,
        'sample_rows': [
            {
                'id': item.id,
                'row_number': item.original_data.row_number if item.original_data else None,
                'data': item.data,
                'changes_made': item.changes_made,
                'quality_score': float(item.quality_score or 0),
                'is_validated': item.is_validated,
                'validated_by': item.validated_by.username if item.validated_by else None,
                'validation_notes': item.validation_notes,
            }
            for item in cleaned_results
        ],
    }


def replay_cleaning(*, job, user):
    execution_context = job.execution_context or {}
    return apply_cleaning(
        source=job.source,
        user=user,
        pipeline_id=(execution_context.get('pipeline') or {}).get('id'),
        rule_ids=execution_context.get('rule_ids', [job.rule_id]),
        include_all_auto_rules=execution_context.get('include_all_auto_rules', False),
        quality_gate=execution_context.get('quality_gate', {}),
        decision_overrides=execution_context.get('decision_overrides', []),
    )


def validate_cleaning_job(*, job, user, is_validated, validation_notes):
    updated_count = job.cleaned_results.update(
        is_validated=is_validated,
        validated_by_id=user.id if is_validated else None,
        validation_notes=validation_notes,
    )
    return {
        'job_id': job.id,
        'validated_rows': updated_count if is_validated else 0,
        'unvalidated_rows': updated_count if not is_validated else 0,
        'is_validated': is_validated,
        'validation_notes': validation_notes,
    }


def _resolve_execution_plan(*, source, user, pipeline_id, rule_ids, include_all_auto_rules, quality_gate):
    pipeline = None
    pipeline_rules = []
    effective_quality_gate = quality_gate or {}

    if pipeline_id:
        pipeline = CleaningPipeline.objects.filter(id=pipeline_id, is_active=True).first()
        if not pipeline:
            raise CleaningError('The selected cleaning pipeline does not exist or is inactive.')
        if pipeline.source_type_scope and pipeline.source_type_scope != source.source_type:
            raise CleaningError('The selected pipeline is not applicable to this source type.')
        pipeline_rules = list(pipeline.rules.filter(is_active=True).order_by('-priority', 'id'))
        if rule_ids:
            selected_rule_ids = {int(rule_id) for rule_id in rule_ids}
            pipeline_rules = [rule for rule in pipeline_rules if rule.id in selected_rule_ids]
        effective_quality_gate = {**pipeline.quality_gate, **effective_quality_gate}
    elif not rule_ids and not include_all_auto_rules:
        pipeline = _select_default_pipeline(source)
        if pipeline:
            pipeline_rules = list(pipeline.rules.filter(is_active=True).order_by('-priority', 'id'))
            effective_quality_gate = {**pipeline.quality_gate, **effective_quality_gate}

    rules = _resolve_rules(
        user=user,
        explicit_rules=pipeline_rules,
        rule_ids=rule_ids,
        include_all_auto_rules=include_all_auto_rules and not bool(rule_ids),
    )
    return pipeline, rules, effective_quality_gate


def _build_no_rules_message(*, source, pipeline, rule_ids, include_all_auto_rules):
    if pipeline and not pipeline.rules.filter(is_active=True).exists():
        return (
            f'Aucune correction active n est disponible pour le pipeline "{pipeline.name}". '
            'Active au moins une regle dans ce pipeline avant de lancer le nettoyage.'
        )

    if rule_ids:
        return (
            'Les corrections selectionnees ne sont pas disponibles ou ne sont plus actives. '
            'Verifie la configuration des regles avant de relancer le nettoyage.'
        )

    if include_all_auto_rules:
        return (
            f'Aucune correction automatique n est configuree pour {source.name}. '
            'Lance d abord le diagnostic, puis active au moins une regle ou un pipeline applicable.'
        )

    return (
        f'Aucune correction applicable n a ete trouvee pour {source.name}. '
        'Configure au moins une regle active ou un pipeline de nettoyage.'
    )


def _resolve_rules(*, user, explicit_rules, rule_ids, include_all_auto_rules):
    queryset = CleaningRule.objects.filter(is_active=True)
    rules = list(explicit_rules)

    if rule_ids:
        existing_ids = {rule.id for rule in rules}
        rules.extend([rule for rule in queryset.filter(id__in=rule_ids).order_by('-priority', 'id') if rule.id not in existing_ids])

    if include_all_auto_rules:
        auto_rules = list(queryset.filter(apply_to_all=True).order_by('-priority', 'id'))
        existing_ids = {rule.id for rule in rules}
        rules.extend([rule for rule in auto_rules if rule.id not in existing_ids])

    return sorted(rules, key=lambda rule: (-rule.priority, rule.id))


def _data_columns(dataframe):
    return [column for column in dataframe.columns if column != '_row_number']


def _string_empty_mask(series):
    try:
        return series.astype('string').str.strip().eq('').fillna(False)
    except Exception:
        return pd.Series(False, index=series.index)


def _missing_like_matrix(dataframe, columns=None):
    target_columns = columns or _data_columns(dataframe)
    if not target_columns:
        return pd.DataFrame(index=dataframe.index)

    matrix = dataframe[target_columns].isna().copy()
    for column in target_columns:
        matrix[column] = matrix[column] | _string_empty_mask(dataframe[column])
    return matrix


def _normalize_str(value):
    try:
        return re.sub(r"\s+", " ", str(value).strip().lower())
    except Exception:
        return ""


def _fuzzy_suggest_matches(source_columns, canonical_columns, top_n=1, threshold=60):
    """Return fuzzy match suggestions for each source column against canonical columns.

    Output format: { source_col: [ { 'candidate': canon, 'score': int }, ... ] }
    Requires `thefuzz`; if unavailable returns {}.
    """
    if not fuzz:
        return {}

    suggestions = {}
    norm_canon = [(canon, _normalize_str(canon)) for canon in canonical_columns]
    for col in source_columns:
        ncol = _normalize_str(col)
        best = []
        for canon, ncanon in norm_canon:
            try:
                score = fuzz.token_set_ratio(ncol, ncanon)
            except Exception:
                score = 0
            if score >= threshold:
                best.append({'candidate': canon, 'score': int(score)})
        if best:
            best = sorted(best, key=lambda x: -x['score'])[:top_n]
            suggestions[col] = best
    return suggestions


def _load_source_dataframe(source, sheet_name=None):
    qs = source.raw_data_rows.order_by('row_number')
    if sheet_name is not None:
        qs = qs.filter(sheet_name=sheet_name)
    raw_rows = list(qs.values('row_number', 'data', 'sheet_name'))
    if not raw_rows:
        raise CleaningError('The selected data source does not contain raw rows.')

    records = []
    for row in raw_rows:
        record = {'_row_number': row['row_number']}
        record.update(row['data'])
        records.append(record)

    dataframe = pd.DataFrame(records)
    return dataframe.where(pd.notnull(dataframe), None)


def _load_all_sheets_as_dataframes(source):
    """Load all sheets as separate DataFrames. Returns dict {sheet_name: DataFrame}."""
    from apps.ingestion.models import DataSourceSheet
    sheets = DataSourceSheet.objects.filter(source=source)
    if not sheets.exists():
        df = _load_source_dataframe(source)
        return {'': df}

    result = {}
    for sheet in sheets:
        try:
            df = _load_source_dataframe(source, sheet_name=sheet.sheet_name)
            result[sheet.sheet_name] = df
        except CleaningError:
            continue
    if not result:
        df = _load_source_dataframe(source)
        result[''] = df
    return result


def _run_cleaning_job(*, source, user, rule, dataframe, execution_context):
    total_rows_before = len(dataframe)
    started_at = timezone.now()
    start_time = time.perf_counter()

    with transaction.atomic():
        job = CleaningJob.objects.create(
            source=source,
            rule=rule,
            status='running',
            total_rows=total_rows_before,
            started_at=started_at,
            created_by=user,
            execution_context=execution_context,
        )

        try:
            result = _apply_single_rule(dataframe=dataframe, rule=rule)
            cleaned_dataframe = result['dataframe']
            summary = result['summary']
            quality_scores = result['quality_scores']
            changes_by_row = result['changes_by_row']
            validation_issues = result['validation_issues']

            _persist_cleaned_results(
                job=job,
                source=source,
                dataframe=cleaned_dataframe,
                quality_scores=quality_scores,
                changes_by_row=changes_by_row,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job.status = 'completed'
            job.rows_processed = summary['rows_processed']
            job.rows_affected = summary['rows_affected']
            job.rows_skipped = summary['rows_skipped']
            job.rows_failed = summary['rows_failed']
            job.progress_percent = 100
            job.completed_at = timezone.now()
            job.duration_ms = duration_ms
            job.error_message = None
            job.save()

            rule.execution_count += 1
            if rule.success_rate is None:
                rule.success_rate = 100
            else:
                rule.success_rate = min(100, float(rule.success_rate) * 0.8 + 20)
            rule.save(update_fields=['execution_count', 'success_rate', 'updated_at'])

            cleaned_dataframe.attrs['validation_issues'] = validation_issues
            return job, cleaned_dataframe
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job.status = 'failed'
            job.rows_processed = 0
            job.rows_failed = total_rows_before
            job.progress_percent = 0
            job.completed_at = timezone.now()
            job.duration_ms = duration_ms
            job.error_message = str(exc)
            job.save()
            raise CleaningError(str(exc)) from exc


def _apply_rules(*, dataframe, rules, quality_gate):
    current_dataframe = dataframe.copy()
    aggregated_issues = []

    for rule in rules:
        result = _apply_single_rule(dataframe=current_dataframe, rule=rule)
        current_dataframe = result['dataframe']
        aggregated_issues.extend(result['validation_issues'])

    sample_rows = _dataframe_records(current_dataframe.drop(columns=['_row_number'], errors='ignore').head(10))
    summary = _summarize_dataframe(current_dataframe)
    summary['average_quality_score'] = _average_quality_score(current_dataframe)
    column_profile = _build_column_profile(current_dataframe)
    sample_row_numbers = current_dataframe.head(10)['_row_number'].tolist()
    original_by_row = _row_lookup(dataframe, row_numbers=sample_row_numbers)
    quality_gate_failure = _evaluate_quality_gate(
        dataframe=current_dataframe,
        validation_issues=aggregated_issues,
        quality_gate=quality_gate,
    )
    if quality_gate_failure:
        aggregated_issues.append({
            'rule': 'quality_gate',
            'code': 'quality_gate_failed',
            'message': quality_gate_failure,
        })

    return {
        'dataframe': current_dataframe,
        'summary': summary,
        'column_profile': column_profile,
        'sample_rows': sample_rows,
        'diff_samples': _build_diff_samples(original_by_row, current_dataframe),
        'validation_issues': aggregated_issues,
    }


def _apply_single_rule(*, dataframe, rule):
    working = dataframe.copy()
    target_columns = _resolve_target_columns(working, rule)
    changes_by_row = {int(row_no): [] for row_no in working['_row_number'].tolist()}
    validation_issues = []
    rows_affected = 0

    if rule.rule_type == 'standardize':
        mode = rule.parameters.get('mode', 'trim_lower')
        for column in target_columns:
            original = working[column].copy()
            working[column] = working[column].apply(lambda value: _standardize_value(value, mode))
            rows_affected += _record_changes(working, original, column, changes_by_row, f'standardize:{mode}')

    elif rule.rule_type == 'fill_value':
        fill_value = rule.parameters.get('value', rule.parameters.get('fill_value', ''))
        for column in target_columns:
            mask = _missing_like_matrix(working, [column])[column]
            rows_affected += int(mask.sum())
            working.loc[mask, column] = fill_value
            _record_mask_changes(working, mask, column, changes_by_row, f'fill_value:{fill_value}')

    elif rule.rule_type == 'fill_mean':
        for column in target_columns:
            numeric_series = pd.to_numeric(working[column], errors='coerce')
            fill_value = numeric_series.mean()
            if pd.isna(fill_value):
                continue
            mask = _missing_like_matrix(working, [column])[column]
            rows_affected += int(mask.sum())
            working.loc[mask, column] = round(float(fill_value), 4)
            _record_mask_changes(working, mask, column, changes_by_row, f'fill_mean:{round(float(fill_value), 4)}')

    elif rule.rule_type == 'fill_median':
        for column in target_columns:
            numeric_series = pd.to_numeric(working[column], errors='coerce')
            fill_value = numeric_series.median()
            if pd.isna(fill_value):
                continue
            mask = _missing_like_matrix(working, [column])[column]
            rows_affected += int(mask.sum())
            working.loc[mask, column] = round(float(fill_value), 4)
            _record_mask_changes(working, mask, column, changes_by_row, f'fill_median:{round(float(fill_value), 4)}')

    elif rule.rule_type == 'fill_mode':
        for column in target_columns:
            empty_mask = _missing_like_matrix(working, [column])[column]
            mode_series = working.loc[~empty_mask, column]
            if mode_series.empty:
                continue
            fill_value = mode_series.mode().iloc[0]
            mask = empty_mask
            rows_affected += int(mask.sum())
            working.loc[mask, column] = fill_value
            _record_mask_changes(working, mask, column, changes_by_row, f'fill_mode:{fill_value}')

    elif rule.rule_type == 'remove_empty_rows':
        subset = target_columns or _data_columns(working)
        before = len(working)
        mask = _missing_like_matrix(working, subset).all(axis=1)
        removed_rows = working.loc[mask, '_row_number'].tolist()
        working = working.loc[~mask].reset_index(drop=True)
        rows_affected += before - len(working)
        if removed_rows:
            validation_issues.append({
                'rule': rule.name,
                'code': 'empty_rows_removed',
                'message': f'Removed {len(removed_rows)} empty or whitespace-only rows.',
                'row_numbers': removed_rows,
            })

    elif rule.rule_type == 'drop_rows_by_missing_threshold':
        threshold = float(rule.parameters.get('threshold', 0.5))
        subset = target_columns or _data_columns(working)
        before = len(working)
        row_missing_rate = _missing_like_matrix(working, subset).mean(axis=1)
        mask = row_missing_rate > threshold
        removed_rows = working.loc[mask, '_row_number'].tolist()
        working = working.loc[~mask].reset_index(drop=True)
        rows_affected += before - len(working)
        if removed_rows:
            validation_issues.append({
                'rule': rule.name,
                'code': 'rows_dropped_by_missing_threshold',
                'message': f'Removed {len(removed_rows)} rows above missing threshold {threshold}.',
                'row_numbers': removed_rows,
            })

    elif rule.rule_type == 'drop_columns_by_missing_threshold':
        threshold = float(rule.parameters.get('threshold', 0.5))
        candidate_columns = target_columns or [column for column in working.columns if column != '_row_number']
        dropped_columns = []
        for column in candidate_columns:
            missing_rate = sum(_is_empty_like(value) for value in working[column]) / max(len(working), 1)
            if missing_rate > threshold:
                dropped_columns.append(column)
        if dropped_columns:
            working = working.drop(columns=dropped_columns)
            rows_affected += len(dropped_columns)
            validation_issues.append({
                'rule': rule.name,
                'code': 'columns_dropped_by_missing_threshold',
                'message': f'Dropped columns above missing threshold {threshold}.',
                'columns': dropped_columns,
            })

    elif rule.rule_type == 'regex_replace':
        pattern = rule.parameters.get('pattern')
        replacement = rule.parameters.get('replacement', '')
        if not pattern:
            raise CleaningError('regex_replace requires a pattern parameter.')
        regex = re.compile(pattern)
        for column in target_columns:
            original = working[column].copy()
            working[column] = working[column].apply(lambda value: regex.sub(replacement, str(value)) if value not in (None, '') else value)
            rows_affected += _record_changes(working, original, column, changes_by_row, 'regex_replace')

    elif rule.rule_type == 'remove_duplicates':
        subset = target_columns or [column for column in working.columns if column != '_row_number']
        duplicate_mask = working.duplicated(subset=subset, keep='first')
        duplicate_rows = working.loc[duplicate_mask, '_row_number'].tolist()
        rows_affected += len(duplicate_rows)
        if duplicate_rows:
            validation_issues.append({
                'rule': rule.name,
                'code': 'duplicates_removed',
                'message': f'Removed {len(duplicate_rows)} duplicate rows.',
                'row_numbers': duplicate_rows,
            })
        working = working.loc[~duplicate_mask].reset_index(drop=True)

    elif rule.rule_type == 'normalize':
        mode = rule.parameters.get('mode', 'upper')
        for column in target_columns:
            original = working[column].copy()
            working[column] = working[column].apply(lambda value: _normalize_value(value, mode, rule.parameters))
            rows_affected += _record_changes(working, original, column, changes_by_row, f'normalize:{mode}')

    elif rule.rule_type == 'convert_dtype':
        target_dtype = rule.parameters.get('dtype', 'string')
        for column in target_columns:
            original = working[column].copy()
            working[column] = working[column].apply(lambda value: _convert_dtype(value, target_dtype, rule.parameters))
            rows_affected += _record_changes(working, original, column, changes_by_row, f'convert_dtype:{target_dtype}')

    elif rule.rule_type == 'value_map':
        mapping = rule.parameters.get('mapping', {})
        case_insensitive = bool(rule.parameters.get('case_insensitive', False))
        for column in target_columns:
            original = working[column].copy()
            working[column] = working[column].apply(lambda value: _map_value(value, mapping, case_insensitive))
            rows_affected += _record_changes(working, original, column, changes_by_row, 'value_map')

    elif rule.rule_type == 'rename_columns':
        mapping = rule.parameters.get('mapping', {})
        normalized_mapping = {str(key): str(value) for key, value in mapping.items()}
        applicable = {column: normalized_mapping[column] for column in working.columns if column in normalized_mapping}
        if applicable:
            working = working.rename(columns=applicable)
            rows_affected += len(applicable)
            validation_issues.append({
                'rule': rule.name,
                'code': 'columns_renamed',
                'message': f'Renamed {len(applicable)} columns.',
                'columns': applicable,
            })

    elif rule.rule_type == 'split_column':
        source_column = rule.parameters.get('source_column')
        separator = rule.parameters.get('separator', ' ')
        target_columns_param = rule.parameters.get('target_columns', [])
        if not source_column or not target_columns_param:
            raise CleaningError('split_column requires source_column and target_columns parameters.')
        if source_column not in working.columns:
            raise CleaningError(f'split_column source column "{source_column}" was not found.')
        split_frame = working[source_column].fillna('').astype(str).str.split(separator, expand=True)
        for index, target_column in enumerate(target_columns_param):
            original = pd.Series([None] * len(working))
            working[target_column] = split_frame[index] if index in split_frame.columns else None
            rows_affected += _record_changes(working, original, target_column, changes_by_row, f'split_column:{source_column}')

    elif rule.rule_type == 'merge_columns':
        source_columns = rule.parameters.get('source_columns', [])
        target_column = rule.parameters.get('target_column')
        separator = rule.parameters.get('separator', ' ')
        if not source_columns or not target_column:
            raise CleaningError('merge_columns requires source_columns and target_column parameters.')
        missing_source_columns = [column for column in source_columns if column not in working.columns]
        if missing_source_columns:
            raise CleaningError(f'merge_columns source columns not found: {", ".join(missing_source_columns)}')
        original = working[target_column].copy() if target_column in working.columns else pd.Series([None] * len(working))
        working[target_column] = working[source_columns].apply(
            lambda row: separator.join(str(value).strip() for value in row if not _is_empty_like(value)),
            axis=1,
        )
        rows_affected += _record_changes(working, original, target_column, changes_by_row, f'merge_columns:{",".join(source_columns)}')

    elif rule.rule_type == 'validate_format':
        pattern = rule.parameters.get('pattern')
        if not pattern:
            raise CleaningError('validate_format requires a pattern parameter.')
        regex = re.compile(pattern)
        for column in target_columns:
            invalid_rows = []
            for _, row in working.iterrows():
                value = row.get(column)
                if value in (None, ''):
                    continue
                if not regex.match(str(value)):
                    invalid_rows.append(int(row['_row_number']))
                    changes_by_row[int(row['_row_number'])].append({
                        'rule': rule.name,
                        'column': column,
                        'action': 'validate_format',
                        'status': 'invalid_format',
                    })
            if invalid_rows:
                rows_affected += len(invalid_rows)
                validation_issues.append({
                    'rule': rule.name,
                    'code': 'invalid_format',
                    'message': f'Column "{column}" has values not matching the expected format.',
                    'row_numbers': invalid_rows,
                })

    elif rule.rule_type == 'remove_nulls':
        subset = target_columns or [column for column in working.columns if column != '_row_number']
        before = len(working)
        mask = _missing_like_matrix(working, subset).any(axis=1)
        working = working.loc[~mask].reset_index(drop=True)
        rows_affected += before - len(working)

    elif rule.rule_type == 'extract_labeled_fields':
        from apps.nettoyage.structure_detection.cell_transformer import extract_labeled_fields
        source_column = rule.parameters.get('source_column')
        labels = rule.parameters.get('labels', [])
        result_columns = rule.parameters.get('result_columns', [])
        if not source_column or not labels:
            raise CleaningError('extract_labeled_fields requires source_column and labels parameters.')
        if source_column not in working.columns:
            raise CleaningError(f'extract_labeled_fields source column "{source_column}" not found.')
        for col in result_columns:
            working[col] = ''
        original = working[source_column].copy()
        for idx, row in working.iterrows():
            texte = str(row[source_column]) if pd.notna(row[source_column]) else ''
            extracted = extract_labeled_fields(texte, labels)
            for col in result_columns:
                working.at[idx, col] = extracted.get(col, '')
        working = working.drop(columns=[source_column])
        rows_affected += _record_changes(working, original, result_columns[0] if result_columns else source_column, changes_by_row, 'extract_labeled_fields')

    elif rule.rule_type == 'fix_ambiguous_chars':
        from apps.nettoyage.structure_detection.cell_transformer import fix_ambiguous_numeric_chars
        substitutions = rule.parameters.get('substitutions', {})
        cas_incertains = rule.parameters.get('cas_incertains', [])
        for column in target_columns:
            if column not in working.columns:
                continue
            original = working[column].copy()
            for idx, val in working[column].items():
                str_val = str(val) if pd.notna(val) else ''
                result = fix_ambiguous_numeric_chars(str_val, substitutions, cas_incertains)
                if not result['needs_review']:
                    working.at[idx, column] = result['corrected']
            rows_affected += _record_changes(working, original, column, changes_by_row, f'fix_ambiguous_chars:{column}')

    elif rule.rule_type == 'split_value_unit':
        import re as _re
        source_column = rule.parameters.get('source_column')
        target_number = rule.parameters.get('target_number_column', 'Quantity')
        target_text = rule.parameters.get('target_text_column', 'Measure')
        if not source_column:
            raise CleaningError('split_value_unit requires source_column parameter.')
        if source_column not in working.columns:
            raise CleaningError(f'split_value_unit source column "{source_column}" not found.')
        working[target_number] = ''
        working[target_text] = ''
        original_number = working[target_number].copy()
        original_text = working[target_text].copy()
        for idx, val in working[source_column].items():
            str_val = str(val) if pd.notna(val) else ''
            match = _re.match(r'^([+-]?\d+(?:[.,]\d+)?)\s*([a-zA-Z].*)$', str_val.strip())
            if match:
                working.at[idx, target_number] = match.group(1).replace(',', '.')
                working.at[idx, target_text] = match.group(2).strip()
            else:
                working.at[idx, target_number] = str_val
                working.at[idx, target_text] = ''
        working = working.drop(columns=[source_column])
        rows_affected += _record_changes(working, original_number, target_number, changes_by_row, f'split_value_unit:{source_column}')

    elif rule.rule_type == 'explode_delimited_list':
        colonnes_liees = rule.parameters.get('colonnes_liees', [])
        delimiteur = rule.parameters.get('delimiteur', '|')
        colonnes_a_repeter = rule.parameters.get('colonnes_a_repeter', [])
        if not colonnes_liees:
            raise CleaningError('explode_delimited_list requires colonnes_liees parameter.')
        missing = [c for c in colonnes_liees if c not in working.columns]
        if missing:
            raise CleaningError(f'explode_delimited_list columns not found: {missing}')
        result_rows = []
        for idx, row in working.iterrows():
            ligne = row.to_dict()
            listes = {}
            for col in colonnes_liees:
                val = ligne.get(col, '')
                if pd.isna(val):
                    val = ''
                parts = [p.strip() for p in str(val).split(delimiteur)]
                listes[col] = parts
            lengths = [len(parts) for parts in listes.values()]
            if len(set(lengths)) > 1:
                result_rows.append(ligne)
                continue
            nb = lengths[0] if lengths else 0
            if nb == 0:
                result_rows.append(ligne)
                continue
            for i in range(nb):
                new_row = {}
                for col_a_repeter in colonnes_a_repeter:
                    new_row[col_a_repeter] = ligne.get(col_a_repeter, '')
                for col in colonnes_liees:
                    new_row[col] = listes[col][i]
                result_rows.append(new_row)
        before = len(working)
        working = pd.DataFrame(result_rows)
        if '_row_number' not in working.columns:
            working['_row_number'] = range(1, len(working) + 1)
        rows_affected += abs(len(working) - before)

    elif rule.rule_type == 'unpivot':
        from apps.nettoyage.structure_detection.pivot_transformer import PivotTransformer
        params = rule.parameters
        header_row_index = params.get('header_row_index')
        value_col_indices = params.get('value_col_indices')
        unpivot_map = params.get('unpivot_map', [])
        source_file_path = params.get('source_file_path', '')

        original_df = None
        if source_file_path:
            try:
                from pathlib import Path
                media_root = Path(settings.MEDIA_ROOT)
                fp = source_file_path
                full_path = media_root / fp if not Path(fp).is_absolute() else Path(fp)
                if not full_path.exists():
                    full_path = Path(fp)
                if full_path.exists():
                    original_df = pd.read_excel(str(full_path), header=None, engine='openpyxl')
            except Exception:
                original_df = None

        if original_df is not None and header_row_index is not None and value_col_indices:
            working = original_df.copy()
            if header_row_index > 0:
                header_values = working.iloc[header_row_index].tolist()
                working = working.iloc[header_row_index + 1:].reset_index(drop=True)
                new_cols = []
                for i, h in enumerate(header_values):
                    h_str = str(h).strip() if pd.notna(h) else ''
                    if h_str and h_str != 'None':
                        new_cols.append(h_str)
                    else:
                        new_cols.append(f'col_{i}')
                working.columns = new_cols
        else:
            if header_row_index is not None and value_col_indices:
                if header_row_index > 0 and len(working) > header_row_index:
                    header_values = working.iloc[header_row_index].tolist()
                    working = working.iloc[header_row_index + 1:].reset_index(drop=True)
                    new_cols = []
                    for i, h in enumerate(header_values):
                        h_str = str(h).strip() if pd.notna(h) else ''
                        if h_str and h_str != 'None':
                            new_cols.append(h_str)
                        else:
                            new_cols.append(f'col_{i}')
                    working.columns = new_cols

        mapping = {
            'colonnes_identifiantes': params.get('colonnes_identifiantes', []),
            'colonnes_valeurs': params.get('colonnes_valeurs', []),
            'nom_nouvelle_colonne_dimension': params.get('nom_nouvelle_colonne_dimension', 'Dimension'),
            'nom_nouvelle_colonne_valeur': params.get('nom_nouvelle_colonne_valeur', 'Valeur'),
        }
        id_vars = mapping['colonnes_identifiantes']
        value_vars = mapping['colonnes_valeurs']

        col_positions = {col: i for i, col in enumerate(working.columns)}
        data_cols = [column for column in working.columns if column != '_row_number']

        def _resolve_by_position(cols: list[str], indices: list[int], data_cols: list[str]) -> list[str]:
            resolved = []
            for name, idx in zip(cols, indices):
                if name in working.columns:
                    resolved.append(name)
                elif name.startswith('col_') and len(data_cols) > 1 and idx < len(data_cols):
                    resolved.append(data_cols[idx])
                elif idx < len(data_cols):
                    resolved.append(data_cols[idx])
                else:
                    resolved.append(name)
            return resolved

        if value_col_indices and value_vars and len(value_col_indices) == len(value_vars):
            mapping['colonnes_valeurs'] = _resolve_by_position(value_vars, value_col_indices, data_cols)
            value_vars = mapping['colonnes_valeurs']
        else:
            mapping['colonnes_valeurs'] = _resolve_by_position(value_vars, list(range(len(value_vars))), data_cols)
            value_vars = mapping['colonnes_valeurs']

        if id_vars:
            resolved_id_vars = []
            for name in id_vars:
                if name in working.columns:
                    resolved_id_vars.append(name)
                elif name.startswith('col_'):
                    idx = int(name.split('_')[1])
                    resolved_id_vars.append(data_cols[idx] if idx < len(data_cols) else name)
                else:
                    resolved_id_vars.append(name)
            mapping['colonnes_identifiantes'] = resolved_id_vars
            id_vars = resolved_id_vars

        missing = [c for c in id_vars + value_vars if c not in working.columns]
        if missing:
            raise CleaningError(f'unpivot: colonnes manquantes: {missing}. Colonnes dispo: {list(working.columns)[:10]}')
        transformer = PivotTransformer()
        before_rows = len(working)
        result_df = transformer.unpivot_from_mapping(working, mapping)
        if result_df is None:
            raise CleaningError('unpivot: transformation echouee (resultat vide)')
        if unpivot_map and mapping['nom_nouvelle_colonne_dimension'] in result_df.columns:
            dim_col = mapping['nom_nouvelle_colonne_dimension']
            col_label_map = {}
            for entry in unpivot_map:
                src = entry.get('source_col')
                path = entry.get('path', [])
                non_empty = [p for p in path if p and p != 'None']
                label = ' | '.join(non_empty[:-1]) if len(non_empty) > 1 else (non_empty[0] if non_empty else f'col_{src}')
                col_label_map[f'col_{src}'] = label
            result_df[dim_col] = result_df[dim_col].map(lambda x: col_label_map.get(x, x))
        working = result_df
        if '_row_number' not in working.columns:
            working['_row_number'] = range(1, len(working) + 1)
        rows_affected += abs(len(working) - before_rows)

    else:
        raise CleaningError(f'Unsupported cleaning rule type: {rule.rule_type}')

    quality_scores = _calculate_quality_scores(working)
    summary = _summarize_dataframe(working, rows_affected=rows_affected)
    return {
        'dataframe': working,
        'summary': summary,
        'quality_scores': quality_scores,
        'changes_by_row': changes_by_row,
        'validation_issues': validation_issues,
    }


def _resolve_target_columns(dataframe, rule):
    data_columns = _data_columns(dataframe)
    matched = set()

    for column in rule.column_names:
        if column in data_columns:
            matched.add(column)

    if rule.column_pattern:
        regex = re.compile(rule.column_pattern)
        for column in data_columns:
            if regex.search(column):
                matched.add(column)

    if not matched and rule.rule_type != 'remove_duplicates':
        matched = set(data_columns)

    return sorted(matched)


def _persist_cleaned_results(*, job, source, dataframe, quality_scores, changes_by_row, cleaning_report=None):
    raw_rows_by_number = dict(source.raw_data_rows.values_list('row_number', 'id'))
    cleaned_rows = []
    data_columns = _data_columns(dataframe)
    trace_lookup = _build_structure_trace_lookup(cleaning_report)
    for row in dataframe.to_dict(orient='records'):
        row_number = int(row['_row_number'])
        data = {
            column: _sanitize_value(row.get(column))
            for column in data_columns
        }
        row_changes = list(changes_by_row.get(row_number, []))
        if row_number not in raw_rows_by_number and row_number in trace_lookup:
            row_changes.insert(
                0,
                {
                    'action': 'structure_reconstruction',
                    'source_trace': trace_lookup[row_number],
                },
            )
        cleaned_rows.append(
            CleanedData(
                job=job,
                original_data_id=raw_rows_by_number.get(row_number),
                data=data,
                changes_made=row_changes,
                quality_score=quality_scores.get(row_number, 100),
            )
        )

    CleanedData.objects.filter(job=job).delete()
    seen_original_ids = set()
    deduped_rows = []
    for row in cleaned_rows:
        oid = row.original_data_id
        if oid is not None and oid in seen_original_ids:
            continue
        if oid is not None:
            seen_original_ids.add(oid)
        deduped_rows.append(row)
    CleanedData.objects.bulk_create(deduped_rows, batch_size=1000)


def _build_structure_trace_lookup(cleaning_report):
    structure = (
        (cleaning_report or {})
        .get('metadata', {})
        .get('structure_reconstruction', {})
    )
    traces = structure.get('traces_echantillon', []) or []
    lookup = {}
    for trace in traces:
        row_number = trace.get('row_number_reconstruit')
        if row_number is None:
            continue
        lookup[int(row_number)] = _json_safe(trace)
    return lookup


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, 'item') and callable(getattr(value, 'item')):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _apply_engine_decisions(*, cleaned_dataframe, cleaning_report, decision_overrides):
    overrides = decision_overrides or []
    if not overrides:
        return cleaned_dataframe, cleaning_report

    working = cleaned_dataframe.copy()
    report = _json_safe(cleaning_report)
    applied = []

    columns_to_drop = []
    unmapped_columns_to_drop = []
    sparse_rows_to_drop = []
    for item in overrides:
        if not isinstance(item, dict):
            continue
        if item.get('decision') != 'apply':
            continue
        if item.get('action') == 'drop_quasi_empty_column' and item.get('column'):
            columns_to_drop.append(str(item['column']))
        if item.get('action') == 'drop_unmapped_column' and item.get('column'):
            unmapped_columns_to_drop.append(str(item['column']))
        if item.get('action') == 'drop_sparse_row' and item.get('row_number') is not None:
            try:
                sparse_rows_to_drop.append(int(item['row_number']))
            except (TypeError, ValueError):
                continue

    columns_to_drop = [column for column in dict.fromkeys(columns_to_drop) if column in working.columns and column != '_row_number']
    normalized_unmapped_columns_to_drop = []
    for column in dict.fromkeys(unmapped_columns_to_drop):
        if column in working.columns and column != '_row_number':
            normalized_unmapped_columns_to_drop.append(column)
            continue
        if isinstance(column, str) and column.startswith('extra_'):
            candidate = column[6:]
            if candidate in working.columns and candidate != '_row_number':
                normalized_unmapped_columns_to_drop.append(candidate)

    unmapped_columns_to_drop = list(dict.fromkeys(normalized_unmapped_columns_to_drop))
    sparse_rows_to_drop = list(dict.fromkeys(sparse_rows_to_drop))
    if columns_to_drop:
        working = working.drop(columns=columns_to_drop, errors='ignore')
        report.setdefault('corrections', []).append(
            {
                'regle': 'R31',
                'description': 'Suppression des colonnes quasi vides validee par l utilisateur',
                'nombre': len(columns_to_drop),
                'exemples': [{'avant': column, 'apres': 'supprimée'} for column in columns_to_drop[:10]],
            }
        )
        report.setdefault('metadata', {}).setdefault('decision_application', []).append(
            {
                'action': 'drop_quasi_empty_column',
                'columns': columns_to_drop,
            }
        )
        applied.append(f"{len(columns_to_drop)} colonne(s) quasi vide(s) supprimée(s)")

    if unmapped_columns_to_drop:
        working = working.drop(columns=unmapped_columns_to_drop, errors='ignore')
        report.setdefault('corrections', []).append(
            {
                'regle': 'R32',
                'description': 'Suppression des colonnes non mappees validee par l utilisateur',
                'nombre': len(unmapped_columns_to_drop),
                'exemples': [{'avant': column, 'apres': 'supprimée'} for column in unmapped_columns_to_drop[:10]],
            }
        )
        metadata = report.setdefault('metadata', {})
        metadata.setdefault('decision_application', []).append(
            {
                'action': 'drop_unmapped_column',
                'columns': unmapped_columns_to_drop,
            }
        )
        mapping = report.setdefault('mapping', {})
        mapping['colonnes_non_mappees'] = [
            column for column in mapping.get('colonnes_non_mappees', [])
            if column not in unmapped_columns_to_drop
        ]
        mapping_detail = metadata.setdefault('mapping_resultat', {})
        mapping_detail['colonnes_extra'] = [
            column for column in mapping_detail.get('colonnes_extra', [])
            if column not in unmapped_columns_to_drop
        ]
        mapping_detail['colonnes_a_revoir'] = [
            column for column in mapping_detail.get('colonnes_a_revoir', [])
            if column not in unmapped_columns_to_drop
        ]
        applied.append(f"{len(unmapped_columns_to_drop)} colonne(s) non mappee(s) supprimée(s)")

    if sparse_rows_to_drop:
        before = len(working)
        working = working.loc[~working['_row_number'].isin(sparse_rows_to_drop)].reset_index(drop=True)
        removed = before - len(working)
        if removed:
            report.setdefault('corrections', []).append(
                {
                    'regle': 'R33',
                    'description': 'Suppression des lignes tres incompletes validee par l utilisateur',
                    'nombre': removed,
                    'exemples': [{'avant': f'Ligne {row_number}', 'apres': 'supprimée'} for row_number in sparse_rows_to_drop[:10]],
                }
            )
            report.setdefault('metadata', {}).setdefault('decision_application', []).append(
                {
                    'action': 'drop_sparse_row',
                    'row_numbers': sparse_rows_to_drop,
                }
            )
            applied.append(f"{removed} ligne(s) tres incomplete(s) supprimée(s)")

    if applied:
        report.setdefault('metadata', {}).setdefault('resume_executif', {}).setdefault('corrections_principales', []).append(
            {
                'regle': 'R31-R33',
                'description': '; '.join(applied),
                'nombre': len(columns_to_drop) + len(unmapped_columns_to_drop) + len(sparse_rows_to_drop),
            }
        )

    return working, report


def _record_changes(dataframe, original_series, column, changes_by_row, action):
    affected = 0
    for index, original_value in original_series.items():
        new_value = dataframe.at[index, column]
        if original_value != new_value:
            row_number = int(dataframe.at[index, '_row_number'])
            changes_by_row[row_number].append({
                'column': column,
                'action': action,
                'from': original_value,
                'to': new_value,
            })
            affected += 1
    return affected


def _record_mask_changes(dataframe, mask, column, changes_by_row, action):
    for index in dataframe.index[mask]:
        row_number = int(dataframe.at[index, '_row_number'])
        changes_by_row[row_number].append({
            'column': column,
            'action': action,
            'to': dataframe.at[index, column],
        })


def _standardize_value(value, mode):
    if value in (None, ''):
        return value
    string_value = str(value).strip()
    if mode == 'trim':
        return string_value
    if mode == 'upper':
        return string_value.upper()
    if mode == 'lower':
        return string_value.lower()
    if mode == 'title':
        return string_value.title()
    if mode == 'trim_lower':
        return string_value.lower()
    return string_value


def _normalize_value(value, mode, parameters):
    if value in (None, ''):
        return value
    if mode == 'upper':
        return str(value).upper()
    if mode == 'lower':
        return str(value).lower()
    if mode == 'date_iso':
        parsed = pd.to_datetime(value, errors='coerce')
        if pd.isna(parsed):
            return value
        return parsed.date().isoformat()
    if mode == 'currency_code':
        normalized = str(value).strip().upper()
        currency_map = parameters.get('mapping', {})
        return currency_map.get(normalized, normalized)
    if mode == 'numeric':
        try:
            decimals = int(parameters.get('decimals', 2))
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return value
    return value


def _convert_dtype(value, target_dtype, parameters):
    if _is_empty_like(value):
        return None

    if target_dtype == 'string':
        return str(value).strip()

    if target_dtype == 'integer':
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return value

    if target_dtype == 'float':
        decimals = int(parameters.get('decimals', 4))
        try:
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return value

    if target_dtype == 'boolean':
        normalized = str(value).strip().lower()
        truthy = {'true', '1', 'yes', 'y', 'oui'}
        falsy = {'false', '0', 'no', 'n', 'non'}
        if normalized in truthy:
            return True
        if normalized in falsy:
            return False
        return value

    if target_dtype == 'date':
        parsed = pd.to_datetime(value, errors='coerce', dayfirst=bool(parameters.get('dayfirst', False)))
        if pd.isna(parsed):
            return value
        return parsed.date().isoformat()

    return value


def _map_value(value, mapping, case_insensitive):
    if _is_empty_like(value):
        return value
    if case_insensitive:
        normalized_mapping = {str(key).lower(): replacement for key, replacement in mapping.items()}
        return normalized_mapping.get(str(value).lower(), value)
    return mapping.get(value, value)


def _calculate_quality_scores(dataframe):
    data_columns = _data_columns(dataframe)
    if not data_columns:
        return {int(row_number): 100 for row_number in dataframe['_row_number'].tolist()}

    missing_by_row = _missing_like_matrix(dataframe, data_columns).sum(axis=1)
    total_columns = len(data_columns) or 1
    scores = (100 - (missing_by_row / total_columns) * 100).clip(lower=0).round(2)
    row_numbers = dataframe['_row_number'].astype(int).tolist()
    return dict(zip(row_numbers, scores.tolist(), strict=False))


def _summarize_dataframe(dataframe, rows_affected=0):
    data_columns = _data_columns(dataframe)
    total_cells = max(len(dataframe) * max(len(data_columns), 1), 1)
    missing_cells = int(_missing_like_matrix(dataframe, data_columns).sum().sum()) if data_columns else 0
    return {
        'row_count': len(dataframe),
        'column_count': len(data_columns),
        'rows_processed': len(dataframe),
        'rows_affected': rows_affected,
        'rows_skipped': 0,
        'rows_failed': 0,
        'missing_value_rate': round(missing_cells / total_cells, 4),
    }


def _serialize_rule(rule):
    return {
        'id': rule.id,
        'name': rule.name,
        'rule_type': rule.rule_type,
        'priority': rule.priority,
        'column_names': rule.column_names,
        'parameters': rule.parameters,
    }


def _serialize_pipeline(pipeline):
    return {
        'id': pipeline.id,
        'name': pipeline.name,
        'description': pipeline.description,
        'source_type_scope': pipeline.source_type_scope,
        'quality_gate': pipeline.quality_gate,
    }


def _select_default_pipeline(source):
    return (
        CleaningPipeline.objects.filter(is_active=True, apply_to_all=True)
        .filter(source_type_scope__in=[source.source_type, None, ''])
        .prefetch_related('rules')
        .order_by('name')
        .first()
    )


def _row_lookup(dataframe, row_numbers=None):
    lookup = {}
    subset = dataframe
    if row_numbers:
        subset = dataframe[dataframe['_row_number'].isin(row_numbers)]
    for row in subset.to_dict(orient='records'):
        row_number = int(row['_row_number'])
        lookup[row_number] = {
            column: _sanitize_value(value)
            for column, value in row.items()
            if column != '_row_number'
        }
    return lookup


def _build_diff_samples(original_by_row, current_dataframe):
    diffs = []
    for _, row in current_dataframe.head(10).iterrows():
        row_number = int(row['_row_number'])
        current = {
            column: _sanitize_value(row[column])
            for column in current_dataframe.columns
            if column != '_row_number'
        }
        original = {
            key: _sanitize_value(value)
            for key, value in original_by_row.get(row_number, {}).items()
        }
        changes = []
        for column, new_value in current.items():
            if original.get(column) != new_value:
                changes.append({
                    'column': column,
                    'from': original.get(column),
                    'to': new_value,
                })
        diffs.append({
            'row_number': row_number,
            'original': original,
            'cleaned': current,
            'changes': changes,
        })
    return diffs


def _average_quality_score(dataframe):
    data_columns = _data_columns(dataframe)
    if not len(dataframe):
        return 0
    if not data_columns:
        return 100
    average_missing_ratio = float(_missing_like_matrix(dataframe, data_columns).mean(axis=1).mean())
    return round(max(0, 100 - average_missing_ratio * 100), 2)


def _evaluate_quality_gate(*, dataframe, validation_issues, quality_gate):
    if not quality_gate:
        return None

    average_quality_score = _average_quality_score(dataframe)
    missing_value_rate = _summarize_dataframe(dataframe)['missing_value_rate']

    min_quality_score = quality_gate.get('min_quality_score')
    if min_quality_score is not None and average_quality_score < float(min_quality_score):
        return f'Quality gate failed: average quality score {average_quality_score} is below {min_quality_score}.'

    max_missing_value_rate = quality_gate.get('max_missing_value_rate')
    if max_missing_value_rate is not None and missing_value_rate > float(max_missing_value_rate):
        return f'Quality gate failed: missing value rate {missing_value_rate} is above {max_missing_value_rate}.'

    if quality_gate.get('block_on_validation_issues') and validation_issues:
        return 'Quality gate failed: validation issues were detected.'

    return None


def _build_column_profile(dataframe):
    profile = []
    data_columns = _data_columns(dataframe)
    missing_matrix = _missing_like_matrix(dataframe, data_columns)
    for column in data_columns:
        series = dataframe[column]
        total = max(len(series), 1)
        missing_count = int(missing_matrix[column].sum())
        non_missing = series[~missing_matrix[column]]
        top_values = non_missing.astype(str).value_counts().head(5).to_dict() if not non_missing.empty else {}
        profile.append({
            'column': column,
            'missing_rate': round(missing_count / total, 4),
            'unique_count': int(non_missing.astype(str).nunique()) if not non_missing.empty else 0,
            'top_values': top_values,
        })
    return profile


def _deduplicate_suggestions(suggestions):
    deduplicated = []
    seen = set()
    for suggestion in sorted(suggestions, key=lambda item: (-item.get('priority', 0), item['rule_type'])):
        key = (
            suggestion['rule_type'],
            tuple(suggestion.get('column_names', [])),
            _make_hashable(suggestion.get('suggested_parameters') or {}),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(suggestion)
    return deduplicated


def _make_hashable(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _make_hashable(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_make_hashable(item) for item in value)
    return value


def _extract_validation_issues_from_engine_report(cleaning_report):
    return [
        {
            'rule': alert.get('regle'),
            'code': alert.get('severite'),
            'message': alert.get('message'),
            'row_numbers': alert.get('lignes', []),
        }
        for alert in cleaning_report.get('alertes', [])
    ]


def _build_engine_preview_result(*, original_dataframe, cleaned_dataframe, cleaning_report, quality_gate):
    validation_issues = _extract_validation_issues_from_engine_report(cleaning_report)
    changes_by_row = _build_changes_by_row_from_dataframes(original_dataframe, cleaned_dataframe)
    rows_affected = _count_rows_affected(changes_by_row, original_dataframe, cleaned_dataframe)
    summary = _summarize_dataframe(cleaned_dataframe, rows_affected=rows_affected)
    summary['initial_row_count'] = len(original_dataframe)
    summary['final_row_count'] = len(cleaned_dataframe)
    summary['rows_removed'] = max(len(original_dataframe) - len(cleaned_dataframe), 0)
    summary['columns_removed'] = max(len(_data_columns(original_dataframe)) - len(_data_columns(cleaned_dataframe)), 0)

    sample_row_numbers = cleaned_dataframe.head(10)['_row_number'].astype(int).tolist() if '_row_number' in cleaned_dataframe.columns else []
    original_by_row = _row_lookup(original_dataframe, row_numbers=sample_row_numbers)
    diff_samples = _build_diff_samples(original_by_row, cleaned_dataframe)
    quality_gate_failure = _evaluate_quality_gate(
        dataframe=cleaned_dataframe,
        validation_issues=validation_issues,
        quality_gate=quality_gate,
    )
    if quality_gate_failure:
        validation_issues.append(
            {
                'rule': 'quality_gate',
                'code': 'quality_gate_failed',
                'message': quality_gate_failure,
                'row_numbers': [],
            }
        )

    sample_rows = []
    for row in cleaned_dataframe.head(10).to_dict(orient='records'):
        row_number = int(row['_row_number'])
        cleaned_data = {column: _sanitize_value(value) for column, value in row.items() if column != '_row_number'}
        sample_rows.append(
            {
                'row_number': row_number,
                'data': cleaned_data,
                'status': 'updated' if changes_by_row.get(row_number) else 'unchanged',
            }
        )

    return {
        'summary': summary,
        'column_profile': _build_column_profile(cleaned_dataframe),
        'sample_rows': sample_rows,
        'diff_samples': diff_samples,
        'validation_issues': validation_issues,
        'business_summary': _build_engine_business_summary(summary, cleaning_report, validation_issues),
    }


def _build_changes_by_row_from_dataframes(original_dataframe, cleaned_dataframe):
    changes_by_row = {}
    original_lookup = {
        int(row['_row_number']): row
        for row in original_dataframe.to_dict(orient='records')
    }

    for row in cleaned_dataframe.to_dict(orient='records'):
        row_number = int(row['_row_number'])
        original_row = original_lookup.get(row_number, {})
        changes = []
        for column, new_value in row.items():
            if column == '_row_number':
                continue
            old_value = original_row.get(column)
            sanitized_old = _sanitize_value(old_value)
            sanitized_new = _sanitize_value(new_value)
            if sanitized_old != sanitized_new:
                changes.append({
                    'column': column,
                    'action': 'engine_pipeline_update',
                    'from': sanitized_old,
                    'to': sanitized_new,
                })
        changes_by_row[row_number] = changes

    return changes_by_row


def _count_rows_affected(changes_by_row, original_dataframe, cleaned_dataframe):
    changed_rows = sum(1 for changes in changes_by_row.values() if changes)
    removed_rows = max(len(original_dataframe) - len(cleaned_dataframe), 0)
    return changed_rows + removed_rows


def _extract_detected_issues_from_engine_report(cleaning_report):
    detected_issues = []
    for alert in cleaning_report.get('alertes', []):
        detected_issues.append({
            'code': f"engine_{(alert.get('regle') or 'alert').lower()}",
            'column': None,
            'message': alert.get('message', 'Un point de controle demande une verification.'),
            'row_numbers': alert.get('lignes', []),
        })

    profiling_issues = (
        cleaning_report.get('metadata', {})
        .get('integrations', {})
        .get('profilage_auto', {})
        .get('issues', [])
    )
    for issue in profiling_issues:
        detected_issues.append({
            'code': f"{issue.get('source', 'profiling')}_{issue.get('type', 'issue')}",
            'column': issue.get('column'),
            'message': issue.get('message', 'Le fichier contient un point de qualite a surveiller.'),
            'row_numbers': issue.get('rows', []),
        })

    return detected_issues


def _extract_suggestions_from_engine_report(cleaning_report):
    suggestions = []
    for correction in cleaning_report.get('corrections', []):
        suggestions.append({
            'rule_type': 'engine_correction',
            'reason': correction.get('description', 'Une correction automatique peut etre appliquee.'),
            'suggested_parameters': {
                'regle': correction.get('regle'),
                'exemples': correction.get('exemples', []),
            },
            'priority': 6,
        })

    llm_suggestions = (
        cleaning_report.get('metadata', {})
        .get('integrations', {})
        .get('assistant_llm', {})
        .get('suggestions', [])
    )
    for suggestion in llm_suggestions:
        suggestions.append({
            'rule_type': 'llm_review',
            'column_names': [suggestion['column']] if suggestion.get('column') else [],
            'reason': suggestion.get('reason', 'Une verification humaine est recommandee avant validation.'),
            'suggested_parameters': {
                'proposal': suggestion.get('proposal'),
                'confidence': suggestion.get('confidence'),
                'requires_human_validation': suggestion.get('requires_human_validation', True),
            },
            'priority': 5,
        })

    return suggestions


def _merge_detected_issues(base_issues, engine_issues):
    merged = []
    seen = set()
    for issue in [*base_issues, *engine_issues]:
        key = (
            issue.get('code'),
            issue.get('column'),
            issue.get('message'),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(issue)
    return merged


def _build_business_summary(summary, validation_issues):
    messages = [f"{summary['row_count']} ligne(s) et {summary['column_count']} colonne(s) restent exploitables apres nettoyage."]
    if summary.get('rows_affected'):
        messages.append(f"{summary['rows_affected']} ligne(s) ont ete modifiees ou retirees.")
    else:
        messages.append('Aucune ligne n a ete modifiee automatiquement sur ce passage.')
    if validation_issues:
        messages.append(f"{len(validation_issues)} point(s) demandent encore une verification humaine.")
    else:
        messages.append('Aucun blocage majeur n a ete remonte apres ce passage.')
    taux_vides = round(summary['missing_value_rate'] * 100, 2)
    messages.append(f"Taux de cellules vides apres nettoyage : {taux_vides}%.")
    return messages[:4]


def _build_engine_business_summary(summary, cleaning_report, validation_issues):
    messages = []
    correction_count = len(cleaning_report.get('corrections', []))
    alert_count = len(cleaning_report.get('alertes', []))
    rows_removed = summary.get('rows_removed', 0)
    columns_removed = summary.get('columns_removed', 0)
    rows_affected = summary.get('rows_affected', 0)

    if correction_count:
        messages.append(f"{correction_count} type(s) de correction automatique ont ete prepares.")
    if rows_affected:
        messages.append(f"{rows_affected} ligne(s) changeraient reellement si tu lances le nettoyage.")
    else:
        messages.append('Aucune ligne ne changerait automatiquement dans cet apercu.')
    if rows_removed or columns_removed:
        parts = []
        if rows_removed:
            parts.append(f"{rows_removed} ligne(s) seraient retirees")
        if columns_removed:
            parts.append(f"{columns_removed} colonne(s) seraient ecartees")
        messages.append(', '.join(parts) + '.')
    if alert_count or validation_issues:
        messages.append(f"{max(alert_count, len(validation_issues))} point(s) resteraient a verifier apres application.")
    return messages


def _build_suggestion_summary(detected_issues):
    if not detected_issues:
        return ['Le fichier ne presente pas de risque majeur dans cet echantillon.']
    messages = []
    for issue in detected_issues[:4]:
        column = issue.get('column')
        if column:
            messages.append(f"{column} : {issue['message']}")
        else:
            messages.append(issue['message'])
    return messages


def _is_empty_like(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    if isinstance(value, str) and value.strip() == '':
        return True
    return False


def _dataframe_records(dataframe):
    return [
        {column: _sanitize_value(value) for column, value in row.items()}
        for row in dataframe.to_dict(orient='records')
    ]


def _sanitize_value(value):
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value
