"""
Tests for Dashboard Preferences and Views (M5 Advanced Features)
"""
import json
from django.contrib.auth.models import User
from django.test import TestCase
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from apps.dashboard.models import PreferenceUtilisateur, VuePersonnalisee
from apps.dashboard.services import default_preferences_for_role


class PreferenceUtilisateurModelTests(TestCase):
    """Tests for PreferenceUtilisateur model"""

    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='testpass123')

    def test_create_preference(self):
        """Test creating a new preference record"""
        pref = PreferenceUtilisateur.objects.create(
            user=self.user,
            colonnes_tableau=['region', 'produit', 'montant'],
            kpis_visibles=['ventes_totales', 'quantite'],
            kpis_ordre=['ventes_totales', 'quantite'],
            devise='FCFA',
            format_nombres='fr-FR'
        )
        self.assertEqual(pref.user, self.user)
        self.assertEqual(len(pref.colonnes_tableau), 3)
        self.assertEqual(pref.devise, 'FCFA')

    def test_preference_string_representation(self):
        """Test __str__ method"""
        pref = PreferenceUtilisateur.objects.create(
            user=self.user,
            colonnes_tableau=['region'],
            kpis_visibles=['ventes'],
            kpis_ordre=['ventes'],
        )
        self.assertIn(self.user.username, str(pref))

    def test_default_preferences_for_role(self):
        """Test that role-based defaults are generated correctly"""
        analyst_prefs = default_preferences_for_role('analyst')
        self.assertIn('colonnes_tableau', analyst_prefs)
        self.assertIn('kpis_visibles', analyst_prefs)
        self.assertEqual(analyst_prefs.get('devise'), 'FCFA')

        viewer_prefs = default_preferences_for_role('viewer')
        self.assertTrue(len(viewer_prefs['colonnes_tableau']) <= len(analyst_prefs['colonnes_tableau']))


class VuePersonnaliseeModelTests(TestCase):
    """Tests for VuePersonnalisee model"""

    def setUp(self):
        self.user = User.objects.create_user(username='vue_test_user', password='testpass123')

    def test_create_vue(self):
        """Test creating a new personalized view"""
        config = {
            'lignes': ['region'],
            'colonnes': ['mois'],
            'metric': 'montant_total',
            'aggfunc': 'sum'
        }
        vue = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue Régionale',
            description='Analyse par région',
            icone='📊',
            config=config,
            ordre=1
        )
        self.assertEqual(vue.user, self.user)
        self.assertEqual(vue.config['metric'], 'montant_total')

    def test_max_20_vues_per_user(self):
        """Test that a user can create up to 20 views"""
        config = {'metric': 'test'}
        for i in range(20):
            VuePersonnalisee.objects.create(
                user=self.user,
                nom=f'Vue {i}',
                config=config,
                ordre=i
            )
        self.assertEqual(VuePersonnalisee.objects.filter(user=self.user).count(), 20)

        # 21st view should raise validation error
        vue_21 = VuePersonnalisee(
            user=self.user,
            nom='Vue 21',
            config=config,
            ordre=20
        )
        with self.assertRaises(ValidationError):
            vue_21.clean()

    def test_vue_string_representation(self):
        """Test __str__ method"""
        config = {'metric': 'test'}
        vue = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Test Vue',
            config=config
        )
        self.assertEqual(str(vue), 'Test Vue')

    def test_is_default_uniqueness(self):
        """Test that only one view can be default per user"""
        config = {'metric': 'test'}
        vue1 = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue 1',
            config=config,
            is_default=True
        )
        self.assertTrue(vue1.is_default)

        vue2 = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue 2',
            config=config,
            is_default=False
        )
        vue2.is_default = True
        vue2.save()

        # Refresh vue1 from DB
        vue1.refresh_from_db()
        self.assertFalse(vue1.is_default)
        self.assertTrue(vue2.is_default)


class PreferenceAPITests(APITestCase):
    """Tests for Preference API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='api_test', password='testpass123')
        self.client.force_authenticate(user=self.user)

    def test_get_preferences_auto_create(self):
        """Test GET /api/dashboard/preferences/ auto-creates preferences if missing"""
        response = self.client.get('/api/dashboard/preferences/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        # Verify preference was created
        pref = PreferenceUtilisateur.objects.get(user=self.user)
        self.assertIsNotNone(pref)

    def test_update_preferences(self):
        """Test PUT /api/dashboard/preferences/ updates preferences"""
        # First GET to auto-create
        self.client.get('/api/dashboard/preferences/')

        update_data = {
            'colonnes_tableau': [],
            'kpis_visibles': [],
            'kpis_ordre': [],
            'periode_defaut': 'trimestre_en_cours',
            'devise': 'EUR'
        }
        response = self.client.put('/api/dashboard/preferences/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['devise'], 'EUR')

    def test_reset_preferences(self):
        """Test POST /api/dashboard/preferences/reset/ resets to defaults"""
        # Create custom preferences
        PreferenceUtilisateur.objects.create(
            user=self.user,
            colonnes_tableau=['custom1', 'custom2'],
            kpis_visibles=['custom_kpi'],
            kpis_ordre=['custom_kpi'],
            devise='EUR'
        )

        response = self.client.post('/api/dashboard/preferences/reset/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify reset to defaults
        pref = PreferenceUtilisateur.objects.get(user=self.user)
        self.assertEqual(pref.devise, 'FCFA')

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access preferences"""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/dashboard/preferences/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class VuePersonnaliseeAPITests(APITestCase):
    """Tests for Personalized Views API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='vue_api_test', password='testpass123')
        self.client.force_authenticate(user=self.user)
        VuePersonnalisee.objects.filter(user=self.user).delete()

    def test_list_vues(self):
        """Test GET /api/dashboard/vues/"""
        config = {'metric': 'montant_total', 'aggfunc': 'sum'}
        VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue 1',
            config=config,
            ordre=1
        )
        response = self.client.get('/api/dashboard/vues/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else (response.data.get('results') or [])
        noms = [v['nom'] for v in results]
        self.assertIn('Vue 1', noms)

    def test_create_vue(self):
        """Test POST /api/dashboard/vues/"""
        config = {
            'lignes': ['region'],
            'colonnes': ['mois'],
            'metric': 'montant_total',
            'aggfunc': 'sum'
        }
        data = {
            'nom': 'Nouvelle Vue',
            'description': 'Test description',
            'config': config,
            'icone': '📈'
        }
        response = self.client.post('/api/dashboard/vues/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nom'], 'Nouvelle Vue')

    def test_retrieve_vue(self):
        """Test GET /api/dashboard/vues/{id}/"""
        config = {'metric': 'test'}
        vue = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue à récupérer',
            config=config
        )
        response = self.client.get(f'/api/dashboard/vues/{vue.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nom'], 'Vue à récupérer')

    def test_update_vue(self):
        """Test PUT /api/dashboard/vues/{id}/"""
        config = {'metric': 'old'}
        vue = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue à modifier',
            config=config
        )
        new_config = {'metric': 'new', 'aggfunc': 'avg'}
        update_data = {
            'nom': 'Vue modifiée',
            'config': new_config
        }
        response = self.client.put(f'/api/dashboard/vues/{vue.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['config']['metric'], 'new')

    def test_delete_vue(self):
        """Test DELETE /api/dashboard/vues/{id}/"""
        config = {'metric': 'test'}
        vue = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue à supprimer',
            config=config
        )
        response = self.client.delete(f'/api/dashboard/vues/{vue.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(VuePersonnalisee.objects.filter(id=vue.id).exists())

    def test_set_default_action(self):
        """Test POST /api/dashboard/vues/{id}/default/"""
        config = {'metric': 'test'}
        vue1 = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue 1',
            config=config,
            is_default=True,
            ordre=1
        )
        vue2 = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue 2',
            config=config,
            ordre=2
        )

        response = self.client.post(f'/api/dashboard/vues/{vue2.id}/default/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        vue1.refresh_from_db()
        vue2.refresh_from_db()
        self.assertFalse(vue1.is_default)
        self.assertTrue(vue2.is_default)

    def test_duplicate_action(self):
        """Test POST /api/dashboard/vues/{id}/dupliquer/"""
        config = {'metric': 'test', 'lignes': ['region']}
        vue = VuePersonnalisee.objects.create(
            user=self.user,
            nom='Vue à dupliquer',
            config=config,
            description='Original description'
        )

        response = self.client.post(f'/api/dashboard/vues/{vue.id}/dupliquer/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('(copie)', response.data['nom'])
        self.assertEqual(response.data['config'], config)

    def test_other_user_cannot_access_vues(self):
        """Test that users cannot access other users' views"""
        other_user = User.objects.create_user(username='other_user', password='testpass123')
        config = {'metric': 'test'}
        vue = VuePersonnalisee.objects.create(
            user=other_user,
            nom='Vue privée',
            config=config
        )

        response = self.client.get(f'/api/dashboard/vues/{vue.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access views"""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/dashboard/vues/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
