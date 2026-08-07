from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nettoyage', '0009_structural_reconstruction'),
    ]

    operations = [
        migrations.AddField(
            model_name='correctionexample',
            name='sous_type_transformation',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Cell-level sub-type for filtered similarity search: '
                    'extraction_champs_texte_libre, correction_caracteres_ambigus, '
                    'scission_valeur_unite, explosion_liste_delimitee, or empty'
                ),
                max_length=50,
            ),
        ),
    ]
