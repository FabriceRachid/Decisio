from __future__ import annotations

import importlib
import re
from difflib import SequenceMatcher

import pandas as pd  # type: ignore[reportMissingModuleSource]

from .report import CleaningReport

try:
    fuzz = getattr(importlib.import_module('thefuzz'), 'fuzz', None)
except Exception:  # pragma: no cover - optional dependency
    fuzz = None


STANDARD_FIELDS = {
    'date': ['date', 'dt', 'date vente', 'date facture'],
    'date_commande': ['date commande', 'purchase date', 'order date', 'datefirstpurchase', 'date first purchase'],
    'date_livraison': ['date livraison', 'delivery date', 'ship date'],
    'date_naissance': ['date naissance', 'birthdate', 'birth date', 'date de naissance', 'dob'],
    'date_premier_achat': ['date premier achat', 'first purchase date', 'datefirstpurchase', 'date first purchase'],
    'montant_total': ['montant total', 'mont ttc', 'total fact', 'mnt', 'montant ttc', 'total amount'],
    'prix_unitaire': ['prix unitaire', 'prixunitaire', 'pu', 'prix unit', 'unit price', 'unitprice'],
    'quantite': ['qte', 'qté', 'quantite', 'qty', 'quantity'],
    'client': ['client', 'client nom', 'nom client', 'customer', 'customer name', 'client_name'],
    'produit': ['produit', 'designation', 'article', 'product', 'item'],
    'reference': ['reference', 'ref', 'réf', 'sku', 'product reference', 'key', 'alternate key', 'product key'],
    'categorie': ['categorie', 'catégorie', 'famille', 'category', 'subcategory', 'sub category', 'product category'],
    'description': ['description', 'libelle', 'label', 'name', 'display name', 'product name', 'subcategory name'],
    'vendeur': ['vendeur', 'commercial', 'agent', 'salesperson', 'sales rep'],
    'canal': ['canal', 'channel', 'sales channel'],
    'region': ['region', 'zone', 'territoire', 'country', 'province'],
    'stock_initial': ['stock initial', 'opening stock'],
    'stock_final': ['stock final', 'closing stock'],
    'entrepot': ['entrepot', 'dépôt', 'depot', 'warehouse'],
    'id_commande': ['id commande', 'commande id', 'num commande', 'order id'],
    'id_facture': ['id facture', 'facture id', 'num facture', 'invoice id'],
    'id_produit': ['id produit', 'produit id', 'product id'],
    'id_client': ['id client', 'client id', 'customer id'],
    'telephone': ['telephone', 'phone', 'mobile', 'tel', 'gsm', 'phone number'],
    'email': ['email', 'mail', 'e-mail', 'email address'],
    'prenom': ['prenom', 'prénom', 'firstname', 'first name', 'given name'],
    'nom': ['nom', 'lastname', 'last name', 'surname', 'family name'],
    'civilite': ['civilite', 'civility', 'title', 'salutation', 'mr', 'mrs'],
    'genre': ['gender', 'genre', 'sexe', 'sex'],
}

FIELD_FAMILIES = {
    'date': 'date',
    'date_commande': 'date',
    'date_livraison': 'date',
    'date_naissance': 'date',
    'date_premier_achat': 'date',
    'montant_total': 'amount',
    'prix_unitaire': 'amount',
    'quantite': 'quantity',
    'client': 'entity',
    'produit': 'entity',
    'reference': 'identifier',
    'categorie': 'entity',
    'description': 'entity',
    'vendeur': 'entity',
    'canal': 'entity',
    'region': 'geo',
    'stock_initial': 'quantity',
    'stock_final': 'quantity',
    'entrepot': 'geo',
    'id_commande': 'identifier',
    'id_facture': 'identifier',
    'id_produit': 'identifier',
    'id_client': 'identifier',
    'telephone': 'phone',
    'email': 'email',
    'prenom': 'person_name',
    'nom': 'person_name',
    'civilite': 'title',
    'genre': 'gender',
}

HARD_LABEL_RULES = {
    'telephone': {'keywords': {'phone', 'telephone', 'tel', 'mobile', 'gsm'}},
    'email': {'keywords': {'email', 'mail', 'e-mail'}},
    'prenom': {'keywords': {'firstname', 'first name', 'prenom', 'prénom', 'given name'}},
    'nom': {'keywords': {'lastname', 'last name', 'surname', 'family name', 'nom'}},
    'civilite': {'keywords': {'title', 'civilite', 'civility', 'salutation', 'mr', 'mrs', 'ms', 'mme'}},
    'genre': {'keywords': {'gender', 'genre', 'sex', 'sexe'}},
    'date_naissance': {'keywords': {'birth', 'naissance', 'dob', 'birthdate'}},
    'date_premier_achat': {'keywords': {'first purchase', 'datefirstpurchase', 'premier achat'}},
    'reference': {'keywords': {'reference', 'ref', 'sku', 'alternatekey', 'alternate key', 'productkey', 'product key'}},
    'categorie': {'keywords': {'category', 'categorie', 'subcategory', 'sub category'}},
    'description': {'keywords': {'description', 'libelle', 'label', 'display name'}},
}

CONTENT_REGEX = {
    'phone': re.compile(r'^\+?[0-9][0-9\s().-]{6,}$'),
    'email': re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    'gender': re.compile(r'^(m|f|male|female|homme|femme|masculin|feminin|féminin)$', re.IGNORECASE),
    'title': re.compile(r'^(mr|mrs|ms|mme|mlle|m|dr|prof)$', re.IGNORECASE),
    'person_name': re.compile(r"^[A-Za-zÀ-ÿ' -]{2,}$"),
}


def _normalize_label(label: str) -> str:
    normalized = re.sub(r'[\W_]+', ' ', str(label).strip().lower(), flags=re.UNICODE)
    return re.sub(r'\s+', ' ', normalized).strip()


def _similarity(left: str, right: str) -> int:
    if fuzz is not None:
        return int(fuzz.token_sort_ratio(left, right))
    return int(SequenceMatcher(None, left, right).ratio() * 100)


def _label_has_keyword(normalized_label: str, keyword: str) -> bool:
    keyword = _normalize_label(keyword)
    if not keyword:
        return False
    if ' ' in keyword:
        return keyword in normalized_label
    tokens = set(normalized_label.split())
    return keyword in tokens or (len(keyword) >= 4 and keyword in normalized_label)


def _looks_like_date(value: str) -> bool:
    text = str(value).strip().lower()
    if not text:
        return False
    if re.search(r'[\/\-.]', text):
        return True
    if re.search(r'[a-zà-ÿ]{3,}', text):
        return True
    return bool(re.fullmatch(r'\d{8}', text))


class MappingService:
    CONFIRMED_THRESHOLD = 88
    SUGGESTION_THRESHOLD = 72

    def map(self, dataframe: pd.DataFrame, report: CleaningReport) -> dict[str, dict[str, int | str | bool]]:
        mapping: dict[str, dict[str, int | str | bool]] = {}
        detected_domain = self._detect_dataset_domain(dataframe)
        report.metadata['mapping_contexte'] = {'dataset_type': detected_domain}
        report.metadata['mapping_resultat'] = {
            'colonnes_extra': [],
            'colonnes_a_revoir': [],
        }

        for column in dataframe.columns:
            if column == '_row_number':
                continue

            normalized = _normalize_label(column)
            if any(_label_has_keyword(normalized, keyword) for keyword in {'suffix', 'namestyle', 'name style'}):
                report.add_unmapped(column)
                report.metadata['mapping_resultat']['colonnes_extra'].append(f'extra_{column}')
                report.metadata['mapping_resultat']['colonnes_a_revoir'].append(
                    {
                        'original': column,
                        'profil_detecte': None,
                        'meilleur_candidat': None,
                        'score': 0,
                    }
                )
                continue

            inferred_profile = self._infer_content_profile(dataframe[column])
            direct_match = self._resolve_direct_match(normalized, inferred_profile)
            if direct_match is not None:
                mapping[column] = {'standard': direct_match, 'score': 100, 'confirmed': True, 'method': 'direct_rule'}
                report.add_mapping(original=column, standard=direct_match, score=100, confirmed=True, methode='direct_rule')
                continue

            scores = []
            for standard_field, aliases in STANDARD_FIELDS.items():
                candidates = [standard_field, *aliases]
                base_score = max(_similarity(normalized, _normalize_label(candidate)) for candidate in candidates)
                adjusted_score = max(
                    0,
                    min(
                        100,
                        base_score + self._heuristic_adjustment(standard_field, normalized, dataframe[column], inferred_profile, detected_domain),
                    ),
                )
                scores.append((standard_field, adjusted_score))

            scores.sort(key=lambda item: item[1], reverse=True)
            best_field, best_score = scores[0]
            second_score = scores[1][1] if len(scores) > 1 else -1
            is_ambiguous = second_score >= 0 and (best_score - second_score) < 6 and best_score < self.CONFIRMED_THRESHOLD

            content_match = self._resolve_content_match(inferred_profile, normalized)
            if content_match and best_score < self.CONFIRMED_THRESHOLD:
                best_field = content_match
                best_score = max(best_score, self.CONFIRMED_THRESHOLD if inferred_profile in {'date', 'phone', 'email', 'gender', 'title'} else self.SUGGESTION_THRESHOLD + 6)
                second_score = -1
                is_ambiguous = False

            if best_score < self.SUGGESTION_THRESHOLD or is_ambiguous:
                report.add_unmapped(column)
                report.metadata['mapping_resultat']['colonnes_extra'].append(f'extra_{column}')
                report.metadata['mapping_resultat']['colonnes_a_revoir'].append(
                    {
                        'original': column,
                        'profil_detecte': inferred_profile,
                        'meilleur_candidat': best_field,
                        'score': int(best_score),
                    }
                )
                continue

            confirmed = best_score >= self.CONFIRMED_THRESHOLD
            method = 'content_matching' if content_match == best_field else 'fuzzy_matching'
            mapping[column] = {'standard': best_field, 'score': best_score, 'confirmed': confirmed, 'method': method}
            report.add_mapping(original=column, standard=best_field, score=best_score, confirmed=confirmed, methode=method)

        return mapping

    def _resolve_direct_match(self, normalized_label: str, inferred_profile: str | None) -> str | None:
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'client', 'customer', 'client nom', 'nom client', 'customer name'}):
            if not any(_label_has_keyword(normalized_label, keyword) for keyword in {'firstname', 'first name', 'prenom', 'prénom', 'lastname', 'last name', 'surname', 'family name'}):
                return 'client'

        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'subcategory', 'sub category', 'category', 'categorie'}):
            if 'name' in normalized_label or 'label' in normalized_label or 'libelle' in normalized_label:
                return 'categorie'
            if 'key' in normalized_label or 'id' in normalized_label:
                return 'reference'

        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'alternatekey', 'alternate key', 'productkey', 'product key'}):
            return 'reference'

        for standard_field, config in HARD_LABEL_RULES.items():
            keywords = config.get('keywords', set())
            if any(_label_has_keyword(normalized_label, keyword) for keyword in keywords):
                return standard_field

        if 'name' in normalized_label and not any(
            _label_has_keyword(normalized_label, keyword)
            for keyword in {'client', 'customer', 'first', 'last', 'prenom', 'nom', 'surname', 'family'}
        ):
            if any(_label_has_keyword(normalized_label, keyword) for keyword in {'category', 'categorie', 'subcategory', 'sub category'}):
                return 'categorie'
            return 'description'

        if inferred_profile == 'email':
            return 'email'
        if inferred_profile == 'phone':
            return 'telephone'
        if inferred_profile == 'gender':
            return 'genre'
        if inferred_profile == 'title':
            return 'civilite'
        return None

    def _resolve_content_match(self, inferred_profile: str | None, normalized_label: str) -> str | None:
        if inferred_profile == 'date':
            if 'commande' in normalized_label or 'order' in normalized_label or 'purchase' in normalized_label:
                return 'date_commande'
            if 'livraison' in normalized_label or 'delivery' in normalized_label or 'ship' in normalized_label:
                return 'date_livraison'
            if 'birth' in normalized_label or 'naissance' in normalized_label or 'dob' in normalized_label:
                return 'date_naissance'
            if 'first purchase' in normalized_label or 'premier achat' in normalized_label:
                return 'date_premier_achat'
            return 'date'
        if inferred_profile == 'amount':
            if 'unit' in normalized_label or 'unitaire' in normalized_label or 'price' in normalized_label or normalized_label == 'pu':
                return 'prix_unitaire'
            return 'montant_total'
        if inferred_profile == 'quantity':
            return 'quantite'
        if inferred_profile == 'person_name':
            if 'first' in normalized_label or 'prenom' in normalized_label:
                return 'prenom'
            if 'last' in normalized_label or 'surname' in normalized_label or 'nom' in normalized_label:
                return 'nom'
            return 'client'
        if inferred_profile == 'identifier':
            if 'client' in normalized_label:
                return 'id_client'
            if 'product' in normalized_label or 'produit' in normalized_label:
                return 'id_produit'
            if 'invoice' in normalized_label or 'facture' in normalized_label:
                return 'id_facture'
            if 'commande' in normalized_label or 'order' in normalized_label:
                return 'id_commande'
            return 'reference'
        if inferred_profile is None and 'name' in normalized_label:
            if any(_label_has_keyword(normalized_label, keyword) for keyword in {'category', 'categorie', 'subcategory', 'sub category'}):
                return 'categorie'
            return 'description'
        return None

    def _heuristic_adjustment(
        self,
        standard_field: str,
        normalized_label: str,
        series: pd.Series,
        inferred_profile: str | None,
        detected_domain: str,
    ) -> int:
        adjustment = 0

        hard_match_keywords = HARD_LABEL_RULES.get(standard_field, {}).get('keywords', set())
        if any(_label_has_keyword(normalized_label, keyword) for keyword in hard_match_keywords):
            adjustment += 30
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'prix', 'unit', 'unitaire', 'unit price'}):
            if standard_field == 'prix_unitaire':
                adjustment += 25
            elif standard_field == 'quantite':
                adjustment -= 18
        if 'key' in normalized_label or 'id' in normalized_label:
            if standard_field in {'reference', 'id_client', 'id_produit', 'id_facture', 'id_commande'}:
                adjustment += 16
            if standard_field in {'quantite', 'montant_total', 'prix_unitaire', 'client', 'produit'}:
                adjustment -= 24
        if 'name' in normalized_label or 'label' in normalized_label or 'libelle' in normalized_label:
            if standard_field in {'description', 'categorie', 'client', 'produit'}:
                adjustment += 10
            if standard_field in {'quantite', 'montant_total', 'prix_unitaire'}:
                adjustment -= 18

        if self._is_hard_conflict(standard_field, normalized_label, inferred_profile):
            return -70

        field_family = FIELD_FAMILIES.get(standard_field)
        if inferred_profile and field_family == inferred_profile:
            adjustment += 22
        elif inferred_profile and field_family and inferred_profile != field_family:
            adjustment -= 20

        adjustment += self._domain_adjustment(standard_field, detected_domain)

        sample = series.dropna().head(25)
        if sample.empty:
            return adjustment

        as_text = sample.astype(str).str.strip()
        if field_family == 'date':
            parsed = pd.to_datetime(as_text, errors='coerce', dayfirst=True, format='mixed')
            if parsed.notna().mean() >= 0.7 and as_text.apply(_looks_like_date).mean() >= 0.7:
                adjustment += 16

        numeric = pd.to_numeric(as_text.str.replace(' ', ''), errors='coerce')
        if standard_field == 'montant_total' and numeric.notna().mean() >= 0.7 and numeric.median() > 1000:
            adjustment += 15
        if standard_field == 'quantite' and numeric.notna().mean() >= 0.7 and numeric.median() <= 10000:
            adjustment += 12

        return adjustment

    def _infer_content_profile(self, series: pd.Series) -> str | None:
        sample = series.dropna().head(30)
        if sample.empty:
            return None

        text = sample.astype(str).str.strip()
        lowered = text.str.lower()

        if lowered.apply(lambda value: bool(CONTENT_REGEX['email'].match(value))).mean() >= 0.7:
            return 'email'

        parsed_dates = pd.to_datetime(text, errors='coerce', dayfirst=True, format='mixed')
        if parsed_dates.notna().mean() >= 0.7 and text.apply(_looks_like_date).mean() >= 0.7:
            return 'date'

        if lowered.apply(lambda value: bool(CONTENT_REGEX['phone'].match(value))).mean() >= 0.7:
            return 'phone'
        if lowered.apply(lambda value: bool(CONTENT_REGEX['gender'].match(value))).mean() >= 0.7:
            return 'gender'
        if lowered.apply(lambda value: bool(CONTENT_REGEX['title'].match(value))).mean() >= 0.7:
            return 'title'

        numeric = pd.to_numeric(text.str.replace(' ', ''), errors='coerce')
        if numeric.notna().mean() >= 0.7:
            median = float(numeric.dropna().median()) if numeric.notna().any() else 0
            if 0 <= median <= 10000:
                return 'quantity'
            if median > 1000:
                return 'amount'
            return 'identifier'

        if lowered.apply(lambda value: bool(CONTENT_REGEX['person_name'].match(value))).mean() >= 0.8:
            return 'person_name'
        return None

    def _is_hard_conflict(self, standard_field: str, normalized_label: str, inferred_profile: str | None) -> bool:
        field_family = FIELD_FAMILIES.get(standard_field)

        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'suffix', 'namestyle', 'name style'}):
            return True

        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'phone', 'telephone', 'mobile', 'gsm', 'tel'}):
            return standard_field != 'telephone'
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'prix', 'unitaire', 'unit price', 'unit'}):
            return standard_field in {'quantite', 'date', 'date_commande', 'date_livraison', 'date_naissance', 'date_premier_achat'}
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'email', 'mail', 'e mail'}):
            return standard_field != 'email'
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'gender', 'genre', 'sex', 'sexe'}):
            return standard_field != 'genre'
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'firstname', 'first name', 'prenom', 'prénom'}):
            return standard_field != 'prenom'
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'lastname', 'last name', 'surname', 'family name'}):
            return standard_field != 'nom'
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'client', 'customer'}):
            return standard_field in {'prenom', 'nom', 'vendeur', 'region'}
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'birth', 'naissance', 'dob', 'birthdate'}):
            return standard_field not in {'date_naissance'}
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'datefirstpurchase', 'first purchase', 'premier achat'}):
            return standard_field not in {'date_premier_achat', 'date_commande'}
        if any(_label_has_keyword(normalized_label, keyword) for keyword in {'title', 'salutation', 'civilite', 'civility'}):
            return standard_field != 'civilite'
        if ('key' in normalized_label or 'id' in normalized_label) and standard_field in {'quantite', 'montant_total', 'prix_unitaire', 'client', 'produit'}:
            return True
        if ('name' in normalized_label or 'label' in normalized_label or 'libelle' in normalized_label) and standard_field in {'quantite', 'montant_total', 'prix_unitaire'}:
            return True

        if inferred_profile in {'phone', 'email', 'gender', 'title'} and field_family != inferred_profile:
            return True
        return False

    def _detect_dataset_domain(self, dataframe: pd.DataFrame) -> str:
        normalized_columns = [_normalize_label(column) for column in dataframe.columns if column != '_row_number']
        joined = ' '.join(normalized_columns)
        if any(token in joined for token in ['client', 'firstname', 'lastname', 'birthdate', 'gender', 'phone', 'email']):
            return 'customer'
        if any(token in joined for token in ['stock', 'warehouse', 'entrepot']):
            return 'inventory'
        if any(token in joined for token in ['montant', 'prix', 'facture', 'invoice']):
            return 'sales'
        return 'generic'

    def _domain_adjustment(self, standard_field: str, detected_domain: str) -> int:
        if detected_domain == 'customer' and standard_field in {'prenom', 'nom', 'genre', 'civilite', 'telephone', 'email', 'date_naissance', 'date_premier_achat', 'date_commande', 'client'}:
            return 12
        if detected_domain == 'inventory' and standard_field in {'stock_initial', 'stock_final', 'entrepot', 'produit', 'reference'}:
            return 10
        if detected_domain == 'sales' and standard_field in {'montant_total', 'prix_unitaire', 'quantite', 'date', 'date_commande', 'client', 'produit'}:
            return 8
        return 0
