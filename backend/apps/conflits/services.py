"""
M3: Conflict Detection and Resolution Services
Handles identification, analysis, and guided resolution of inter-source conflicts.
"""

import json
import logging
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from collections import Counter
import re

from django.db.models import Q, Count, Case, When, IntegerField
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction

from apps.conflits.models import (
    Conflict, ConflictType, ConflictResolution, ActivityLog
)
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleaningJob

logger = logging.getLogger(__name__)


class ConflictDetectionService:
    """
    Identifies various types of conflicts in data and loads them for resolution.
    """
    
    CONFLICT_STRATEGIES = {
        'DUPLICATE_RECORDS': 'majority_vote',
        'MISSING_VALUES': 'default_value',
        'DATA_TYPE_MISMATCH': 'latest_value',
        'FORMAT_INCONSISTENCY': 'user_selected',
        'BUSINESS_CONFLICT': 'user_selected',
    }
    
    def __init__(self, user: User = None):
        self.user = user

    def _create_or_update_conflict(
        self,
        *,
        source: DataSource,
        conflict_type: ConflictType,
        signature: str,
        description: str,
        affected_columns: list[str] | None = None,
        affected_row_ids: list[int | str] | None = None,
        conflict_details: dict | None = None,
        priority: int = 5,
        impact_score: Decimal | None = None,
    ) -> Conflict:
        existing = (
            Conflict.objects.filter(
                data_source=source,
                conflict_type=conflict_type,
                status__in=['detected', 'investigating', 'resolving'],
            )
            .filter(conflict_details__signature=signature)
            .order_by('-detected_at')
            .first()
        )

        payload = {
            **(conflict_details or {}),
            'signature': signature,
            'active_dataset': self._get_source_rows(source)[1],
        }
        normalized_row_ids = [str(item) for item in (affected_row_ids or [])]

        if existing:
            existing.affected_columns = affected_columns or []
            existing.affected_row_ids = normalized_row_ids
            existing.conflict_details = payload
            existing.description = description
            existing.priority = priority
            existing.impact_score = impact_score
            existing.detected_by = 'system'
            existing.resolved_at = None
            existing.resolution_summary = None
            existing.status = 'detected'
            existing.save(
                update_fields=[
                    'affected_columns',
                    'affected_row_ids',
                    'conflict_details',
                    'description',
                    'priority',
                    'impact_score',
                    'detected_by',
                    'status',
                    'resolved_at',
                    'resolution_summary',
                ]
            )
            return existing

        return Conflict.objects.create(
            data_source=source,
            conflict_type=conflict_type,
            affected_columns=affected_columns or [],
            affected_row_ids=normalized_row_ids,
            conflict_details=payload,
            status='detected',
            priority=priority,
            detected_by='system',
            description=description,
            impact_score=impact_score,
        )

    def _log_detection_activity(self, source: DataSource, result: Dict[str, Any]) -> None:
        ActivityLog.objects.create(
            user=self.user,
            user_email=getattr(self.user, 'email', None),
            user_role=getattr(getattr(self.user, 'profile', None), 'role', None),
            action_type='read',
            resource_type='ConflictDetection',
            resource_id=source.id,
            resource_name=source.name,
            action_details={
                'source_id': source.id,
                'total_conflicts': result.get('total_conflicts', 0),
                'by_type': result.get('by_type', {}),
                'active_dataset': result.get('active_dataset'),
            },
            status_code=200,
        )

    def _get_active_cleaning_job(self, source: DataSource) -> Optional[CleaningJob]:
        jobs = (
            CleaningJob.objects.filter(source=source, status='completed')
            .prefetch_related('cleaned_results')
            .order_by('-completed_at', '-created_at')
        )
        for job in jobs:
            total = job.cleaned_results.count()
            if total and job.cleaned_results.filter(is_validated=True).count() == total:
                return job
        return None

    def _get_source_rows(self, source: DataSource) -> Tuple[List[Dict[str, Any]], str]:
        active_job = self._get_active_cleaning_job(source)
        if active_job:
            rows = list(
                active_job.cleaned_results.filter(is_validated=True)
                .order_by('original_data__row_number', 'id')
                .values_list('data', flat=True)
            )
            return rows, 'validated_cleaning'

        rows = list(
            RawData.objects.filter(source=source)
            .order_by('row_number')
            .values_list('data', flat=True)
        )
        return rows, 'raw_source'
    
    def detect_conflicts_in_source(
        self, 
        source: DataSource, 
        source_type_code: str = None,
        check_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive conflict detection for a data source.
        Can be triggered during ingestion (M1) or cleaning (M2).
        
        Args:
            source: DataSource to analyze
            source_type_code: Specific conflict type to check for
            check_types: List of conflict types to detect
        
        Returns:
            {
                'total_conflicts': int,
                'by_type': {'DUPLICATE_RECORDS': 5, ...},
                'by_severity': {'critical': 2, 'high': 3, ...},
                'conflicts': [ConflictType objects],
                'summary': str
            }
        """
        if not check_types:
            check_types = [
                'DUPLICATE_RECORDS',
                'MISSING_VALUES',
                'DATA_TYPE_MISMATCH',
                'FORMAT_INCONSISTENCY',
            ]
        
        detected = {}
        conflict_objects = []
        active_dataset = 'raw_source'
        
        try:
            _, active_dataset = self._get_source_rows(source)
            # 1. Check for duplicate records
            if 'DUPLICATE_RECORDS' in check_types:
                dup_conflicts = self._detect_duplicates(source)
                if dup_conflicts:
                    conflict_objects.extend(dup_conflicts)
            
            # 2. Check for missing values
            if 'MISSING_VALUES' in check_types:
                missing_conflicts = self._detect_missing_values(source)
                if missing_conflicts:
                    conflict_objects.extend(missing_conflicts)
            
            # 3. Check for data type mismatches
            if 'DATA_TYPE_MISMATCH' in check_types:
                dtype_conflicts = self._detect_data_type_issues(source)
                if dtype_conflicts:
                    conflict_objects.extend(dtype_conflicts)
            
            # 4. Check for format inconsistencies
            if 'FORMAT_INCONSISTENCY' in check_types:
                format_conflicts = self._detect_format_issues(source)
                if format_conflicts:
                    conflict_objects.extend(format_conflicts)
            
            # Aggregate by actual conflict type and severity
            for conflict in conflict_objects:
                code = conflict.conflict_type.code
                detected[code] = detected.get(code, 0) + 1

            severity_counts = {}
            for conflict in conflict_objects:
                severity = conflict.conflict_type.severity
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            result = {
                'total_conflicts': len(conflict_objects),
                'by_type': detected,
                'by_severity': severity_counts,
                'conflicts': conflict_objects,
                'active_dataset': active_dataset,
                'summary': f"Found {len(conflict_objects)} conflicts: {', '.join([f'{k}={v}' for k, v in detected.items()])}"
            }
            self._log_detection_activity(source, result)
            return result
            
        except Exception as e:
            logger.exception(f"Error detecting conflicts in source {source.id}")
            return {
                'total_conflicts': 0,
                'by_type': {},
                'by_severity': {},
                'conflicts': [],
                'active_dataset': active_dataset,
                'error': str(e),
                'summary': f"Error detecting conflicts: {str(e)}"
            }
    
    def _detect_duplicates(self, source: DataSource) -> List[Conflict]:
        """Detect duplicate records within a source or across sources."""
        conflicts = []
        
        try:
            row_payloads, _ = self._get_source_rows(source)
            
            if len(row_payloads) < 2:
                return conflicts
            
            # Hash each row to find duplicates
            seen_hashes = {}
            duplicate_rows = []
            
            for row_data in row_payloads:
                row_hash = hashlib.md5(
                    json.dumps(row_data, sort_keys=True, default=str).encode('utf-8')
                ).hexdigest()
                
                if row_hash in seen_hashes:
                    duplicate_rows.append({
                        'duplicate_of': seen_hashes[row_hash],
                        'row': row_data
                    })
                else:
                    seen_hashes[row_hash] = row_data
            
            if duplicate_rows:
                # Get or create DUPLICATE_RECORDS conflict type
                conflict_type, _ = ConflictType.objects.get_or_create(
                    code='DUPLICATE_RECORDS',
                    defaults={
                        'name': 'Duplicate Records',
                        'severity': 'high',
                        'description': 'Identical records found in the dataset',
                        'auto_resolve': True,
                        'resolution_strategy': 'majority_vote'
                    }
                )
                
                # Create conflict record
                signature_payload = json.dumps(
                    duplicate_rows[:10], sort_keys=True, default=str
                ).encode('utf-8')
                conflict = self._create_or_update_conflict(
                    source=source,
                    conflict_type=conflict_type,
                    signature=f"duplicates:{len(duplicate_rows)}:{hashlib.md5(signature_payload).hexdigest()}",
                    affected_row_ids=[item['row'].get('_row_number', index + 1) if isinstance(item['row'], dict) else index + 1 for index, item in enumerate(duplicate_rows)],
                    conflict_details={
                        'duplicate_count': len(duplicate_rows),
                        'sample_duplicates': duplicate_rows[:3]
                    },
                    priority=8,
                    impact_score=Decimal('80.00'),
                    description=f"Found {len(duplicate_rows)} duplicate records"
                )
                conflicts.append(conflict)
                logger.info(f"Detected {len(duplicate_rows)} duplicate records in source {source.id}")

            partial_conflict = self._detect_partial_duplicate_conflict(source, row_payloads)
            if partial_conflict is not None:
                conflicts.append(partial_conflict)
        
        except Exception as e:
            logger.error(f"Error detecting duplicates: {str(e)}")
        
        return conflicts
    
    def _detect_missing_values(self, source: DataSource) -> List[Conflict]:
        """Detect missing or null values in key fields."""
        conflicts = []
        
        try:
            row_payloads, _ = self._get_source_rows(source)
            
            if not row_payloads:
                return conflicts
            
            # Analyze missing values across all rows
            missing_by_field = {}
            total_rows = len(row_payloads)
            
            for row_data in row_payloads:
                if isinstance(row_data, dict):
                    for field, value in row_data.items():
                        if value is None or value == '' or value == 'NULL':
                            if field not in missing_by_field:
                                missing_by_field[field] = []
                            missing_by_field[field].append(row_data)
            
            # Flag fields with > 20% missing values
            for field, missing_rows in missing_by_field.items():
                missing_rate = len(missing_rows) / total_rows
                if missing_rate > 0.2:
                    conflict_type, _ = ConflictType.objects.get_or_create(
                        code='MISSING_VALUES',
                        defaults={
                            'name': 'Missing Values',
                            'severity': 'medium',
                            'description': f'Field {field} has > 20% missing values',
                            'auto_resolve': True,
                            'resolution_strategy': 'default_value'
                        }
                    )
                    
                    conflict = self._create_or_update_conflict(
                        source=source,
                        conflict_type=conflict_type,
                        signature=f"missing:{field}",
                        affected_columns=[field],
                        affected_row_ids=self._row_ids_for_predicate(row_payloads, lambda row: row.get(field) in (None, '', 'NULL')),
                        conflict_details={
                            'field': field,
                            'missing_count': len(missing_rows),
                            'missing_rate': round(missing_rate, 3),
                            'sample_missing': missing_rows[:3]
                        },
                        priority=5 if missing_rate < 0.5 else 7,
                        impact_score=Decimal(str(round(missing_rate * 100, 2))),
                        description=f"Field '{field}' missing in {len(missing_rows)} rows ({missing_rate:.1%})"
                    )
                    conflicts.append(conflict)
        
        except Exception as e:
            logger.error(f"Error detecting missing values: {str(e)}")
        
        return conflicts
    
    def _detect_data_type_issues(self, source: DataSource) -> List[Conflict]:
        """Detect data type inconsistencies."""
        conflicts = []
        
        try:
            row_payloads, _ = self._get_source_rows(source)
            
            # Analyze data types by field
            type_by_field = {}
            inconsistent_fields = {}
            
            for row_data in row_payloads:
                if isinstance(row_data, dict):
                    for field, value in row_data.items():
                        if field not in type_by_field:
                            type_by_field[field] = Counter()
                        
                        value_type = type(value).__name__
                        type_by_field[field][value_type] += 1
            
            # Find inconsistent fields (> 1 type for same field)
            for field, type_counts in type_by_field.items():
                if len(type_counts) > 1:
                    inconsistent_fields[field] = dict(type_counts)
            
            if inconsistent_fields:
                conflict_type, _ = ConflictType.objects.get_or_create(
                    code='DATA_TYPE_MISMATCH',
                    defaults={
                        'name': 'Data Type Mismatch',
                        'severity': 'medium',
                        'description': 'Mixed data types in same column',
                        'auto_resolve': False,
                        'resolution_strategy': 'user_selected'
                    }
                )
                
                conflict = self._create_or_update_conflict(
                    source=source,
                    conflict_type=conflict_type,
                    signature=f"dtype:{','.join(sorted(inconsistent_fields.keys()))}",
                    affected_columns=list(inconsistent_fields.keys()),
                    conflict_details={
                        'inconsistent_fields': inconsistent_fields,
                        'field_count': len(inconsistent_fields)
                    },
                    priority=6,
                    impact_score=Decimal('60.00'),
                    description=f"{len(inconsistent_fields)} fields have mixed data types"
                )
                conflicts.append(conflict)
        
        except Exception as e:
            logger.error(f"Error detecting data type issues: {str(e)}")
        
        return conflicts
    
    def _detect_format_issues(self, source: DataSource) -> List[Conflict]:
        """Detect format inconsistencies (dates, phone numbers, emails, etc.)."""
        conflicts = []
        
        try:
            row_payloads, _ = self._get_source_rows(source)
            
            # Common format patterns
            patterns = {
                'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                'phone': r'^\+?1?\d{9,15}$',
                'date': r'^\d{4}-\d{2}-\d{2}',
                'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            }
            
            format_issues = {}
            
            for row_data in row_payloads:
                if isinstance(row_data, dict):
                    for field, value in row_data.items():
                        if not isinstance(value, str):
                            continue
                        
                        if field not in format_issues:
                            format_issues[field] = {
                                'invalid_count': 0,
                                'detected_format': None,
                                'samples': []
                            }
                        
                        field_hint = field.lower()
                        expected_format = None
                        if any(token in field_hint for token in ['email', 'mail']):
                            expected_format = 'email'
                        elif any(token in field_hint for token in ['phone', 'tel', 'mobile', 'gsm']):
                            expected_format = 'phone'
                        elif any(token in field_hint for token in ['date', 'dt']):
                            expected_format = 'date'
                        elif 'uuid' in field_hint:
                            expected_format = 'uuid'

                        if expected_format:
                            format_issues[field]['detected_format'] = expected_format
                            is_valid = bool(re.match(patterns[expected_format], value))
                        else:
                            is_valid = True
                            for fmt_name, pattern in patterns.items():
                                if re.match(pattern, value):
                                    format_issues[field]['detected_format'] = fmt_name
                                    break

                        if not is_valid and format_issues[field]['detected_format']:
                            format_issues[field]['invalid_count'] += 1
                            if len(format_issues[field]['samples']) < 3:
                                format_issues[field]['samples'].append(value)
            
            # Create conflict for fields with format issues
            issue_fields = {
                k: v for k, v in format_issues.items()
                if v['invalid_count'] > 0 and v['detected_format']
            }
            
            if issue_fields:
                conflict_type, _ = ConflictType.objects.get_or_create(
                    code='FORMAT_INCONSISTENCY',
                    defaults={
                        'name': 'Format Inconsistency',
                        'severity': 'low',
                        'description': 'Values do not match expected format',
                        'auto_resolve': True,
                        'resolution_strategy': 'user_selected'
                    }
                )
                
                conflict = self._create_or_update_conflict(
                    source=source,
                    conflict_type=conflict_type,
                    signature=f"format:{','.join(sorted(issue_fields.keys()))}",
                    affected_columns=list(issue_fields.keys()),
                    affected_row_ids=self._format_issue_row_ids(row_payloads, issue_fields),
                    conflict_details={
                        'format_issues': issue_fields,
                        'field_count': len(issue_fields)
                    },
                    priority=3,
                    impact_score=Decimal('35.00'),
                    description=f"{len(issue_fields)} fields have format inconsistencies"
                )
                conflicts.append(conflict)
        
        except Exception as e:
            logger.error(f"Error detecting format issues: {str(e)}")
        
        return conflicts

    def _row_ids_for_predicate(self, rows: List[Dict[str, Any]], predicate) -> List[int]:
        row_ids: list[int] = []
        for index, row in enumerate(rows, start=1):
            if isinstance(row, dict) and predicate(row):
                row_ids.append(int(row.get('_row_number', index)))
        return row_ids

    def _format_issue_row_ids(self, rows: List[Dict[str, Any]], issue_fields: Dict[str, Any]) -> List[int]:
        row_ids: list[int] = []
        patterns = {
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'phone': r'^\+?1?\d{9,15}$',
            'date': r'^\d{4}-\d{2}-\d{2}',
            'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        }
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            for field, details in issue_fields.items():
                value = row.get(field)
                detected = details.get('detected_format')
                if isinstance(value, str) and detected in patterns and not re.match(patterns[detected], value):
                    row_ids.append(int(row.get('_row_number', index)))
                    break
        return row_ids

    def _detect_partial_duplicate_conflict(self, source: DataSource, row_payloads: List[Dict[str, Any]]) -> Optional[Conflict]:
        keyed_rows: dict[tuple, list[dict[str, Any]]] = {}
        for index, row_data in enumerate(row_payloads, start=1):
            if not isinstance(row_data, dict):
                continue
            order_id = row_data.get('id_commande') or row_data.get('order_id')
            if order_id:
                key = ('id_commande', str(order_id).strip().lower())
            else:
                date = row_data.get('date') or row_data.get('date_commande') or row_data.get('Date vente')
                client = row_data.get('client') or row_data.get('Client_Nom') or row_data.get('customer_code')
                amount = row_data.get('montant_total') or row_data.get('Mont_TTC') or row_data.get('amount')
                if not (date and client and amount):
                    continue
                key = ('business_triplet', str(date).strip(), str(client).strip().lower(), str(amount).strip())
            keyed_rows.setdefault(key, []).append({'row_number': int(row_data.get('_row_number', index)), 'data': row_data})

        conflict_groups = []
        for key, grouped_rows in keyed_rows.items():
            if len(grouped_rows) < 2:
                continue
            normalized_records = [{k: v for k, v in item['data'].items() if k != '_row_number'} for item in grouped_rows]
            unique_snapshots = {json.dumps(record, sort_keys=True, default=str) for record in normalized_records}
            if len(unique_snapshots) > 1:
                conflict_groups.append({
                    'key': key,
                    'rows': grouped_rows,
                })

        if not conflict_groups:
            return None

        conflict_type, _ = ConflictType.objects.get_or_create(
            code='BUSINESS_CONFLICT',
            defaults={
                'name': 'Business Key Conflict',
                'severity': 'high',
                'description': 'Rows share the same business key but disagree on one or more fields',
                'auto_resolve': False,
                'resolution_strategy': 'user_selected',
            }
        )
        sample = conflict_groups[0]
        signature_payload = json.dumps(
            conflict_groups[:5], sort_keys=True, default=str
        ).encode('utf-8')
        return self._create_or_update_conflict(
            source=source,
            conflict_type=conflict_type,
            signature=f"partial-duplicates:{hashlib.md5(signature_payload).hexdigest()}",
            affected_columns=[],
            affected_row_ids=[item['row_number'] for group in conflict_groups for item in group['rows']][:50],
            conflict_details={
                'conflict_group_count': len(conflict_groups),
                'sample_groups': conflict_groups[:3],
            },
            priority=9,
            impact_score=Decimal('90.00'),
            description=f"{len(conflict_groups)} business-key conflicts require M3 resolution",
        )


class ConflictResolutionService:
    """
    Guided workflow for resolving detected conflicts.
    Provides step-by-step users guidance and auto-resolution options.
    """
    
    def __init__(self, user: User):
        self.user = user
    
    def get_conflict_resolution_guidance(self, conflict: Conflict) -> Dict[str, Any]:
        """
        Provides guided suggestions for resolving a conflict.
        Includes: recommended strategy, alternative options, impact analysis.
        
        Args:
            conflict: Conflict instance to resolve
        
        Returns:
            {
                'conflict_id': int,
                'type': str,
                'guidance': str,
                'recommended_strategy': str,
                'alternative_strategies': [str],
                'impact_analysis': {...},
                'steps': [{'step': int, 'description': str, 'action': str}],
                'estimated_effort': str,
                'risk_level': str
            }
        """
        guidance = {
            'conflict_id': conflict.id,
            'conflict_type': conflict.conflict_type.code,
            'affected_fields': conflict.affected_columns or [],
            'affected_rows': len(conflict.affected_row_ids or []),
        }
        
        if conflict.conflict_type.code == 'DUPLICATE_RECORDS':
            guidance.update(self._guide_duplicate_resolution(conflict))
        elif conflict.conflict_type.code == 'MISSING_VALUES':
            guidance.update(self._guide_missing_value_resolution(conflict))
        elif conflict.conflict_type.code == 'DATA_TYPE_MISMATCH':
            guidance.update(self._guide_type_mismatch_resolution(conflict))
        elif conflict.conflict_type.code == 'FORMAT_INCONSISTENCY':
            guidance.update(self._guide_format_resolution(conflict))
        else:
            guidance.update({
                'guidance': f"Conflict type '{conflict.conflict_type.name}' requires manual review",
                'recommended_strategy': 'manual_review',
                'alternative_strategies': [],
                'impact_analysis': {
                    'impact_level': 'Medium',
                    'notes': 'Aucune stratégie standard n’est disponible pour ce type de conflit.',
                },
                'steps': [
                    {
                        'step': 1,
                        'description': 'Review conflict details',
                        'action': 'examine_details'
                    },
                    {
                        'step': 2,
                        'description': 'Decide resolution strategy',
                        'action': 'choose_strategy'
                    }
                ],
                'estimated_effort': 'Medium (10-20 minutes)',
                'risk_level': 'medium'
            })
        
        return guidance
    
    def _guide_duplicate_resolution(self, conflict: Conflict) -> Dict[str, Any]:
        """Guidance for duplicate record conflicts."""
        return {
            'guidance': "Plusieurs lignes semblent représenter la même information. Il faut décider laquelle garder.",
            'recommended_strategy': 'majority_vote',
            'alternative_strategies': ['manual_override', 'discard', 'auto_merge'],
            'impact_analysis': {
                'duplicate_count': conflict.conflict_details.get('duplicate_count', 0),
                'business_effect': 'Évite de compter plusieurs fois la même donnée.',
                'impact_level': 'Faible'
            },
            'steps': [
                {
                    'step': 1,
                    'description': 'Comparer les lignes qui se ressemblent',
                    'action': 'comparer'
                },
                {
                    'step': 2,
                    'description': 'Choisir la valeur ou la ligne à conserver',
                    'action': 'choisir'
                },
                {
                    'step': 3,
                    'description': 'Écarter les doublons inutiles',
                    'action': 'ecarter'
                },
                {
                    'step': 4,
                    'description': 'Vérifier que le résultat reste cohérent',
                    'action': 'verifier'
                }
            ],
            'estimated_effort': 'Court',
            'risk_level': 'Faible'
        }
    
    def _guide_missing_value_resolution(self, conflict: Conflict) -> Dict[str, Any]:
        """Guidance for missing value conflicts."""
        details = conflict.conflict_details
        field = details.get('field', 'Unknown')
        missing_rate = details.get('missing_rate', 0)
        
        return {
            'guidance': f"Le champ '{field}' manque sur une partie des lignes. Il faut décider s'il faut compléter, garder tel quel ou écarter les lignes les plus incomplètes.",
            'recommended_strategy': 'default_value' if missing_rate < 0.5 else 'discard',
            'alternative_strategies': [
                'manual_override', 'default_value', 'discard', 'user_selected'
            ],
            'impact_analysis': {
                'missing_count': details.get('missing_count', 0),
                'missing_rate': missing_rate,
                'business_effect': 'Peut fausser les indicateurs si le champ est important.',
                'impact_level': 'Moyen' if missing_rate > 0.3 else 'Faible'
            },
            'steps': [
                {
                    'step': 1,
                    'description': f'Voir à quel point le champ {field} manque',
                    'action': 'observer'
                },
                {
                    'step': 2,
                    'description': 'Choisir entre compléter, conserver ou écarter',
                    'action': 'choisir'
                },
                {
                    'step': 3,
                    'description': 'Contrôler l’effet de la décision',
                    'action': 'controler'
                },
                {
                    'step': 4,
                    'description': 'Valider la décision',
                    'action': 'valider'
                }
            ],
            'estimated_effort': 'Court',
            'risk_level': 'Faible'
        }
    
    def _guide_type_mismatch_resolution(self, conflict: Conflict) -> Dict[str, Any]:
        """Guidance for data type mismatch conflicts."""
        return {
            'guidance': "Le même champ contient des formats différents. Il faut choisir le format final le plus cohérent pour l'analyse.",
            'recommended_strategy': 'latest_value',
            'alternative_strategies': ['manual_override', 'user_selected', 'discard'],
            'impact_analysis': {
                'affected_fields': len(conflict.affected_columns or []),
                'business_effect': 'Peut empêcher les calculs ou mélanger des valeurs incompatibles.',
                'impact_level': 'Moyen'
            },
            'steps': [
                {
                    'step': 1,
                    'description': 'Voir les formats actuellement mélangés',
                    'action': 'observer'
                },
                {
                    'step': 2,
                    'description': 'Choisir le format final à retenir',
                    'action': 'choisir'
                },
                {
                    'step': 3,
                    'description': 'Vérifier que les valeurs restent compréhensibles',
                    'action': 'controler'
                },
                {
                    'step': 4,
                    'description': 'Appliquer la décision',
                    'action': 'valider'
                }
            ],
            'estimated_effort': 'Moyen',
            'risk_level': 'Moyen'
        }
    
    def _guide_format_resolution(self, conflict: Conflict) -> Dict[str, Any]:
        """Guidance for format inconsistency conflicts."""
        return {
            'guidance': "Des valeurs similaires n'utilisent pas le même format. Il faut les uniformiser pour éviter les écarts de lecture.",
            'recommended_strategy': 'user_selected',
            'alternative_strategies': ['manual_override', 'latest_value', 'discard'],
            'impact_analysis': {
                'affected_fields': len(conflict.affected_columns or []),
                'invalid_count': sum(
                    v.get('invalid_count', 0)
                    for v in conflict.conflict_details.get('format_issues', {}).values()
                ),
                'business_effect': 'Facilite la comparaison et évite les erreurs de regroupement.',
                'impact_level': 'Faible'
            },
            'steps': [
                {
                    'step': 1,
                    'description': 'Voir les formats actuellement rencontrés',
                    'action': 'observer'
                },
                {
                    'step': 2,
                    'description': 'Choisir la forme à garder',
                    'action': 'choisir'
                },
                {
                    'step': 3,
                    'description': 'Contrôler le résultat attendu',
                    'action': 'controler'
                },
                {
                    'step': 4,
                    'description': 'Valider l’uniformisation',
                    'action': 'valider'
                }
            ],
            'estimated_effort': 'Court',
            'risk_level': 'Faible'
        }
    
    def resolve_conflict(
        self,
        conflict: Conflict,
        method: str,
        chosen_value: Any = None,
        notes: str = None,
        requires_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Records and applies a conflict resolution decision.
        
        Args:
            conflict: Conflict to resolve
            method: Resolution method (manual_override, auto_merge, etc.)
            chosen_value: The value chosen (if applicable)
            notes: Resolution notes
            requires_approval: Whether this needs manager approval
        
        Returns:
            {'success': bool, 'resolution_id': int, 'message': str}
        """
        if conflict.status in {'resolved', 'ignored'}:
            return {
                'success': False,
                'message': f'Conflict {conflict.id} is already {conflict.status}.'
            }

        if requires_approval and conflict.conflict_type.severity == 'critical':
            conflict_status = 'resolving'
        else:
            conflict_status = 'resolved'

        with transaction.atomic():
            try:
                rollback_data = {
                    'previous_status': conflict.status,
                    'previous_resolution_summary': conflict.resolution_summary,
                    'previous_resolved_at': conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                }
                resolution = ConflictResolution.objects.create(
                    conflict=conflict,
                    resolution_method=method,
                    chosen_value=chosen_value,
                    alternative_values=conflict.conflict_details,
                    resolution_notes=notes,
                    is_reversible=True,
                    rollback_data=rollback_data,
                    resolved_by=self.user,
                    approval_required=requires_approval,
                    confidence_score=Decimal('85.00')
                )
                
                conflict.status = conflict_status
                conflict.resolved_at = timezone.now() if conflict_status == 'resolved' else None
                conflict.resolution_summary = f"Resolved via {method}: {notes or ''}".strip()
                conflict.save(update_fields=['status', 'resolved_at', 'resolution_summary'])
                
                ActivityLog.objects.create(
                    user=self.user,
                    user_email=getattr(self.user, 'email', None),
                    user_role=getattr(getattr(self.user, 'profile', None), 'role', None),
                    action_type='update',
                    resource_type='Conflict',
                    resource_id=conflict.id,
                    resource_name=f"Resolved conflict {conflict.id}",
                    action_details={
                        'conflict_type': conflict.conflict_type.code,
                        'resolution_method': method,
                        'requires_approval': requires_approval,
                        'status': conflict_status,
                    }
                )
                
                return {
                    'success': True,
                    'resolution_id': resolution.id,
                    'message': f"Conflict resolved using {method}",
                    'status': conflict.status
                }

            except Exception as e:
                logger.exception(f"Error resolving conflict {conflict.id}")
                return {
                    'success': False,
                    'message': f"Failed to resolve conflict: {str(e)}"
                }
