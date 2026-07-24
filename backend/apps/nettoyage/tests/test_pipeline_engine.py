import pytest
from pathlib import Path

import pandas as pd
from django.contrib.auth.models import User

from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.engine import LoaderService, NettoyagePipeline
from apps.nettoyage.engine.montant_cleaner import MontantCleaner
from apps.nettoyage.engine.report import CleaningReport
from apps.nettoyage.engine.text_cleaner import TextCleaner
from apps.nettoyage.services import suggest_cleaning


@pytest.mark.django_db
def test_pipeline_generates_core_report_with_mapping_corrections_and_score():
    user = User.objects.create_user(username='pipe_core', email='pipe_core@example.com')
    source = DataSource.objects.create(
        name='Ventes_Mars2026.csv',
        source_type='csv',
        uploaded_by=user,
        encoding='utf-8',
        delimiter=';',
        has_header=True,
        checksum_md5='abc123',
    )
    RawData.objects.bulk_create(
        [
            RawData(source=source, row_number=1, data={'Mont_TTC': '1 740 000 FCFA', 'Qté': '2', 'Date vente': '01/03/2026', 'Client_Nom': 'DIST. OUAGA  '}, validation_status='valid'),
            RawData(source=source, row_number=2, data={'Mont_TTC': '1 740 000 FCFA', 'Qté': '2', 'Date vente': '01/03/2026', 'Client_Nom': 'DIST. OUAGA  '}, validation_status='valid'),
            RawData(source=source, row_number=3, data={'Mont_TTC': '', 'Qté': '', 'Date vente': '', 'Client_Nom': '   '}, validation_status='warning'),
        ]
    )

    cleaned_df, report = NettoyagePipeline(source=source, user_id=user.id).analyze_source()

    assert len(cleaned_df) == 1
    mapped_targets = {item['standard'] for item in report['mapping']['colonnes_mappees']}
    assert {'montant_total', 'quantite', 'date', 'client'}.issubset(mapped_targets)
    correction_rules = {item['regle'] for item in report['corrections']}
    assert {'R01', 'R03', 'R06', 'R10', 'R14'}.issubset(correction_rules)
    assert report['metadata']['separateur_detecte'] == ';'
    assert report['rollback']['disponible'] is True
    assert report['score']['global'] == report['score_qualite']
    assert report['score']['couleur'] in {'vert', 'bleu', 'orange', 'rouge'}


@pytest.mark.django_db
def test_loader_enriches_metadata_from_csv_file():
    user = User.objects.create_user(username='pipe_loader', email='pipe_loader@example.com')
    csv_path = Path('test_media/nettoyage_loader_ventes.csv')
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes('Date vente;Mont_TTC;Client_Nom\n01/03/2026;1740000;Marché Central\n'.encode('cp1252'))
    source = DataSource.objects.create(
        name='ventes.csv',
        source_type='csv',
        uploaded_by=user,
        file_path=str(csv_path),
        encoding='utf-8',
        delimiter=',',
        has_header=False,
    )
    RawData.objects.create(
        source=source,
        row_number=1,
        data={'Date vente': '01/03/2026', 'Mont_TTC': '1740000', 'Client_Nom': 'Marché Central'},
        validation_status='valid',
    )

    _, report = NettoyagePipeline(source=source, user_id=user.id).analyze_source()

    assert report['metadata']['encodage_detecte'] in {'cp1252', 'iso-8859-1', 'windows-1252'}
    assert report['metadata']['separateur_detecte'] == ';'
    assert report['metadata']['has_header'] is True
    assert report['metadata']['est_donnee_exploitable'] is True


def test_loader_classifies_summary_like_single_sheet_as_non_data():
    loader = LoaderService()
    sample = pd.DataFrame(
        [
            ['Résumé mensuel', None, None],
            ['Chiffre du mois', None, None],
            ['Commentaires du manager', None, None],
        ]
    )

    analysis = loader._classify_tabular_content(sample, header_row_index=0)

    assert analysis['is_data_like'] is False
    assert analysis['content_type'] in {'resume_ou_notes', 'feuille_semistructuree', 'vide'}


@pytest.mark.django_db
def test_suggest_cleaning_returns_mapping_alerts_and_report():
    user = User.objects.create_user(username='pipe_suggest', email='pipe_suggest@example.com')
    source = DataSource.objects.create(name='Suggest.csv', source_type='csv', uploaded_by=user)
    RawData.objects.create(
        source=source,
        row_number=1,
        data={'Date vente': '01/03/2026', 'Mont_TTC': '15000 FCFA', 'Libelle inconnu': 'Pack Promo'},
        validation_status='warning',
    )

    payload = suggest_cleaning(source=source)

    assert 'cleaning_report' in payload
    assert 'mapping' in payload
    assert 'alertes' in payload
    assert 'score_detail' in payload
    assert payload['mapping']['colonnes_mappees']


def test_montant_cleaner_normalizes_major_fcfa_formats_and_flags_outliers():
    cleaner = MontantCleaner()
    report = CleaningReport(
        fichier_id='1',
        nom_fichier='montants.csv',
        lignes_initiales=4,
        colonnes_initiales=1,
        metadata={},
    )
    dataframe = pd.DataFrame(
        [
            {'_row_number': 1, 'Mont_TTC': '1 740 000 FCFA'},
            {'_row_number': 2, 'Mont_TTC': '(1 740 000)'},
            {'_row_number': 3, 'Mont_TTC': '1,74M'},
            {'_row_number': 4, 'Mont_TTC': '15'},
        ]
    )
    mapping = {'Mont_TTC': {'standard': 'montant_total'}}

    cleaned = cleaner.clean(dataframe, report, mapping)

    assert cleaned['Mont_TTC'].tolist()[:3] == [1740000, -1740000, 1740000]
    assert any(alert['regle'] == 'R13' for alert in report.alertes)


def test_text_cleaner_preserves_local_accents_and_exposes_semantic_review_actions():
    cleaner = TextCleaner()
    report = CleaningReport(
        fichier_id='2',
        nom_fichier='clients.csv',
        lignes_initiales=3,
        colonnes_initiales=1,
        metadata={},
    )
    dataframe = pd.DataFrame(
        [
            {'_row_number': 1, 'Client_Nom': '  DIST. OUAGA  '},
            {'_row_number': 2, 'Client_Nom': 'Dist Ouaga'},
            {'_row_number': 3, 'Client_Nom': 'Konaté'},
        ]
    )
    mapping = {'Client_Nom': {'standard': 'client'}}

    cleaned = cleaner.clean(dataframe, report, mapping)

    assert cleaned.loc[0, 'Client_Nom'] == 'Dist. Ouaga'
    assert cleaned.loc[2, 'Client_Nom'] == 'Konaté'
    assert any(alert['regle'] == 'R16' for alert in report.alertes)
