"""
Orchestrator for the intelligent structural detection pipeline.
Coordinates: heuristic detection → LLM (if needed) → validation gates → human review queue.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from django.conf import settings

from apps.nettoyage.structure_detection.heuristic_detector import HeuristicDetector
from apps.nettoyage.structure_detection.llm_service import LLMReconstructionService
from apps.nettoyage.structure_detection.validation_gates import ValidationGates
from apps.nettoyage.structure_detection.correction_memory import CorrectionMemory

logger = logging.getLogger(__name__)


class StructureDetectionOrchestrator:
    """
    Orchestrates the full structural detection pipeline:
    1. Heuristic detection (fast, no LLM)
    2. If low confidence → LLM call with correction examples
    3. Validation gates
    4. If gates fail → human review queue
    """

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        self.confidence_threshold = config.get(
            'confidence_threshold',
            getattr(settings, 'STRUCTURE_DETECTION_CONFIDENCE_THRESHOLD', 0.8),
        )
        self.heuristic = HeuristicDetector()
        self.llm_service = LLMReconstructionService()
        self.validation_gates = ValidationGates(config.get('validation_config'))
        self.correction_memory = CorrectionMemory()

    def detect_and_reconstruct(
        self,
        file_path: str,
        sheet_name: str | None = None,
        source_id: int | None = None,
        force_llm: bool = False,
    ) -> dict[str, Any]:
        """
        Full pipeline: detect structure, optionally call LLM, validate, return plan.
        """
        start_time = time.time()
        result = {
            'method_used': 'heuristic',
            'status': 'completed',
            'structural_fingerprint': None,
            'reconstruction_plan': None,
            'validation_report': None,
            'confidence_score': 0,
            'requires_human_review': False,
            'correction_examples_used': [],
            'duration_ms': 0,
            'error': None,
        }

        try:
            logger.info(f"Starting structural detection for {file_path} (sheet={sheet_name})")

            fp = self.heuristic.detect_from_file(file_path, sheet_name)
            fp_dict = fp.to_dict()
            result['structural_fingerprint'] = fp_dict

            logger.info(
                f"Heuristic detection complete: confidence={fp.confidence}, "
                f"subtables={len(fp.subtables)}, issues={len(fp.issues)}"
            )

            if fp.confidence >= self.confidence_threshold and not force_llm:
                logger.info(f"High confidence ({fp.confidence} >= {self.confidence_threshold}), skipping LLM")
                plan = self._build_plan_from_fingerprint(fp)
                result['reconstruction_plan'] = plan
                result['confidence_score'] = fp.confidence
                result['method_used'] = 'heuristic'
            else:
                logger.info(f"Low confidence ({fp.confidence}) or forced LLM, calling LLM service")
                result['method_used'] = 'llm'

                try:
                    similar_corrections = self.correction_memory.find_similar(fp_dict, limit=5)
                except Exception as e:
                    logger.warning(f"Correction memory search failed: {e}")
                    similar_corrections = []
                result['correction_examples_used'] = [c.get('id') for c in similar_corrections]

                llm_response = self.llm_service.propose_reconstruction(
                    fp_dict, similar_corrections
                )

                if llm_response.get('success'):
                    result['reconstruction_plan'] = llm_response.get('reconstruction_plan')
                    result['confidence_score'] = llm_response.get('confidence', 0.5)
                    result['llm_model'] = llm_response.get('llm_model', '')
                    result['llm_tokens_used'] = llm_response.get('llm_tokens_used', 0)
                    result['llm_duration_ms'] = llm_response.get('llm_duration_ms', 0)
                else:
                    logger.warning(f"LLM call failed: {llm_response.get('error')}")
                    plan = self._build_plan_from_fingerprint(fp)
                    result['reconstruction_plan'] = plan
                    result['confidence_score'] = fp.confidence
                    result['error'] = llm_response.get('error')

            validation = self.validation_gates.validate(
                result['reconstruction_plan'] or {}, fp_dict
            )
            result['validation_report'] = validation.to_dict()

            result['confidence_score'] = max(0, min(1,
                result['confidence_score'] + validation.confidence_modifier
            ))

            if validation.requires_human_review:
                result['requires_human_review'] = True
                result['status'] = 'awaiting_review'
                logger.info("File flagged for human review")

        except Exception as e:
            logger.exception(f"Structural detection failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)

        result['duration_ms'] = int((time.time() - start_time) * 1000)
        return result

    def detect_from_dataframe(
        self,
        df,
        sheet_name: str = '',
        source_id: int | None = None,
        force_llm: bool = False,
    ) -> dict[str, Any]:
        """Detect structure from an in-memory DataFrame."""
        start_time = time.time()
        result = {
            'method_used': 'heuristic',
            'status': 'completed',
            'structural_fingerprint': None,
            'reconstruction_plan': None,
            'validation_report': None,
            'confidence_score': 0,
            'requires_human_review': False,
            'correction_examples_used': [],
            'duration_ms': 0,
            'error': None,
        }

        try:
            fp = self.heuristic.detect_from_dataframe(df, sheet_name)
            fp_dict = fp.to_dict()
            result['structural_fingerprint'] = fp_dict

            if fp.confidence >= self.confidence_threshold and not force_llm:
                plan = self._build_plan_from_fingerprint(fp)
                result['reconstruction_plan'] = plan
                result['confidence_score'] = fp.confidence
                result['method_used'] = 'heuristic'
            else:
                result['method_used'] = 'llm'
                try:
                    similar_corrections = self.correction_memory.find_similar(fp_dict, limit=5)
                except Exception as e:
                    logger.warning(f"Correction memory search failed: {e}")
                    similar_corrections = []
                result['correction_examples_used'] = [c.get('id') for c in similar_corrections]

                llm_response = self.llm_service.propose_reconstruction(
                    fp_dict, similar_corrections
                )

                if llm_response.get('success'):
                    result['reconstruction_plan'] = llm_response.get('reconstruction_plan')
                    result['confidence_score'] = llm_response.get('confidence', 0.5)
                else:
                    plan = self._build_plan_from_fingerprint(fp)
                    result['reconstruction_plan'] = plan
                    result['confidence_score'] = fp.confidence
                    result['error'] = llm_response.get('error')

            validation = self.validation_gates.validate(
                result['reconstruction_plan'] or {}, fp_dict
            )
            result['validation_report'] = validation.to_dict()
            result['confidence_score'] = max(0, min(1,
                result['confidence_score'] + validation.confidence_modifier
            ))

            if validation.requires_human_review:
                result['requires_human_review'] = True
                result['status'] = 'awaiting_review'

        except Exception as e:
            logger.exception(f"Structural detection from DataFrame failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)

        result['duration_ms'] = int((time.time() - start_time) * 1000)
        return result

    def _build_plan_from_fingerprint(self, fp) -> dict[str, Any]:
        subtables = []
        for i, st in enumerate(fp.subtables):
            subtables.append({
                'index': i,
                'start_row': st.start_row,
                'end_row': st.end_row,
                'start_col': st.start_col,
                'end_col': st.end_col,
                'header_row': st.header_row or st.start_row,
                'column_names': st.column_names or [f'col_{j}' for j in range(st.start_col, st.end_col + 1)],
                'action': 'keep',
            })

        has_blank_rows = len(fp.blank_rows) > 0
        has_blank_cols = len(fp.blank_cols) > 0
        has_multiple_subtables = len(fp.subtables) > 1
        has_hc = bool(fp.hierarchical_crosstab)

        plan = {
            'subtables': subtables,
            'header_adjustments': [],
            'column_renames': {},
            'unresolved_zones': [],
            'ambiguities': fp.issues,
            'confidence': fp.confidence,
            'source': 'heuristic',
        }

        if has_blank_rows:
            plan['blank_rows'] = fp.blank_rows
        if has_blank_cols:
            plan['blank_cols'] = fp.blank_cols

        if has_hc:
            hc = fp.hierarchical_crosstab
            key_cols = hc.get('key_cols', [])
            value_cols = hc.get('value_cols', [])
            unpivot_map = hc.get('unpivot_map', [])

            raw_header_rows = []
            if hasattr(fp, '_sample_data') and fp._sample_data:
                raw_header_rows = fp._sample_data.get('raw_header_rows', [])

            id_var_names = []
            header_row_idx = hc.get('header_rows', [0])[-1] if hc.get('header_rows') else 0
            for kc in key_cols:
                name = None
                if header_row_idx < len(raw_header_rows) and kc < len(raw_header_rows[header_row_idx]):
                    val = raw_header_rows[header_row_idx][kc]
                    if val and str(val).strip():
                        name = str(val).strip()
                id_var_names.append(name or f'col_{kc}')

            dim_headers = hc.get('dim_headers', [])
            id_set = set(id_var_names)
            dim_names = [dh for dh in dim_headers if dh and not dh.startswith('Niveau') and dh not in id_set]

            mapping_pivot = {
                'colonnes_identifiantes': id_var_names,
                'colonnes_valeurs': [f'col_{vc}' for vc in value_cols],
                'nom_nouvelle_colonne_dimension': ' | '.join(dim_names) if dim_names else 'Dimension',
                'nom_nouvelle_colonne_valeur': 'Montant',
                'header_row_index': hc.get('header_rows', [0])[-1] if hc.get('header_rows') else 0,
                'value_col_indices': value_cols,
                'unpivot_map': unpivot_map,
            }

            plan['type_transformation'] = 'unpivot'
            plan['mapping_pivot'] = mapping_pivot
            plan['hierarchical_crosstab'] = hc

        elif has_blank_rows or has_blank_cols or has_multiple_subtables:
            plan['type_transformation'] = 'structural_cleanup'

        return plan
