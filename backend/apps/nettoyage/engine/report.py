from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from datetime import datetime, timezone


@dataclass
class CleaningReport:
    fichier_id: str
    nom_fichier: str
    lignes_initiales: int
    colonnes_initiales: int
    statut: str = 'SUCCES'
    lignes_finales: int = 0
    colonnes_finales: int = 0
    score_qualite: float = 0.0
    duree_traitement_ms: int = 0
    mapping: dict[str, list[Any]] = field(
        default_factory=lambda: {
            'colonnes_mappees': [],
            'colonnes_non_mappees': [],
        }
    )
    corrections: list[dict[str, Any]] = field(default_factory=list)
    alertes: list[dict[str, Any]] = field(default_factory=list)
    score_detail: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    _start: float = field(default_factory=perf_counter, repr=False)

    def add_mapping(
        self,
        *,
        original: str,
        standard: str,
        score: int,
        confirmed: bool,
        methode: str = 'fuzzy_matching',
    ) -> None:
        self.mapping['colonnes_mappees'].append(
            {
                'original': original,
                'standard': standard,
                'score': score,
                'methode': methode,
                'statut': 'confirme' if confirmed else 'suggestion',
            }
        )

    def add_unmapped(self, column: str) -> None:
        if column not in self.mapping['colonnes_non_mappees']:
            self.mapping['colonnes_non_mappees'].append(column)

    def add_correction(self, *, regle: str, description: str, nombre: int, exemples: list[dict[str, Any]] | None = None) -> None:
        if nombre <= 0:
            return
        self.corrections.append(
            {
                'regle': regle,
                'description': description,
                'nombre': nombre,
                'exemples': exemples or [],
            }
        )

    def add_alert(self, *, regle: str, severite: str, message: str, lignes: list[int] | None = None) -> None:
        self.alertes.append(
            {
                'regle': regle,
                'severite': severite,
                'message': message,
                'lignes': lignes or [],
            }
        )

    def finalize(self, *, lignes_finales: int, colonnes_finales: int, score_qualite: float, score_detail: dict[str, float], statut: str = 'SUCCES') -> None:
        self.lignes_finales = lignes_finales
        self.colonnes_finales = colonnes_finales
        self.score_qualite = round(float(score_qualite), 2)
        self.score_detail = {key: round(float(value), 2) for key, value in score_detail.items()}
        self.statut = statut
        self.duree_traitement_ms = int((perf_counter() - self._start) * 1000)
        self.metadata.setdefault('resume_executif', self._build_executive_summary())
        self.metadata.setdefault(
            'traceabilite',
            {
                'corrections_total': len(self.corrections),
                'alertes_total': len(self.alertes),
                'colonnes_mappees': len(self.mapping['colonnes_mappees']),
                'colonnes_non_mappees': len(self.mapping['colonnes_non_mappees']),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        couche_1_ml = self.metadata.get('couche_1_ml', {})
        mapping_result = self.metadata.get('mapping_resultat', {})
        score_par_colonne = self.metadata.get('score_par_colonne', {})
        colonnes_problematiques = self.metadata.get('colonnes_problematiques', [])
        rollback = self.metadata.get('reversibilite', {})
        actions_requises = self.metadata.get('actions_requises', [])
        score_interpretation, score_color = self._score_interpretation(self.score_qualite)
        return {
            'fichier_id': self.fichier_id,
            'nom_fichier': self.nom_fichier,
            'lignes_initiales': self.lignes_initiales,
            'lignes_finales': self.lignes_finales,
            'colonnes_initiales': self.colonnes_initiales,
            'colonnes_finales': self.colonnes_finales,
            'score_qualite': self.score_qualite,
            'statut': self.statut,
            'duree_traitement_ms': self.duree_traitement_ms,
            'mapping': self.mapping,
            'corrections': self.corrections,
            'alertes': self.alertes,
            'score_detail': self.score_detail,
            'metadata': self.metadata,
            'meta': {
                'fichier_id': self.fichier_id,
                'nom_fichier': self.nom_fichier,
                'hash_md5': self.metadata.get('hash_md5'),
                'lignes_initiales': self.lignes_initiales,
                'lignes_finales': self.lignes_finales,
                'colonnes_initiales': self.colonnes_initiales,
                'colonnes_finales': self.colonnes_finales,
                'duree_traitement_ms': self.duree_traitement_ms,
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'user_id': self.metadata.get('user_id'),
            },
            'score': {
                'global': self.score_qualite,
                'interpretation': score_interpretation,
                'couleur': score_color,
                'detail': self.score_detail,
                'scores_par_colonne': score_par_colonne,
                'colonnes_problematiques': colonnes_problematiques,
            },
            'mapping_detail': {
                'colonnes_mappees': self.mapping['colonnes_mappees'],
                'colonnes_non_mappees': self.mapping['colonnes_non_mappees'],
                'colonnes_extra': mapping_result.get('colonnes_extra', []),
                'colonnes_a_revoir': mapping_result.get('colonnes_a_revoir', []),
            },
            'couche_1_ml': couche_1_ml,
            'rollback': {
                'disponible': bool(rollback.get('rollback_disponible', False)),
                'donnees_brutes_id': rollback.get('source_id'),
                **rollback,
            },
            'actions_requises': actions_requises,
        }

    def _build_executive_summary(self) -> dict[str, Any]:
        sorted_alerts = sorted(
            self.alertes,
            key=lambda item: {'CRITIQUE': 0, 'MOYEN': 1, 'INFO': 2}.get(item.get('severite'), 3),
        )
        return {
            'statut': self.statut,
            'score_qualite': self.score_qualite,
            'problemes_principaux': sorted_alerts[:3],
            'corrections_principales': self.corrections[:3],
            'impact_lignes': {
                'initiales': self.lignes_initiales,
                'finales': self.lignes_finales,
                'ecart': self.lignes_initiales - self.lignes_finales,
            },
        }

    def _score_interpretation(self, score: float) -> tuple[str, str]:
        if score >= 95:
            return 'Excellent', 'vert'
        if score >= 85:
            return 'Bon', 'bleu'
        if score >= 70:
            return 'Acceptable', 'orange'
        return 'Insuffisant', 'rouge'
