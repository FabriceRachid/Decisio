"""
Pivot/Crosstab transformer.
Converts wide-format (pivot/crosstab) data to long format (unpivot/melt).
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class PivotTransformer:
    """
    Transforms pivot/crosstab data to long format using pd.melt.
    """

    def unpivot(
        self,
        df: pd.DataFrame,
        id_vars: list[str] | None = None,
        value_vars: list[str] | None = None,
        var_name: str = 'Dimension',
        value_name: str = 'Valeur',
    ) -> pd.DataFrame | None:
        """
        Unpivot a DataFrame from wide to long format.

        Args:
            df: Input DataFrame
            id_vars: Columns to keep as identifiers (dimensions)
            value_vars: Columns to unpivot (values to melt)
            var_name: Name for the new dimension column
            value_name: Name for the new value column

        Returns:
            Unpivoted DataFrame or None if transformation fails
        """
        if df.empty:
            logger.warning("Empty DataFrame, cannot unpivot")
            return None

        if id_vars is None or value_vars is None:
            logger.warning("id_vars and value_vars are required")
            return None

        missing_id = [c for c in id_vars if c not in df.columns]
        missing_val = [c for c in value_vars if c not in df.columns]
        if missing_id:
            logger.warning(f"Missing id_vars columns: {missing_id}")
            return None
        if missing_val:
            logger.warning(f"Missing value_vars columns: {missing_val}")
            return None

        try:
            result = pd.melt(
                df,
                id_vars=id_vars,
                value_vars=value_vars,
                var_name=var_name,
                value_name=value_name,
            )
            result = result.dropna(subset=[value_name])
            result = result.reset_index(drop=True)
            logger.info(
                f"Unpivot complete: {len(df)} rows -> {len(result)} rows "
                f"(id_vars={id_vars}, value_vars={value_vars})"
            )
            return result
        except Exception as e:
            logger.exception(f"Unpivot failed: {e}")
            return None

    def unpivot_from_mapping(
        self,
        df: pd.DataFrame,
        mapping: dict[str, Any],
    ) -> pd.DataFrame | None:
        """
        Unpivot using a mapping_pivot dict from LLM or heuristic.

        mapping format:
        {
            "colonnes_identifiantes": ["Product", "Region"],
            "colonnes_valeurs": ["Janvier", "Fevrier", "Mars"],
            "nom_nouvelle_colonne_dimension": "Mois",
            "nom_nouvelle_colonne_valeur": "Ventes"
        }
        """
        if not mapping:
            logger.warning("Empty mapping, cannot unpivot")
            return None

        id_vars = mapping.get('colonnes_identifiantes', [])
        value_vars = mapping.get('colonnes_valeurs', [])
        var_name = mapping.get('nom_nouvelle_colonne_dimension', 'Dimension')
        value_name = mapping.get('nom_nouvelle_colonne_valeur', 'Valeur')

        if not id_vars or not value_vars:
            logger.warning("Mapping must specify colonnes_identifiantes and colonnes_valeurs")
            return None

        return self.unpivot(df, id_vars, value_vars, var_name, value_name)

    def validate_unpivot_result(
        self,
        original_df: pd.DataFrame,
        unpivoted_df: pd.DataFrame,
        mapping: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate the unpivot result:
        - Row count matches non-empty cell count
        - No missing dimension values
        - Value column has expected type
        """
        value_vars = mapping.get('colonnes_valeurs', [])
        id_vars = mapping.get('colonnes_identifiantes', [])
        var_name = mapping.get('nom_nouvelle_colonne_dimension', 'Dimension')
        value_name = mapping.get('nom_nouvelle_colonne_valeur', 'Valeur')

        expected_rows = 0
        for _, row in original_df.iterrows():
            for col in value_vars:
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    expected_rows += 1

        actual_rows = len(unpivoted_df)
        row_count_ok = actual_rows == expected_rows

        missing_dims = []
        for dim_col in id_vars:
            if dim_col in unpivoted_df.columns:
                null_count = unpivoted_df[dim_col].isna().sum()
                if null_count > 0:
                    missing_dims.append((dim_col, int(null_count)))

        value_type = 'unknown'
        if value_name in unpivoted_df.columns:
            if pd.api.types.is_numeric_dtype(unpivoted_df[value_name]):
                value_type = 'numeric'
            elif pd.api.types.is_datetime64_any_dtype(unpivoted_df[value_name]):
                value_type = 'date'
            else:
                value_type = 'text'

        return {
            'valid': row_count_ok and not missing_dims,
            'expected_rows': expected_rows,
            'actual_rows': actual_rows,
            'row_count_ok': row_count_ok,
            'missing_dimensions': missing_dims,
            'value_type': value_type,
        }
