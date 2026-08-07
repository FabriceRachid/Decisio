"""
Service to convert a reconstruction plan into executable CleaningRule objects.
Bridges the gap between structure detection (M2) and the nettoyage pipeline.
"""
from __future__ import annotations

import logging
from typing import Any

from apps.nettoyage.models import CleaningPipeline, CleaningRule

logger = logging.getLogger(__name__)


class PlanToRulesService:
    """
    Converts a structural reconstruction plan into CleaningRule objects
    that can be executed by the existing nettoyage pipeline.
    """

    def preview_rules(self, *, plan: dict[str, Any], source) -> dict[str, Any]:
        """
        Preview what rules would be generated from a plan, without creating them.
        Returns rule descriptions and estimated impact.
        """
        subtables = plan.get('subtables', [])
        column_renames = plan.get('column_renames', {})
        ambiguities = plan.get('ambiguities', [])
        cell_transforms = plan.get('transformations_cellule', [])

        rules_preview = []

        type_transform = plan.get('type_transformation')
        mapping_pivot = plan.get('mapping_pivot')
        if type_transform in ('unpivot', 'mixed') and mapping_pivot:
            id_vars = mapping_pivot.get('colonnes_identifiantes', [])
            value_vars = mapping_pivot.get('colonnes_valeurs', [])
            var_name = mapping_pivot.get('nom_nouvelle_colonne_dimension', 'Dimension')
            value_name = mapping_pivot.get('nom_nouvelle_colonne_valeur', 'Valeur')
            rules_preview.append({
                'rule_type': 'unpivot',
                'name': f'Depivotter {len(value_vars)} colonnes en format long',
                'description': (
                    f'Colonnes identifiantes: {", ".join(id_vars)}. '
                    f'{len(value_vars)} colonnes de valeurs -> "{var_name}" + "{value_name}". '
                    f'Format large (crosstab) transforme en format long.'
                ),
                'impact': {
                    'type': 'unpivot',
                    'detail': f'{len(value_vars)} colonnes -> 2 nouvelles colonnes',
                },
                'priority': 10,
            })

        if subtables and len(subtables) > 1:
            main_table = max(subtables, key=lambda st: st.get('end_row', 0) - st.get('start_row', 0))
            main_start = main_table.get('start_row', 0)
            main_end = main_table.get('end_row', 0)
            other_count = len(subtables) - 1
            rules_preview.append({
                'rule_type': 'subtable_extraction',
                'name': f'Extraire sous-table principale (lignes {main_start}-{main_end})',
                'description': (
                    f'Detection de {len(subtables)} sous-tables. '
                    f'Conservation de la plus grande ({main_start}-{main_end}), '
                    f'suppression des {other_count} autres.'
                ),
                'impact': {
                    'type': 'row_reduction',
                    'detail': f'{other_count} sous-table(s) supprimee(s)',
                },
                'priority': 10,
            })

        if column_renames:
            examples = list(column_renames.items())[:5]
            rules_preview.append({
                'rule_type': 'rename_columns',
                'name': f'Renommer {len(column_renames)} colonne(s)',
                'description': 'Renommage: ' + ', '.join(f'{k} -> {v}' for k, v in examples),
                'impact': {
                    'type': 'column_rename',
                    'detail': f'{len(column_renames)} colonne(s) renommee(s)',
                },
                'priority': 9,
            })

        for ct in cell_transforms:
            sous_type = ct.get('sous_type', '')
            col_src = ct.get('colonne_source', '')
            if sous_type == 'extraction_champs_texte_libre':
                labels = ct.get('details', {}).get('labels_detectes', [])
                result_cols = ct.get('colonnes_resultantes', [])
                rules_preview.append({
                    'rule_type': 'extract_labeled_fields',
                    'name': f'Extraire champs textuels depuis {col_src}',
                    'description': f'Extraction de {len(labels)} labels ({", ".join(labels[:4])}) vers {len(result_cols)} colonnes.',
                    'impact': {'type': 'column_split', 'detail': f'{col_src} -> {", ".join(result_cols[:4])}'},
                    'priority': 8,
                })
            elif sous_type == 'correction_caracteres_ambigus':
                subs = ct.get('details', {}).get('substitutions_types', {})
                uncertain = ct.get('details', {}).get('cas_incertains', [])
                rules_preview.append({
                    'rule_type': 'fix_ambiguous_chars',
                    'name': f'Corriger caracteres ambigus dans {col_src}',
                    'description': f'{len(subs)} substitution(s), {len(uncertain)} valeur(s) incertaine(s).',
                    'impact': {'type': 'value_correction', 'detail': f'Correction dans {col_src}'},
                    'priority': 7,
                })
            elif sous_type == 'scission_valeur_unite':
                col_nb = ct.get('details', {}).get('colonne_nombre', 'Quantity')
                col_tx = ct.get('details', {}).get('colonne_texte', 'Measure')
                rules_preview.append({
                    'rule_type': 'split_value_unit',
                    'name': f'Scinder valeur/unite depuis {col_src}',
                    'description': f'{col_src} -> {col_nb} (numerique) + {col_tx} (texte).',
                    'impact': {'type': 'column_split', 'detail': f'{col_src} -> {col_nb}, {col_tx}'},
                    'priority': 7,
                })
            elif sous_type == 'explosion_liste_delimitee':
                delim = ct.get('details', {}).get('delimiteur_detecte', '|')
                liees = ct.get('details', {}).get('colonnes_liees', [])
                repeter = ct.get('details', {}).get('colonnes_a_repeter', [])
                rules_preview.append({
                    'rule_type': 'explode_delimited_list',
                    'name': f'Exploser listes delimitees ({delim})',
                    'description': f'Colonnes liees: {", ".join(liees)}. Repetition: {", ".join(repeter)}.',
                    'impact': {'type': 'row_explosion', 'detail': f'Explosion sur {len(liees)} colonnes'},
                    'priority': 6,
                })

        rules_preview.append({
            'rule_type': 'remove_empty_rows',
            'name': 'Supprimer lignes vides',
            'description': 'Suppression des lignes entierement vides ou sans donnees significatives.',
            'impact': {
                'type': 'row_removal',
                'detail': 'Lignes 100% nulles supprimees',
            },
            'priority': 8,
        })

        rules_preview.append({
            'rule_type': 'drop_blank_columns',
            'name': 'Supprimer colonnes vides',
            'description': 'Suppression des colonnes avec >95% de valeurs nulles.',
            'impact': {
                'type': 'column_removal',
                'detail': 'Colonnes quasivides supprimees',
            },
            'priority': 7,
        })

        if ambiguities:
            rules_preview.append({
                'rule_type': 'validation',
                'name': f'Validation structurelle ({len(ambiguities)} anomalie(s))',
                'description': 'Marque les anomalies detectees pour review.',
                'impact': {
                    'type': 'flagging',
                    'detail': f'{len(ambiguities)} anomalie(s) signalee(s)',
                },
                'priority': 5,
            })

        return {
            'rules': rules_preview,
            'total_rules': len(rules_preview),
            'plan_summary': {
                'subtables_count': len(subtables),
                'renames_count': len(column_renames),
                'ambiguities_count': len(ambiguities),
                'cell_transforms_count': len(cell_transforms),
                'unpivot_count': 1 if type_transform in ('unpivot', 'mixed') and mapping_pivot else 0,
                'confidence': plan.get('confidence', 0),
            },
        }

    def apply_plan_to_source(self, *, plan: dict[str, Any], source, user) -> dict[str, Any]:
        """
        Main entry: take a reconstruction plan and source, create rules and pipeline,
        then optionally execute cleaning.
        Returns summary of created rules.
        """
        rules_created = []
        pipeline = None

        subtables = plan.get('subtables', [])
        column_renames = plan.get('column_renames', {})
        header_adjustments = plan.get('header_adjustments', [])
        ambiguities = plan.get('ambiguities', [])
        unresolved_zones = plan.get('unresolved_zones', [])
        cell_transforms = plan.get('transformations_cellule', [])
        type_transform = plan.get('type_transformation')
        mapping_pivot = plan.get('mapping_pivot')

        if type_transform in ('unpivot', 'mixed') and mapping_pivot:
            rule = self._create_unpivot_rule(
                mapping_pivot=mapping_pivot,
                source=source,
                user=user,
            )
            if rule:
                rules_created.append(rule)

        if subtables and len(subtables) > 1:
            rule = self._create_subtable_extraction_rule(
                subtables=subtables,
                source=source,
                user=user,
            )
            if rule:
                rules_created.append(rule)

        if column_renames:
            rule = self._create_rename_columns_rule(
                column_renames=column_renames,
                source=source,
                user=user,
            )
            if rule:
                rules_created.append(rule)

        for ct in cell_transforms:
            rule = self._create_cell_level_rule(
                transformation=ct,
                source=source,
                user=user,
            )
            if rule:
                rules_created.append(rule)

        blank_row_rule = self._create_remove_empty_rows_rule(
            subtables=subtables,
            source=source,
            user=user,
        )
        if blank_row_rule:
            rules_created.append(blank_row_rule)

        blank_col_rule = self._create_drop_blank_columns_rule(
            subtables=subtables,
            source=source,
            user=user,
        )
        if blank_col_rule:
            rules_created.append(blank_col_rule)

        if ambiguities:
            rule = self._create_validation_rule(
                ambiguities=ambiguities,
                source=source,
                user=user,
            )
            if rule:
                rules_created.append(rule)

        if rules_created:
            pipeline = self._create_pipeline(
                name=f"Reconstruction auto - {source.name}",
                description="Pipeline genere automatiquement depuis la detection structurale",
                rules=rules_created,
                user=user,
            )

        return {
            'rules_created': [
                {
                    'id': r.id,
                    'name': r.name,
                    'rule_type': r.rule_type,
                    'parameters': r.parameters,
                }
                for r in rules_created
            ],
            'pipeline_id': pipeline.id if pipeline else None,
            'pipeline_name': pipeline.name if pipeline else None,
            'total_rules': len(rules_created),
        }

    def execute_plan(self, *, plan: dict[str, Any], source, user) -> dict[str, Any]:
        """
        Apply plan rules and execute cleaning immediately.
        Returns cleaning job result.
        """
        from apps.nettoyage.services import apply_cleaning

        result = self.apply_plan_to_source(plan=plan, source=source, user=user)
        pipeline_id = result.get('pipeline_id')

        if not pipeline_id:
            return {
                'status': 'no_rules',
                'message': 'Le plan de reconstruction ne genere aucune regle applicable.',
                **result,
            }

        cleaning_result = apply_cleaning(
            source=source,
            user=user,
            pipeline_id=pipeline_id,
            rule_ids=None,
            include_all_auto_rules=False,
            quality_gate={},
        )

        return {
            'status': 'completed',
            'cleaning_result': cleaning_result,
            **result,
        }

    def _create_subtable_extraction_rule(
        self, subtables: list[dict], source, user
    ) -> CleaningRule | None:
        """
        When multiple subtables are detected, create a rule that keeps only
        the main subtable (largest by row count) and removes the rest.
        """
        if len(subtables) < 2:
            return None

        main_table = max(subtables, key=lambda st: st.get('end_row', 0) - st.get('start_row', 0))
        main_start = main_table.get('start_row', 0)
        main_end = main_table.get('end_row', 0)

        other_ranges = []
        for st in subtables:
            if st.get('index') == main_table.get('index'):
                continue
            other_ranges.append({
                'start': st.get('start_row', 0),
                'end': st.get('end_row', 0),
            })

        rule = CleaningRule.objects.create(
            name=f"Extraire sous-table principale (lignes {main_start}-{main_end})",
            description=(
                f"Detection de {len(subtables)} sous-tables. "
                f"Conservation de la sous-table principale (lignes {main_start} a {main_end})."
            ),
            rule_type='drop_rows_by_missing_threshold',
            parameters={
                'threshold': 0.5,
                '_structure_note': {
                    'action': 'keep_main_subtable',
                    'main_range': [main_start, main_end],
                    'other_ranges': other_ranges,
                },
            },
            priority=10,
            category='structural_reconstruction',
            tags=['auto_generated', 'structural', 'subtable'],
            created_by=user,
        )
        logger.info(f"Created subtable extraction rule: {rule.id}")
        return rule

    def _create_rename_columns_rule(
        self, column_renames: dict[str, str], source, user
    ) -> CleaningRule | None:
        """
        Create a rename_columns rule from the plan's column_renames.
        """
        if not column_renames:
            return None

        rule = CleaningRule.objects.create(
            name=f"Renommer {len(column_renames)} colonne(s)",
            description=f"Renommage automatique: {', '.join(f'{k}->{v}' for k, v in list(column_renames.items())[:5])}",
            rule_type='rename_columns',
            parameters={'mapping': column_renames},
            priority=9,
            category='structural_reconstruction',
            tags=['auto_generated', 'structural', 'rename'],
            created_by=user,
        )
        logger.info(f"Created rename columns rule: {rule.id}")
        return rule

    def _create_unpivot_rule(
        self, mapping_pivot: dict[str, Any], source, user
    ) -> CleaningRule | None:
        if not mapping_pivot:
            return None
        id_vars = mapping_pivot.get('colonnes_identifiantes', [])
        value_vars = mapping_pivot.get('colonnes_valeurs', [])
        var_name = mapping_pivot.get('nom_nouvelle_colonne_dimension', 'Dimension')
        value_name = mapping_pivot.get('nom_nouvelle_colonne_valeur', 'Valeur')
        file_path = ''
        if source and hasattr(source, 'file_path'):
            file_path = source.file_path or ''
        rule = CleaningRule.objects.create(
            name=f'Depivotter {len(value_vars)} colonnes (crosstab -> long)',
            description=(
                f'Format large transforme en format long. '
                f'Identifiants: {", ".join(id_vars)}. '
                f'{len(value_vars)} colonnes -> "{var_name}" + "{value_name}".'
            ),
            rule_type='unpivot',
            parameters={
                'colonnes_identifiantes': id_vars,
                'colonnes_valeurs': value_vars,
                'nom_nouvelle_colonne_dimension': var_name,
                'nom_nouvelle_colonne_valeur': value_name,
                'header_row_index': mapping_pivot.get('header_row_index'),
                'value_col_indices': mapping_pivot.get('value_col_indices'),
                'unpivot_map': mapping_pivot.get('unpivot_map', []),
                'source_file_path': file_path,
            },
            priority=10,
            category='structural_reconstruction',
            tags=['auto_generated', 'structural', 'unpivot'],
            created_by=user,
        )
        logger.info(f"Created unpivot rule: {rule.id}")
        return rule

    def _create_remove_empty_rows_rule(
        self, subtables: list[dict], source, user
    ) -> CleaningRule | None:
        """
        Create a remove_empty_rows rule. If subtables are detected,
        target only the blank rows between them.
        """
        rule = CleaningRule.objects.create(
            name="Supprimer lignes vides",
            description="Suppression des lignes entierement vides detectees par l'analyse structurale.",
            rule_type='remove_empty_rows',
            parameters={},
            priority=8,
            category='structural_reconstruction',
            tags=['auto_generated', 'structural', 'empty_rows'],
            created_by=user,
        )
        logger.info(f"Created remove empty rows rule: {rule.id}")
        return rule

    def _create_drop_blank_columns_rule(
        self, subtables: list[dict], source, user
    ) -> CleaningRule | None:
        """
        Create a drop_columns rule for columns that are entirely blank.
        """
        rule = CleaningRule.objects.create(
            name="Supprimer colonnes vides",
            description="Suppression des colonnes entierement vides ou sans donnees significatives.",
            rule_type='drop_columns_by_missing_threshold',
            parameters={'threshold': 0.95},
            priority=7,
            category='structural_reconstruction',
            tags=['auto_generated', 'structural', 'blank_columns'],
            created_by=user,
        )
        logger.info(f"Created drop blank columns rule: {rule.id}")
        return rule

    def _create_validation_rule(
        self, ambiguities: list[dict], source, user
    ) -> CleaningRule | None:
        """
        Create a validate_format rule for columns with detected issues.
        """
        issues_text = '; '.join(str(a) for a in ambiguities[:5])
        rule = CleaningRule.objects.create(
            name=f"Validation structurelle ({len(ambiguities)} anomalie(s))",
            description=f"Marque les problemes detectes: {issues_text}",
            rule_type='validate_format',
            parameters={
                'pattern': '.*',
                '_structure_note': {
                    'action': 'flag_ambiguities',
                    'ambiguities': ambiguities,
                },
            },
            priority=5,
            category='structural_reconstruction',
            tags=['auto_generated', 'structural', 'validation'],
            created_by=user,
        )
        logger.info(f"Created validation rule: {rule.id}")
        return rule

    def _create_cell_level_rule(
        self, transformation: dict[str, Any], source, user
    ) -> CleaningRule | None:
        """Create a CleaningRule for a cell-level transformation."""
        sous_type = transformation.get('sous_type', '')
        col_source = transformation.get('colonne_source', '')
        confidence = transformation.get('niveau_confiance', 0.5)

        if sous_type == 'extraction_champs_texte_libre':
            details = transformation.get('details', {})
            labels = details.get('labels_detectes', [])
            result_cols = transformation.get('colonnes_resultantes', [])
            if not col_source or not labels or not result_cols:
                return None
            rule = CleaningRule.objects.create(
                name=f"Extraire champs textuels depuis {col_source}",
                description=f"Extraction de {len(labels)} labels depuis {col_source} vers {', '.join(result_cols[:4])}",
                rule_type='extract_labeled_fields',
                parameters={
                    'source_column': col_source,
                    'labels': labels,
                    'result_columns': result_cols,
                    '_cell_level': True,
                    '_confidence': confidence,
                },
                priority=8,
                category='structural_reconstruction',
                tags=['auto_generated', 'cell_level', 'extraction'],
                created_by=user,
            )
            logger.info(f"Created extract_labeled_fields rule: {rule.id}")
            return rule

        elif sous_type == 'correction_caracteres_ambigus':
            details = transformation.get('details', {})
            subs = details.get('substitutions_types', {})
            cas_incertains = details.get('cas_incertains', [])
            if not col_source or not subs:
                return None
            rule = CleaningRule.objects.create(
                name=f"Corriger caracteres ambigus dans {col_source}",
                description=f"{len(subs)} substitution(s) dans {col_source}, {len(cas_incertains)} valeur(s) incertaine(s)",
                rule_type='fix_ambiguous_chars',
                column_names=[col_source],
                parameters={
                    'substitutions': subs,
                    'cas_incertains': cas_incertains,
                    '_cell_level': True,
                    '_confidence': confidence,
                },
                priority=7,
                category='structural_reconstruction',
                tags=['auto_generated', 'cell_level', 'char_correction'],
                created_by=user,
            )
            logger.info(f"Created fix_ambiguous_chars rule: {rule.id}")
            return rule

        elif sous_type == 'scission_valeur_unite':
            details = transformation.get('details', {})
            col_nb = details.get('colonne_nombre', 'Quantity')
            col_tx = details.get('colonne_texte', 'Measure')
            if not col_source:
                return None
            rule = CleaningRule.objects.create(
                name=f"Scinder valeur/unite depuis {col_source}",
                description=f"{col_source} -> {col_nb} (numerique) + {col_tx} (texte)",
                rule_type='split_value_unit',
                parameters={
                    'source_column': col_source,
                    'target_number_column': col_nb,
                    'target_text_column': col_tx,
                    '_cell_level': True,
                    '_confidence': confidence,
                },
                priority=7,
                category='structural_reconstruction',
                tags=['auto_generated', 'cell_level', 'split'],
                created_by=user,
            )
            logger.info(f"Created split_value_unit rule: {rule.id}")
            return rule

        elif sous_type == 'explosion_liste_delimitee':
            details = transformation.get('details', {})
            delimiteur = details.get('delimiteur_detecte', '|')
            colonnes_liees = details.get('colonnes_liees', [])
            colonnes_a_repeter = details.get('colonnes_a_repeter', [])
            if not colonnes_liees:
                return None
            rule = CleaningRule.objects.create(
                name=f"Exploser listes delimitees ({delimiteur})",
                description=f"Explosion de {len(colonnes_liees)} colonnes liees avec delimiteur '{delimiteur}'",
                rule_type='explode_delimited_list',
                parameters={
                    'colonnes_liees': colonnes_liees,
                    'delimiteur': delimiteur,
                    'colonnes_a_repeter': colonnes_a_repeter,
                    '_cell_level': True,
                    '_confidence': confidence,
                },
                priority=6,
                category='structural_reconstruction',
                tags=['auto_generated', 'cell_level', 'explode'],
                created_by=user,
            )
            logger.info(f"Created explode_delimited_list rule: {rule.id}")
            return rule

        return None

    def _create_pipeline(
        self, name: str, description: str, rules: list[CleaningRule], user
    ) -> CleaningPipeline:
        """
        Create a CleaningPipeline that groups all auto-generated rules.
        """
        from django.utils import timezone
        ts = timezone.now().strftime('%Y%m%d%H%M%S')
        pipeline = CleaningPipeline.objects.create(
            name=f"{name} ({ts})",
            description=description,
            is_active=True,
            apply_to_all=False,
            created_by=user,
        )
        pipeline.rules.set(rules)
        logger.info(f"Created pipeline '{name}' with {len(rules)} rules")
        return pipeline
