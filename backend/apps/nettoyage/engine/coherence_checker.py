from __future__ import annotations

import pandas as pd

from .report import CleaningReport


class CoherenceChecker:
    def check(self, dataframe: pd.DataFrame, report: CleaningReport, mapped_fields: dict[str, dict]) -> pd.DataFrame:
        reverse_mapping = {meta['standard']: column for column, meta in mapped_fields.items()}

        if {'montant_total', 'quantite', 'prix_unitaire'}.issubset(reverse_mapping):
            amount_col = reverse_mapping['montant_total']
            qty_col = reverse_mapping['quantite']
            unit_col = reverse_mapping['prix_unitaire']
            amount = pd.to_numeric(dataframe[amount_col], errors='coerce')
            qty = pd.to_numeric(dataframe[qty_col], errors='coerce')
            unit = pd.to_numeric(dataframe[unit_col], errors='coerce')
            expected = qty * unit
            denominator = expected.where(expected != 0)
            ratio = ((amount - expected).abs() / denominator).where(denominator.notna(), 0)
            medium_invalid = dataframe.loc[(ratio > 0.01).fillna(False), '_row_number'].astype(int).tolist()
            critical_invalid = dataframe.loc[(ratio > 0.10).fillna(False), '_row_number'].astype(int).tolist()
            if medium_invalid:
                report.add_alert(
                    regle='R18',
                    severite='MOYEN',
                    message='Écarts détectés entre montant total et quantité × prix unitaire.',
                    lignes=medium_invalid[:10],
                )
            if critical_invalid:
                report.add_alert(
                    regle='R18',
                    severite='CRITIQUE',
                    message='Des écarts critiques ont été détectés entre montant total et quantité × prix unitaire.',
                    lignes=critical_invalid[:10],
                )

            zero_qty_rows = dataframe.loc[((qty == 0) & (amount > 0)).fillna(False), '_row_number'].astype(int).tolist()
            if zero_qty_rows:
                report.add_alert(
                    regle='R21',
                    severite='CRITIQUE',
                    message='Des lignes ont une quantité nulle avec un montant positif.',
                    lignes=zero_qty_rows[:10],
                )
            zero_amount_rows = dataframe.loc[((qty > 0) & (amount == 0)).fillna(False), '_row_number'].astype(int).tolist()
            if zero_amount_rows:
                report.add_alert(
                    regle='R21',
                    severite='CRITIQUE',
                    message='Des lignes ont une quantité positive avec un montant nul.',
                    lignes=zero_amount_rows[:10],
                )
            negative_qty_rows = dataframe.loc[(qty < 0).fillna(False), '_row_number'].astype(int).tolist()
            if negative_qty_rows:
                report.add_alert(
                    regle='R21',
                    severite='CRITIQUE',
                    message='Des quantités négatives ont été détectées.',
                    lignes=negative_qty_rows[:10],
                )

        if {'date_commande', 'date_livraison'}.issubset(reverse_mapping):
            order_col = reverse_mapping['date_commande']
            delivery_col = reverse_mapping['date_livraison']
            order_dates = pd.to_datetime(dataframe[order_col], errors='coerce')
            delivery_dates = pd.to_datetime(dataframe[delivery_col], errors='coerce')
            invalid = dataframe.loc[(delivery_dates < order_dates).fillna(False), '_row_number'].astype(int).tolist()
            if invalid:
                report.add_alert(
                    regle='R19',
                    severite='MOYEN',
                    message='Dates de livraison antérieures aux dates de commande détectées.',
                    lignes=invalid[:10],
                )
        if {'date_commande', 'date_livraison', 'date_paiement'}.issubset(reverse_mapping):
            order_dates = pd.to_datetime(dataframe[reverse_mapping['date_commande']], errors='coerce')
            delivery_dates = pd.to_datetime(dataframe[reverse_mapping['date_livraison']], errors='coerce')
            payment_dates = pd.to_datetime(dataframe[reverse_mapping['date_paiement']], errors='coerce')
            invalid = dataframe.loc[((payment_dates < delivery_dates) | (payment_dates < order_dates)).fillna(False), '_row_number'].astype(int).tolist()
            if invalid:
                report.add_alert(
                    regle='R19',
                    severite='MOYEN',
                    message='Des séquences temporelles incohérentes ont été détectées entre commande, livraison et paiement.',
                    lignes=invalid[:10],
                )

        if {'stock_initial', 'stock_final'}.issubset(reverse_mapping):
            initial_col = reverse_mapping['stock_initial']
            final_col = reverse_mapping['stock_final']
            initial_stock = pd.to_numeric(dataframe[initial_col], errors='coerce')
            final_stock = pd.to_numeric(dataframe[final_col], errors='coerce')
            negative_stock_rows = dataframe.loc[(final_stock < 0).fillna(False), '_row_number'].astype(int).tolist()
            if negative_stock_rows:
                report.add_alert(
                    regle='R20',
                    severite='CRITIQUE',
                    message='Des stocks finaux négatifs ont été détectés.',
                    lignes=negative_stock_rows[:10],
                )
            doubled_rows = dataframe.loc[(final_stock > (initial_stock * 2)).fillna(False), '_row_number'].astype(int).tolist()
            if doubled_rows:
                report.add_alert(
                    regle='R20',
                    severite='MOYEN',
                    message='Des variations de stock très élevées ont été détectées.',
                    lignes=doubled_rows[:10],
                )
            quantity_field = reverse_mapping.get('quantite')
            if quantity_field:
                quantity = pd.to_numeric(dataframe[quantity_field], errors='coerce')
                inconsistent_rows = dataframe.loc[((initial_stock - quantity - final_stock).abs() > 1).fillna(False), '_row_number'].astype(int).tolist()
                if inconsistent_rows:
                    report.add_alert(
                        regle='R20',
                        severite='MOYEN',
                        message='Des incohérences ont été détectées entre stock initial, quantité et stock final.',
                        lignes=inconsistent_rows[:10],
                    )

        if {'remise', 'prix_unitaire'}.issubset(reverse_mapping):
            discount = pd.to_numeric(dataframe[reverse_mapping['remise']], errors='coerce')
            unit_price = pd.to_numeric(dataframe[reverse_mapping['prix_unitaire']], errors='coerce')
            excessive_discount_rows = dataframe.loc[(discount > unit_price).fillna(False), '_row_number'].astype(int).tolist()
            if excessive_discount_rows:
                report.add_alert(
                    regle='R21',
                    severite='MOYEN',
                    message='Des remises supérieures au prix unitaire ont été détectées.',
                    lignes=excessive_discount_rows[:10],
                )
            negative_discount_rows = dataframe.loc[(discount < 0).fillna(False), '_row_number'].astype(int).tolist()
            if negative_discount_rows:
                report.add_alert(
                    regle='R21',
                    severite='MOYEN',
                    message='Des remises négatives ont été détectées.',
                    lignes=negative_discount_rows[:10],
                )

        partial_duplicate_group = {'date', 'client', 'produit', 'quantite', 'montant_total'}
        if partial_duplicate_group.issubset(reverse_mapping):
            date_col = reverse_mapping['date']
            client_col = reverse_mapping['client']
            product_col = reverse_mapping['produit']
            quantity_col = reverse_mapping['quantite']
            amount_col = reverse_mapping['montant_total']
            grouped = dataframe.groupby([date_col, client_col, product_col, quantity_col], dropna=False)[amount_col].nunique(dropna=True)
            conflicting_keys = grouped[grouped > 1]
            if not conflicting_keys.empty:
                mask = dataframe.set_index([date_col, client_col, product_col, quantity_col]).index.isin(conflicting_keys.index)
                invalid_rows = dataframe.loc[mask, '_row_number'].astype(int).tolist()
                report.add_alert(
                    regle='R04',
                    severite='MOYEN',
                    message='Des doublons partiels avec montants divergents ont été détectés. Une revue M3 est requise.',
                    lignes=invalid_rows[:10],
                )
        return dataframe
