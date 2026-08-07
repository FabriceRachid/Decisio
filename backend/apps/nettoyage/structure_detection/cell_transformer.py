"""
Cell-level transformers for messy data values.
Each sub-type has a dedicated function rather than a generic engine.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

AMBIGUOUS_CHARS = {
    'i': '1', 'I': '1',
    'o': '0', 'O': '0',
    'l': '1', 's': '5', 'S': '5',
    'B': '8', 'G': '6', 'Z': '2',
}


def extract_labeled_fields(
    texte: str,
    labels_detectes: list[str],
) -> dict[str, str]:
    """
    Extract labeled fields from free-form text.

    Args:
        texte: Raw text containing embedded labels (e.g. "Name John Address Paris Age 25")
        labels_detectes: Ordered list of labels found in the text

    Returns:
        Dict mapping each label to its extracted value.
        Labels not found in the text are mapped to empty string.
    """
    if not texte or not labels_detectes:
        if labels_detectes:
            return {label: '' for label in labels_detectes}
        return {}

    result = {}
    lower_text = texte.lower()
    label_positions = []

    for label in labels_detectes:
        pos = lower_text.find(label.lower())
        if pos != -1:
            label_positions.append((pos, label))

    label_positions.sort(key=lambda x: x[0])

    for i, (pos, label) in enumerate(label_positions):
        label_end = pos + len(label)
        if i + 1 < len(label_positions):
            next_pos = label_positions[i + 1][0]
            value = texte[label_end:next_pos].strip()
        else:
            value = texte[label_end:].strip()
        result[label] = value

    for label in labels_detectes:
        if label not in result:
            result[label] = ''

    return result


def fix_ambiguous_numeric_chars(
    valeur: str,
    substitutions_types: dict[str, str] | None = None,
    cas_incertains: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fix visually ambiguous characters in numeric values.

    Args:
        valeur: Raw value string
        substitutions_types: Mapping of ambiguous chars to correct digits
        cas_incertains: Values deemed too ambiguous to auto-correct

    Returns:
        Dict with 'corrected' (str), 'was_corrected' (bool), 'needs_review' (bool)
    """
    if substitutions_types is None:
        substitutions_types = AMBIGUOUS_CHARS
    if cas_incertains is None:
        cas_incertains = []

    if valeur in cas_incertains:
        return {
            'corrected': valeur,
            'was_corrected': False,
            'needs_review': True,
            'reason': f'Valeur dans cas incertains: {valeur}',
        }

    corrected = valeur
    was_corrected = False

    for ambiguous, correct in substitutions_types.items():
        if ambiguous in corrected:
            corrected = corrected.replace(ambiguous, correct)
            was_corrected = True

    return {
        'corrected': corrected,
        'was_corrected': was_corrected,
        'needs_review': False,
    }


def split_value_unit(valeur: str) -> dict[str, str] | None:
    """
    Split a value that contains a number directly followed by text without separator.

    Args:
        valeur: Raw value (e.g. "0Bottle", "5kg", "12items")

    Returns:
        Dict with 'nombre' (str) and 'texte' (str), or None if no pattern matches.
    """
    if not valeur or not isinstance(valeur, str):
        return None

    match = re.match(r'^([+-]?\d+(?:[.,]\d+)?)\s*([a-zA-Z].*)$', valeur.strip())
    if match:
        return {
            'nombre': match.group(1).replace(',', '.'),
            'texte': match.group(2).strip(),
        }

    return None


def explode_delimited_lists(
    ligne: dict[str, Any],
    colonnes_liees: list[str],
    delimiteur: str,
    colonnes_a_repeter: list[str],
) -> list[dict[str, Any]]:
    """
    Explode delimited lists in linked columns into separate rows.

    Args:
        ligne: Dict representing one source row
        colonnes_liees: Columns containing delimited lists that must have matching lengths
        delimiteur: The delimiter character
        colonnes_a_repeter: Columns to duplicate as-is for each exploded element

    Returns:
        List of dicts, one per exploded element.
        Raises ValueError if list lengths mismatch across linked columns.
    """
    listes = {}
    for col in colonnes_liees:
        val = ligne.get(col, '')
        if pd.isna(val):
            val = ''
        parts = [p.strip() for p in str(val).split(delimiteur)]
        listes[col] = parts

    lengths = {col: len(parts) for col, parts in listes.items()}
    unique_lengths = set(lengths.values())

    if len(unique_lengths) > 1:
        raise ValueError(
            f"Longueurs de listes incoherentes: {lengths}. "
            f"Toutes les colonnes liees doivent avoir le meme nombre d'elements."
        )

    nb_elements = list(unique_lengths)[0]
    if nb_elements == 0:
        return []

    result = []
    for i in range(nb_elements):
        new_row = {}
        for col_a_repeter in colonnes_a_repeter:
            new_row[col_a_repeter] = ligne.get(col_a_repeter, '')
        for col in colonnes_liees:
            new_row[col] = listes[col][i]
        result.append(new_row)

    return result


class CellTransformerEngine:
    """
    Applies cell-level transformations to a DataFrame based on LLM-proposed plans.
    """

    def apply_text_field_extraction(
        self,
        df: pd.DataFrame,
        transformation: dict[str, Any],
    ) -> pd.DataFrame:
        """Apply extraction_champs_texte_libre transformation."""
        col_source = transformation['colonne_source']
        labels = transformation['details']['labels_detectes']
        colonnes_result = transformation['colonnes_resultantes']

        if col_source not in df.columns:
            logger.warning(f"Column '{col_source}' not found in DataFrame")
            return df

        for label in colonnes_result:
            df[label] = ''

        for idx, row in df.iterrows():
            texte = str(row[col_source]) if pd.notna(row[col_source]) else ''
            extracted = extract_labeled_fields(texte, labels)
            for col in colonnes_result:
                df.at[idx, col] = extracted.get(col, '')

        df = df.drop(columns=[col_source])
        return df

    def apply_char_correction(
        self,
        df: pd.DataFrame,
        transformation: dict[str, Any],
    ) -> tuple[pd.DataFrame, list[str]]:
        """
        Apply correction_caracteres_ambigus transformation.
        Returns (updated_df, list_of_values_needing_review).
        """
        col_source = transformation['colonne_source']
        substitutions = transformation['details'].get('substitutions_types', {})
        cas_incertains = transformation['details'].get('cas_incertains', [])

        if col_source not in df.columns:
            logger.warning(f"Column '{col_source}' not found in DataFrame")
            return df, []

        review_needed = []

        for idx, row in df.iterrows():
            val = str(row[col_source]) if pd.notna(row[col_source]) else ''
            result = fix_ambiguous_numeric_chars(val, substitutions, cas_incertains)
            if result['needs_review']:
                review_needed.append(val)
            else:
                df.at[idx, col_source] = result['corrected']

        return df, review_needed

    def apply_value_unit_split(
        self,
        df: pd.DataFrame,
        transformation: dict[str, Any],
    ) -> pd.DataFrame:
        """Apply scission_valeur_unite transformation."""
        col_source = transformation['colonne_source']
        col_nombre = transformation['details']['colonne_nombre']
        col_texte = transformation['details']['colonne_texte']

        if col_source not in df.columns:
            logger.warning(f"Column '{col_source}' not found in DataFrame")
            return df

        df[col_nombre] = ''
        df[col_texte] = ''

        for idx, row in df.iterrows():
            val = str(row[col_source]) if pd.notna(row[col_source]) else ''
            split = split_value_unit(val)
            if split:
                df.at[idx, col_nombre] = split['nombre']
                df.at[idx, col_texte] = split['texte']
            else:
                df.at[idx, col_nombre] = val
                df.at[idx, col_texte] = ''

        df = df.drop(columns=[col_source])
        return df

    def apply_delimited_list_explode(
        self,
        df: pd.DataFrame,
        transformation: dict[str, Any],
    ) -> tuple[pd.DataFrame, list[int]]:
        """
        Apply explosion_liste_delimitee transformation.
        Returns (exploded_df, list_of_source_row_indices_with_mismatch).
        """
        colonnes_liees = transformation['details']['colonnes_liees']
        delimiteur = transformation['details']['delimiteur_detecte']
        colonnes_a_repeter = transformation['details'].get('colonnes_a_repeter', [])

        mismatch_rows = []
        result_rows = []

        for idx, row in df.iterrows():
            ligne = row.to_dict()
            try:
                exploded = explode_delimited_lists(
                    ligne, colonnes_liees, delimiteur, colonnes_a_repeter
                )
                result_rows.extend(exploded)
            except ValueError:
                mismatch_rows.append(idx)
                result_rows.append(ligne)

        return pd.DataFrame(result_rows), mismatch_rows
