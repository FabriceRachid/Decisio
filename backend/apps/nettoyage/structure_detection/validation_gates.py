"""
Validation gates for structural reconstruction.
Uses Pandera-style checks to verify reconstruction quality before accepting.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    gate_name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    all_passed: bool
    gates: list[GateResult]
    confidence_modifier: float = 0.0
    requires_human_review: bool = False
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'all_passed': self.all_passed,
            'gates': [
                {'gate': g.gate_name, 'passed': g.passed, 'message': g.message, 'details': g.details}
                for g in self.gates
            ],
            'confidence_modifier': self.confidence_modifier,
            'requires_human_review': self.requires_human_review,
            'failure_reasons': self.failure_reasons,
        }


class ValidationGates:
    """
    Validates structural reconstruction proposals against quality gates.
    If any gate fails, the file is flagged for human review.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        self.min_confidence = config.get('min_confidence', 0.5)
        self.max_unresolved_rate = config.get('max_unresolved_rate', 0.15)
        self.min_columns_per_subtable = config.get('min_columns_per_subtable', 2)
        self.min_rows_per_subtable = config.get('min_rows_per_subtable', 3)
        self.max_subtables = config.get('max_subtables', 10)

    def validate(
        self,
        reconstruction_plan: dict[str, Any],
        structural_fingerprint: dict[str, Any],
    ) -> ValidationReport:
        gates = []

        gates.append(self._gate_confidence_score(reconstruction_plan))
        gates.append(self._gate_subtable_structure(reconstruction_plan))
        gates.append(self._gate_column_continuity(reconstruction_plan, structural_fingerprint))
        gates.append(self._gate_unresolved_zones(reconstruction_plan, structural_fingerprint))
        gates.append(self._gate_header_alignment(reconstruction_plan, structural_fingerprint))
        gates.append(self._gate_subtable_count(reconstruction_plan))
        gates.append(self._gate_row_count_consistency(reconstruction_plan, structural_fingerprint))

        type_transform = reconstruction_plan.get('type_transformation')
        if type_transform in ('unpivot', 'mixed'):
            gates.append(self._gate_unpivot_mapping(reconstruction_plan))
            gates.append(self._gate_unpivot_column_existence(reconstruction_plan, structural_fingerprint))

        cell_transforms = reconstruction_plan.get('transformations_cellule', [])
        if cell_transforms:
            for ct in cell_transforms:
                sous_type = ct.get('sous_type', '')
                if sous_type == 'extraction_champs_texte_libre':
                    gates.append(self._gate_text_extraction_empty_rate(ct, structural_fingerprint))
                elif sous_type == 'correction_caracteres_ambigus':
                    gates.append(self._gate_char_correction_completeness(ct))
                elif sous_type == 'scission_valeur_unite':
                    gates.append(self._gate_value_unit_numeric(ct))
                elif sous_type == 'explosion_liste_delimitee':
                    gates.append(self._gate_delimited_list_integrity(ct))

        all_passed = all(g.passed for g in gates)
        failure_reasons = [g.message for g in gates if not g.passed]

        confidence_modifier = 0.0
        if not all_passed:
            critical_failures = sum(1 for g in gates if not g.passed and g.gate_name in (
                'confidence_score', 'subtable_structure', 'header_alignment', 'unpivot_mapping'
            ))
            confidence_modifier = -0.1 * critical_failures

        requires_human_review = not all_passed or any(
            g.gate_name == 'confidence_score' and not g.passed for g in gates
        )

        return ValidationReport(
            all_passed=all_passed,
            gates=gates,
            confidence_modifier=confidence_modifier,
            requires_human_review=requires_human_review,
            failure_reasons=failure_reasons,
        )

    def _gate_confidence_score(self, plan: dict) -> GateResult:
        confidence = float(plan.get('confidence', 0))
        passed = confidence >= self.min_confidence
        return GateResult(
            gate_name='confidence_score',
            passed=passed,
            message=(
                f'Score de confiance {confidence:.2f} >= {self.min_confidence}'
                if passed else
                f'Score de confiance {confidence:.2f} < {self.min_confidence} seuil'
            ),
            details={'confidence': confidence, 'threshold': self.min_confidence},
        )

    def _gate_subtable_structure(self, plan: dict) -> GateResult:
        subtables = plan.get('subtables', [])
        issues = []
        for i, st in enumerate(subtables):
            cols = st.get('columns', st.get('column_names', []))
            if len(cols) < self.min_columns_per_subtable:
                issues.append(f'Sous-tableau {i+1}: {len(cols)} colonne(s) < {self.min_columns_per_subtable} minimum')
            row_count = st.get('row_count', st.get('end_row', 0) - st.get('start_row', 0))
            if row_count > 0 and row_count < self.min_rows_per_subtable:
                issues.append(f'Sous-tableau {i+1}: {row_count} lignes < {self.min_rows_per_subtable} minimum')

        passed = len(issues) == 0
        return GateResult(
            gate_name='subtable_structure',
            passed=passed,
            message='Structure des sous-tableaux valide' if passed else '; '.join(issues),
            details={'subtable_count': len(subtables), 'issues': issues},
        )

    def _gate_column_continuity(self, plan: dict, fp: dict) -> GateResult:
        subtables = plan.get('subtables', [])
        issues = []
        total_cols = fp.get('total_cols', 0)

        for i, st in enumerate(subtables):
            cols = st.get('columns', st.get('column_names', []))
            col_indices = []
            for j, col in enumerate(cols):
                if isinstance(col, dict):
                    col_indices.append(col.get('index', j))
                else:
                    col_indices.append(j)

            if col_indices:
                max_col = max(col_indices)
                if max_col >= total_cols:
                    issues.append(
                        f'Sous-tableau {i+1}: colonne index {max_col} hors limites ({total_cols} colonnes)'
                    )

        passed = len(issues) == 0
        return GateResult(
            gate_name='column_continuity',
            passed=passed,
            message='Continuite des colonnes valide' if passed else '; '.join(issues),
            details={'issues': issues},
        )

    def _gate_unresolved_zones(self, plan: dict, fp: dict) -> GateResult:
        unresolved = plan.get('unresolved_zones', plan.get('ambiguities', []))
        total_cells = fp.get('total_rows', 0) * fp.get('total_cols', 1)
        unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0
        unresolved_rate = unresolved_count / total_cells if total_cells > 0 else 0

        passed = unresolved_rate <= self.max_unresolved_rate
        return GateResult(
            gate_name='unresolved_zones',
            passed=passed,
            message=(
                f'Taux de zones non resolues {unresolved_rate:.2%} <= {self.max_unresolved_rate:.2%}'
                if passed else
                f'Taux de zones non resolues {unresolved_rate:.2%} > {self.max_unresolved_rate:.2%} seuil'
            ),
            details={'unresolved_count': unresolved_count, 'unresolved_rate': unresolved_rate},
        )

    def _gate_header_alignment(self, plan: dict, fp: dict) -> GateResult:
        subtables = plan.get('subtables', [])
        header_candidates = fp.get('header_candidates', [])
        hc = plan.get('hierarchical_crosstab')
        issues = []

        for i, st in enumerate(subtables):
            header_row = st.get('header_row')
            if header_row is not None and header_candidates:
                candidate_rows = [h.get('row_index') for h in header_candidates]
                if header_row not in candidate_rows and header_row >= 0:
                    if hc and header_row in hc.get('header_rows', []):
                        continue
                    issues.append(
                        f'Sous-tableau {i+1}: en-tete ligne {header_row} pas dans les candidats detectes'
                    )

        passed = len(issues) == 0
        return GateResult(
            gate_name='header_alignment',
            passed=passed,
            message='Alignement des en-tetes valide' if passed else '; '.join(issues),
            details={'issues': issues},
        )

    def _gate_subtable_count(self, plan: dict) -> GateResult:
        subtables = plan.get('subtables', [])
        count = len(subtables)
        passed = count <= self.max_subtables
        return GateResult(
            gate_name='subtable_count',
            passed=passed,
            message=(
                f'{count} sous-tableau(x) detecte(s)'
                if passed else
                f'{count} sous-tableaux > {self.max_subtables} maximum'
            ),
            details={'count': count},
        )

    def _gate_row_count_consistency(self, plan: dict, fp: dict) -> GateResult:
        subtables = plan.get('subtables', [])
        total_rows = fp.get('total_rows', 0)
        accounted_rows = 0
        for st in subtables:
            start = st.get('start_row', 0)
            end = st.get('end_row', 0)
            accounted_rows += end - start + 1

        if total_rows > 0:
            coverage = accounted_rows / total_rows
            passed = coverage >= 0.3
        else:
            coverage = 0
            passed = True

        return GateResult(
            gate_name='row_count_consistency',
            passed=passed,
            message=f'Couverture des lignes: {coverage:.1%}',
            details={'total_rows': total_rows, 'accounted_rows': accounted_rows, 'coverage': coverage},
        )

    def _gate_unpivot_mapping(self, plan: dict) -> GateResult:
        mapping = plan.get('mapping_pivot', {})
        issues = []

        id_vars = mapping.get('colonnes_identifiantes', [])
        value_vars = mapping.get('colonnes_valeurs', [])
        var_name = mapping.get('nom_nouvelle_colonne_dimension', '')
        value_name = mapping.get('nom_nouvelle_colonne_valeur', '')

        if not id_vars:
            issues.append("Aucune colonne identifiante specifiee (colonnes_identifiantes)")
        if not value_vars:
            issues.append("Aucune colonne valeur specifiee (colonnes_valeurs)")
        if len(id_vars) + len(value_vars) < 2:
            issues.append("Au moins 2 colonnes au total requises (identifiantes + valeurs)")
        if not var_name:
            issues.append("Nom de colonne dimension manquant (nom_nouvelle_colonne_dimension)")
        if not value_name:
            issues.append("Nom de colonne valeur manquant (nom_nouvelle_colonne_valeur)")
        overlap = set(id_vars) & set(value_vars)
        if overlap:
            issues.append(f"Colonnes en double dans identifiantes/valeurs: {overlap}")

        passed = len(issues) == 0
        return GateResult(
            gate_name='unpivot_mapping',
            passed=passed,
            message='Mapping pivot valide' if passed else '; '.join(issues),
            details={
                'id_vars': id_vars,
                'value_vars': value_vars,
                'var_name': var_name,
                'value_name': value_name,
                'issues': issues,
            },
        )

    def _gate_unpivot_column_existence(self, plan: dict, fp: dict) -> GateResult:
        mapping = plan.get('mapping_pivot', {})
        id_vars = mapping.get('colonnes_identifiantes', [])
        value_vars = mapping.get('colonnes_valeurs', [])
        all_cols = id_vars + value_vars

        hc = plan.get('hierarchical_crosstab')
        if hc:
            return GateResult(
                gate_name='unpivot_column_existence',
                passed=True,
                message='Colonnes pivot validees via crosstab hierarchique',
                details={'hierarchical_crosstab': True},
            )

        col_types = fp.get('column_types', {})
        issues = []

        for col in all_cols:
            if col not in col_types:
                issues.append(f"Colonne '{col}' non trouvee dans les colonnes detectees")

        passed = len(issues) == 0
        return GateResult(
            gate_name='unpivot_column_existence',
            passed=passed,
            message='Colonnes pivot trouvees dans le fichier' if passed else '; '.join(issues),
            details={'missing_columns': issues, 'all_columns': list(col_types.keys())[:20]},
        )

    def _gate_text_extraction_empty_rate(
        self, ct: dict, fp: dict
    ) -> GateResult:
        colonnes_result = ct.get('colonnes_resultantes', [])
        max_empty_rate = ct.get('details', {}).get('max_empty_rate_threshold', 0.05)
        col_types = fp.get('column_types', {})

        issues = []
        for col in colonnes_result:
            detected_type = col_types.get(col, 'unknown')
            if detected_type == 'empty':
                issues.append(f"Colonne resultante '{col}' est vide dans le fingerprint")

        if not issues and not colonnes_result:
            issues.append("Aucune colonne resultante specifiee pour l'extraction")

        passed = len(issues) == 0
        return GateResult(
            gate_name='text_extraction_empty_rate',
            passed=passed,
            message="Taux de vides d'extraction acceptable" if passed else '; '.join(issues),
            details={'colonnes_resultantes': colonnes_result, 'issues': issues},
        )

    def _gate_char_correction_completeness(self, ct: dict) -> GateResult:
        details = ct.get('details', {})
        cas_incertains = details.get('cas_incertains', [])
        niveau_confiance = ct.get('niveau_confiance', 0)

        issues = []
        if cas_incertains:
            issues.append(
                f"{len(cas_incertains)} valeur(s) incertaine(s) requierant revision humaine: "
                f"{cas_incertains[:5]}"
            )

        if niveau_confiance < 0.5:
            issues.append(f"Confiance de correction trop faible: {niveau_confiance}")

        passed = len(issues) == 0
        return GateResult(
            gate_name='char_correction_completeness',
            passed=passed,
            message='Correction de caracteres valide' if passed else '; '.join(issues),
            details={
                'cas_incertains_count': len(cas_incertains),
                'niveau_confiance': niveau_confiance,
                'issues': issues,
            },
        )

    def _gate_value_unit_numeric(self, ct: dict) -> GateResult:
        details = ct.get('details', {})
        col_nombre = details.get('colonne_nombre', '')
        colonnes_result = ct.get('colonnes_resultantes', [])

        issues = []
        if not col_nombre:
            issues.append("colonne_nombre non specifiee dans les details")
        if not colonnes_result:
            issues.append("Aucune colonne resultante specifiee")
        elif col_nombre and col_nombre not in colonnes_result:
            issues.append(f"colonne_nombre '{col_nombre}' absente des colonnes_resultantes")

        passed = len(issues) == 0
        return GateResult(
            gate_name='value_unit_numeric',
            passed=passed,
            message='Scission valeur/unite valide' if passed else '; '.join(issues),
            details={'colonne_nombre': col_nombre, 'colonnes_resultantes': colonnes_result},
        )

    def _gate_delimited_list_integrity(self, ct: dict) -> GateResult:
        details = ct.get('details', {})
        colonnes_liees = details.get('colonnes_liees', [])
        delimiteur = details.get('delimiteur_detecte', '')
        colonnes_a_repeter = details.get('colonnes_a_repeter', [])

        issues = []
        if not delimiteur:
            issues.append(" delimiteur non specifie")
        if len(colonnes_liees) < 2:
            issues.append(
                f"Moins de 2 colonnes liees specifiees ({len(colonnes_liees)}), "
                "explosion inutile"
            )

        overlap = set(colonnes_liees) & set(colonnes_a_repeter)
        if overlap:
            issues.append(f"Colonnes en double entre liees et a repeter: {overlap}")

        passed = len(issues) == 0
        return GateResult(
            gate_name='delimited_list_integrity',
            passed=passed,
            message='Integrite des listes delimitees validee' if passed else '; '.join(issues),
            details={
                'colonnes_liees': colonnes_liees,
                'delimiteur': delimiteur,
                'colonnes_a_repeter': colonnes_a_repeter,
                'issues': issues,
            },
        )
