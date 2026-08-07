"""
Correction memory service using pgvector for similarity search.
Stores human-validated structural corrections as embeddings
and retrieves the most relevant ones for LLM few-shot prompting.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

import numpy as np
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

_model_loaded = False
_model_lock = threading.Lock()


def _background_load_model():
    global _model_loaded
    model_name = getattr(
        settings, 'STRUCTURE_DETECTION_EMBEDDING_MODEL', 'all-MiniLM-L6-v2'
    )
    try:
        from sentence_transformers import SentenceTransformer
        CorrectionMemory._class_model = SentenceTransformer(model_name)
        logger.info(f"SentenceTransformer model '{model_name}' loaded in background")
    except ImportError:
        logger.warning("sentence-transformers not installed, using fallback hashing")
        CorrectionMemory._class_load_failed = True
    except Exception as e:
        logger.warning(f"Failed to load SentenceTransformer ({e}), using fallback hashing")
        CorrectionMemory._class_load_failed = True
    finally:
        _model_loaded = True


def _ensure_model_loaded():
    global _model_loaded
    if _model_loaded:
        return
    with _model_lock:
        if _model_loaded:
            return
        t = threading.Thread(target=_background_load_model, daemon=True)
        t.start()
        _model_loaded = True


class CorrectionMemory:
    """
    Manages the correction memory with pgvector embeddings.
    Uses sentence-transformers for local embedding generation.
    """
    _class_model = None
    _class_load_failed = False

    def __init__(self):
        pass

    @property
    def model(self):
        if CorrectionMemory._class_model is not None:
            return CorrectionMemory._class_model
        if CorrectionMemory._class_load_failed:
            return None
        _ensure_model_loaded()
        return CorrectionMemory._class_model

    def generate_embedding(self, structural_fingerprint: dict[str, Any]) -> list[float]:
        """Generate an embedding vector from a structural fingerprint."""
        text = self._fingerprint_to_text(structural_fingerprint)

        if self.model is not None:
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        else:
            return self._hash_embedding(text)

    def store_correction(
        self,
        structural_before: dict[str, Any],
        structural_after: dict[str, Any],
        reconstruction_plan: dict[str, Any],
        description: str,
        correction_type: str,
        source_id: int | None = None,
        snapshot_id: int | None = None,
        user_id: int | None = None,
        sous_type_transformation: str = '',
    ) -> int:
        """Store a new correction example with its embedding."""
        from apps.nettoyage.structure_models import CorrectionExample

        embedding = self.generate_embedding(structural_before)
        embedding_bytes = self._list_to_pgvector(embedding)

        correction = CorrectionExample.objects.create(
            source_id=source_id,
            snapshot_id=snapshot_id,
            structural_before=structural_before,
            structural_after=structural_after,
            reconstruction_plan=reconstruction_plan,
            description=description,
            correction_type=correction_type,
            sous_type_transformation=sous_type_transformation,
            embedding=embedding_bytes,
            created_by_id=user_id,
            is_validated=True,
        )

        logger.info(f"Stored correction example {correction.id} (type={correction_type})")
        return correction.id

    def find_similar(
        self,
        structural_fingerprint: dict[str, Any],
        limit: int = 5,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Find the most similar correction examples using pgvector cosine search."""
        from apps.nettoyage.structure_models import CorrectionExample

        embedding = self.generate_embedding(structural_fingerprint)

        try:
            with connection.cursor() as cursor:
                pgvector_str = self._list_to_pgvector_sql(embedding)
                cursor.execute(
                    """
                    SELECT id, structural_before, structural_after, reconstruction_plan,
                           description, correction_type, created_by_id,
                           1 - (embedding::vector <=> %s::vector) as similarity
                    FROM nettoyage_correctionexample
                    WHERE is_validated = true
                      AND embedding IS NOT NULL
                      AND 1 - (embedding::vector <=> %s::vector) >= %s
                    ORDER BY embedding::vector <=> %s::vector
                    LIMIT %s
                    """,
                    [pgvector_str, pgvector_str, min_similarity, pgvector_str, limit],
                )
                columns = [col[0] for col in cursor.description]
                results = []
                for row in cursor.fetchall():
                    row_dict = dict(zip(columns, row))
                    row_dict['similarity'] = float(row_dict['similarity'])
                    if isinstance(row_dict.get('structural_before'), str):
                        row_dict['structural_before'] = json.loads(row_dict['structural_before'])
                    if isinstance(row_dict.get('structural_after'), str):
                        row_dict['structural_after'] = json.loads(row_dict['structural_after'])
                    if isinstance(row_dict.get('reconstruction_plan'), str):
                        row_dict['reconstruction_plan'] = json.loads(row_dict['reconstruction_plan'])
                    results.append(row_dict)
                return results

        except Exception as e:
            logger.warning(f"pgvector search failed, falling back to in-memory: {e}")
            return self._fallback_search(structural_fingerprint, limit, min_similarity)

    def _fallback_search(
        self,
        structural_fingerprint: dict[str, Any],
        limit: int,
        min_similarity: float,
    ) -> list[dict[str, Any]]:
        """Fallback search using Python when pgvector is unavailable."""
        from apps.nettoyage.structure_models import CorrectionExample

        corrections = CorrectionExample.objects.filter(
            is_validated=True,
            embedding__isnull=False,
        ).order_by('-created_at')[:100]

        target_embedding = np.array(self.generate_embedding(structural_fingerprint))
        results = []

        for c in corrections:
            try:
                stored = np.array(self._pgvector_to_list(c.embedding))
                similarity = float(np.dot(target_embedding, stored) / (
                    np.linalg.norm(target_embedding) * np.linalg.norm(stored) + 1e-8
                ))
                if similarity >= min_similarity:
                    results.append({
                        'id': c.id,
                        'structural_before': c.structural_before,
                        'structural_after': c.structural_after,
                        'reconstruction_plan': c.reconstruction_plan,
                        'description': c.description,
                        'correction_type': c.correction_type,
                        'created_by_id': c.created_by_id,
                        'similarity': similarity,
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]

    def _fingerprint_to_text(self, fp: dict[str, Any]) -> str:
        parts = []
        parts.append(f"rows={fp.get('total_rows', 0)} cols={fp.get('total_cols', 0)}")
        parts.append(f"merged={len(fp.get('merged_cells', []))}")
        parts.append(f"blank_rows={len(fp.get('blank_rows', []))}")
        parts.append(f"blank_cols={len(fp.get('blank_cols', []))}")
        parts.append(f"subtables={len(fp.get('subtables', []))}")
        parts.append(f"headers={len(fp.get('header_candidates', []))}")

        col_types = fp.get('column_types', {})
        if col_types:
            type_counts = {}
            for t in col_types.values():
                type_counts[t] = type_counts.get(t, 0) + 1
            parts.append(f"col_types={type_counts}")

        issues = fp.get('issues', [])
        if issues:
            parts.append(f"issues={len(issues)}")

        return ' | '.join(parts)

    def _hash_embedding(self, text: str) -> list[float]:
        """Deterministic hash-based embedding fallback (384-dim)."""
        import hashlib
        dim = 384
        embedding = np.zeros(dim)
        for i, char in enumerate(text):
            h = hashlib.md5(f"{char}_{i}".encode()).hexdigest()
            val = int(h[:8], 16) / 0xFFFFFFFF
            embedding[i % dim] += val
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding.tolist()

    def _list_to_pgvector(self, vec: list[float]) -> bytes:
        import struct
        dim = len(vec)
        return struct.pack(f'{dim}f', *vec)

    def _list_to_pgvector_sql(self, vec: list[float]) -> str:
        return '[' + ','.join(f'{v:.6f}' for v in vec) + ']'

    def _pgvector_to_list(self, pgvector_bytes) -> list[float]:
        if isinstance(pgvector_bytes, (bytes, memoryview)):
            import struct
            dim = len(pgvector_bytes) // 4
            return list(struct.unpack(f'{dim}f', pgvector_bytes))
        if isinstance(pgvector_bytes, str):
            cleaned = pgvector_bytes.strip('[]')
            return [float(x) for x in cleaned.split(',') if x.strip()]
        return list(pgvector_bytes)
