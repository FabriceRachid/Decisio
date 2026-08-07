"""
LLM service for structural reconstruction of messy files.
Uses Groq (Llama 3.3 70B) to propose reconstruction plans.
Never sends raw data — only structural fingerprints + correction examples.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

RECONSTRUCTION_SYSTEM_PROMPT = """Tu es un moteur de reconstruction de donnees tabulaires desordonnees pour une plateforme de Business Intelligence destinee aux PME.

CONTEXTE
On te fournit la STRUCTURE d'un fichier Excel/CSV desordonne (pas toutes les valeurs — un echantillon des premieres et dernieres lignes, la liste des cellules fusionnees, et les zones vides detectees). Ton role est de proposer un schema de reconstruction, pas de traiter chaque ligne une par une.

DONNEES FOURNIES
- Echantillon structurel : {structural_sample}
- Cellules fusionnees detectees : {merged_cells}
- Lignes/colonnes vides (separateurs potentiels) : {blank_zones}
- Exemples de corrections similaires validees precedemment par un humain : {correction_examples}
- Schema pivot epars detecte (si present) : {sparse_pivot}

TACHE
1. Identifie s'il y a un ou plusieurs sous-tableaux distincts dans la feuille.
2. Pour chaque sous-tableau, identifie la ligne d'en-tete reelle.
3. Propose un nom de colonne clair et normalise pour chaque colonne detectee.
4. Detecte si les donnees presentent un format PIVOT/CROSSTAB a transformer en format LONG (unpivot/melt).
5. Si pivot detecte, identifie les colonnes identifiantes (dimensions) et les colonnes valeurs.
6. Examine le CONTENU de chaque colonne et detecte les transformations au niveau cellule (voir section ci-dessous).
7. Signale les cellules ou zones que tu ne peux pas interpreter avec confiance.
8. Indique un score de confiance global (0 a 1) pour ta proposition.

DETECTION PIVOT
Un schema pivot (ou crosstab) est present quand :
- Les colonnes contiennent des titres de categories (ex: "Janvier", "Fevrier", "Mars" ou "Nord", "Sud", "Est", "Ouest")
- Les valeurs dans ces colonnes sont numeriques (des mesures/quantites)
- Chaque ligne a generalement UNE SEULE valeur non-nulle parmi les colonnes du groupe pivot
- La structure est "eparse" : beaucoup de cellules vides dans les colonnes valeurs

Si tu detectes un pivot, tu dois specifier :
- type_transformation : "unpivot" (format long)
- colonnes_identifiantes : les colonnes qui identifient chaque ligne (dimensions fixes)
- colonnes_valeurs : les colonnes a " fondre " en une seule colonne de valeurs
- nom_nouvelle_colonne_dimension : nom de la colonne qui contiendra les noms d'anciennes colonnes
- nom_nouvelle_colonne_valeur : nom de la colonne qui contiendra les valeurs

DETECTION DE TRANSFORMATIONS AU NIVEAU CELLULE
En plus de l'analyse structurelle globale, examine le CONTENU de chaque colonne sur l'echantillon fourni et detecte les motifs suivants :

- Une colonne contient des phrases en langage libre avec des labels reconnaissables integres (ex. "Name X Address Y Age Z") -> propose une extraction_champs_texte_libre.
- Une colonne censee etre numerique (d'apres son nom ou la majorite de ses valeurs) contient des caracteres qui ressemblent visuellement a des chiffres (i, I, o, O, s, l) -> propose une correction_caracteres_ambigus. Ne corrige QUE les cas ou le contexte (le reste de la valeur, la colonne, les valeurs voisines dans la meme ligne/colonne) rend la correction evidente. Dans le doute, signale sans corriger.
- Une colonne contient un nombre directement suivi de texte sans separateur, de facon repetee sur plusieurs lignes -> propose une scission_valeur_unite.
- Une ou plusieurs colonnes contiennent des valeurs separees par un delimiteur repete (|, ;, virgule) et une autre colonne de la meme ligne contient le meme nombre d'elements separes par le meme delimiteur -> propose une explosion_liste_delimitee, en verifiant la correspondance de position entre les colonnes concernees.
- Si un tableau croise contient des colonnes de sous-total ou de total intermediaire (ex. une colonne "X Total" a cote d'un groupe de colonnes de detail), identifie-les et exclues-les explicitement du mapping_pivot — elles ne doivent jamais etre traitees comme une dimension ni comme une donnee a depivoter.

Ces transformations peuvent se combiner avec une transformation de type "unpivot" sur la meme feuille (utilise alors type_transformation="mixed" et remplis les deux champs mapping_pivot et transformations_cellule).

Pour chaque transformation cellule detectee, specifie :
- colonne_source : nom de la colonne d'origine
- sous_type : le type de transformation parmi les 4 valeurs ci-dessus
- colonnes_resultantes : liste des noms de colonnes resultant de la transformation
- details : structure specifique selon le sous_type (voir schema ci-dessous)
- niveau_confiance : score 0-1 pour cette transformation specifique
- echantillon_ambigu : valeurs sources incertaines necessitant revision humaine

DETAILS PAR SOUS_TYPE :
a) extraction_champs_texte_libre :
   { "labels_detectes": ["Name", "Address", "Age", "Gender"],
     "logique_decoupage": "chaque label marque le debut d'un nouveau champ" }
b) correction_caracteres_ambigus :
   { "substitutions_types": {"i": "1", "o": "0", "O": "0", "s": "5"},
     "cas_incertains": ["valeur1", "valeur2"] }
c) scission_valeur_unite :
   { "motif_detecte": "nombre suivi directement de texte sans separateur",
     "colonne_nombre": "Quantity", "colonne_texte": "Measure" }
d) explosion_liste_delimitee :
   { "delimiteur_detecte": "|",
     "colonnes_liees": ["Category", "Amount"],
     "colonnes_a_repeter": ["Order ID"],
     "verification": "nombre d'elements identique dans toutes les colonnes liees" }

CONTRAINTES IMPORTANTES
- Ne modifie jamais les valeurs elles-memes, uniquement la structure.
- Si deux interpretations sont egalement plausibles, signale l'ambiguite plutot que de trancher silencieusement.
- N'invente aucune donnee manquante.
- Si type_transformation est "unpivot", ne fournis PAS de renamed_columns pour les colonnes identifiantes.
- Pour les corrections de caracteres ambigus, ne marque en cas_incertains QUE les valeurs ou la correction n'est pas evidente.
- Pour les explosions de listes, NE PAS deviner un alignement si les longueurs diffrent — marque pour revision humaine.

FORMAT DE SORTIE : JSON uniquement selon le schema defini."""


class LLMReconstructionService:
    """
    Calls Groq (Llama 3.3 70B) to propose structural reconstruction plans.
    Only receives structural fingerprints, never raw data values.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            api_key = getattr(settings, 'GROQ_API_KEY', '')
            if not api_key:
                raise ValueError("GROQ_API_KEY non configuree dans les variables d'environnement")
            import groq
            self._client = groq.Groq(api_key=api_key)
        return self._client

    def propose_reconstruction(
        self,
        structural_fingerprint: dict[str, Any],
        correction_examples: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send structural fingerprint to LLM and get reconstruction plan.
        Never sends raw data values — only structural metadata.
        """
        structural_sample = self._build_structural_sample(structural_fingerprint)
        merged_cells = json.dumps(structural_fingerprint.get('merged_cells', []), ensure_ascii=False)
        blank_zones = json.dumps({
            'blank_rows': structural_fingerprint.get('blank_rows', []),
            'blank_cols': structural_fingerprint.get('blank_cols', []),
        }, ensure_ascii=False)
        examples_text = self._format_correction_examples(correction_examples or [])
        sparse_pivot_text = json.dumps(
            structural_fingerprint.get('sparse_pivot_candidates', []), ensure_ascii=False
        )

        user_message = (
            f"Voici la structure du fichier a analyser :\n\n"
            f"**Echantillon structurel :**\n{structural_sample}\n\n"
            f"**Cellules fusionnees :** {merged_cells}\n\n"
            f"**Zones vides :** {blank_zones}\n\n"
            f"**Exemples de corrections similaires :**\n{examples_text}\n\n"
            f"**Pivot epars detecte (heuristique) :** {sparse_pivot_text}\n\n"
            f"Propose le schema de reconstruction en JSON."
        )

        model = getattr(settings, 'STRUCTURE_DETECTION_LLM_MODEL', 'llama-3.3-70b-versatile')

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=4096,
                temperature=0.1,
                messages=[
                    {'role': 'system', 'content': RECONSTRUCTION_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_message},
                ],
            )
            duration_ms = int((time.time() - start_time) * 1000)

            content = response.choices[0].message.content
            result = self._parse_llm_response(content)
            result['llm_model'] = model
            result['llm_tokens_used'] = (response.usage.prompt_tokens + response.usage.completion_tokens) if response.usage else 0
            result['llm_duration_ms'] = duration_ms

            return result

        except Exception as e:
            logger.exception("LLM reconstruction call failed")
            return {
                'success': False,
                'error': str(e),
                'reconstruction_plan': None,
                'confidence': 0,
            }

    def _build_structural_sample(self, fp: dict[str, Any]) -> str:
        lines = []
        lines.append(f"Dimensions : {fp.get('total_rows', 0)} lignes x {fp.get('total_cols', 0)} colonnes")

        sample = fp.get('_sample_data')
        if sample:
            header = sample.get('header_row', [])
            if header:
                clean = [str(c) if c is not None else '(vide)' for c in header]
                lines.append(f"En-tetes reelles : {clean}")
            first = sample.get('first_rows', [])
            if first:
                lines.append("Premieres lignes :")
                for i, row in enumerate(first[:3]):
                    clean = [str(c) if c is not None else '(vide)' for c in row[:10]]
                    lines.append(f"  Ligne {i+1}: {clean}")
            last = sample.get('last_rows', [])
            if last:
                lines.append("Dernieres lignes :")
                for i, row in enumerate(last[-2:]):
                    clean = [str(c) if c is not None else '(vide)' for c in row[:10]]
                    lines.append(f"  Ligne {len(first)+i+1}: {clean}")

        subtables = fp.get('subtables', [])
        if subtables:
            lines.append(f"Sous-tableaux detectes : {len(subtables)}")
            for i, st in enumerate(subtables):
                lines.append(
                    f"  Sous-tableau {i+1}: lignes {st.get('start_row', '?')}-{st.get('end_row', '?')}, "
                    f"colonnes {st.get('start_col', '?')}-{st.get('end_col', '?')}"
                )

        headers = fp.get('header_candidates', [])
        if headers:
            lines.append("Candidates en-tete :")
            for h in headers[:3]:
                lines.append(
                    f"  Ligne {h.get('row_index', '?')} (score={h.get('score', '?')}, "
                    f"remplissage={h.get('fill_ratio', '?')})"
                )

        col_types = fp.get('column_types', {})
        if col_types:
            lines.append("Types de colonnes detectes :")
            for col, typ in list(col_types.items())[:10]:
                lines.append(f"  {col}: {typ}")

        issues = fp.get('issues', [])
        if issues:
            lines.append("Problemes detectes :")
            for issue in issues:
                lines.append(f"  - {issue}")

        sparse_pivots = fp.get('sparse_pivot_candidates', [])
        if sparse_pivots:
            lines.append(f"Pivot epars detecte : {len(sparse_pivots)} candidat(s)")
            for i, sp in enumerate(sparse_pivots[:2]):
                lines.append(
                    f"  Groupe {i+1}: colonnes {sp.get('group_headers', [])} "
                    f"(sparsite={sp.get('sparsity_score', '?')})"
                )

        hier_headers = fp.get('hierarchical_headers', [])
        if hier_headers:
            lines.append(f"En-tetes hierarchiques : {len(hier_headers)} ligne(s)")
            for hh in hier_headers[:3]:
                lines.append(f"  Ligne {hh.get('row_index', '?')}: {hh.get('values', [])[:8]}")

        return '\n'.join(lines)

    def _format_correction_examples(self, examples: list[dict]) -> str:
        if not examples:
            return "Aucun exemple disponible."

        lines = []
        for i, ex in enumerate(examples[:5]):
            lines.append(f"Exemple {i+1} (type: {ex.get('correction_type', 'unknown')}) :")
            desc = ex.get('description', 'Pas de description')
            lines.append(f"  Description: {desc}")
            before = ex.get('structural_before', {})
            after = ex.get('structural_after', {})
            lines.append(f"  Avant: {json.dumps(before, ensure_ascii=False)[:200]}")
            lines.append(f"  Apres: {json.dumps(after, ensure_ascii=False)[:200]}")
            lines.append("")

        return '\n'.join(lines)

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        try:
            json_str = None

            in_code_block = False
            json_lines = []
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('```json'):
                    in_code_block = True
                    continue
                elif stripped.startswith('```') and in_code_block:
                    in_code_block = False
                    if json_lines:
                        json_str = '\n'.join(json_lines)
                    continue
                elif in_code_block:
                    json_lines.append(line)

            if json_str is None and json_lines:
                json_str = '\n'.join(json_lines)

            if json_str is None:
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1 and end > start:
                    json_str = content[start:end + 1]

            if json_str is None:
                json_str = content.strip()

            result = json.loads(json_str)

            required_fields = ['subtables', 'confidence']
            for field_name in required_fields:
                if field_name not in result:
                    result[field_name] = [] if field_name == 'subtables' else 0.5

            type_transform = result.get('type_transformation', None)
            mapping_pivot = result.get('mapping_pivot', None)
            cell_transforms = result.get('transformations_cellule', None)

            return {
                'success': True,
                'reconstruction_plan': result,
                'confidence': float(result.get('confidence', 0.5)),
                'subtables': result.get('subtables', []),
                'ambiguities': result.get('ambiguities', []),
                'warnings': result.get('warnings', []),
                'type_transformation': type_transform,
                'mapping_pivot': mapping_pivot,
                'transformations_cellule': cell_transforms,
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return {
                'success': False,
                'error': f'JSON parse error: {e}',
                'reconstruction_plan': None,
                'confidence': 0,
                'raw_response': content[:1000],
            }
