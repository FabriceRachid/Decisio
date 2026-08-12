"""
Tests pour le cache du dashboard auto-build (même dashboard, pas de régénération).
"""
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status

from apps.dashboard.models import Dashboard, Widget
from apps.dashboard.services import dashboard_auto_cache_key, DASHBOARD_AUTO_CACHE_TTL
from apps.ingestion.models import DataSource


class DashboardAutoBuildCacheTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='dashcache', password='testpass123')
        self.user.profile.role = 'analyst'
        self.user.profile.save(update_fields=['role'])
        self.client.force_authenticate(user=self.user)
        self.source = DataSource.objects.create(
            name='Source Cache', source_type='csv', uploaded_by=self.user,
            status='completed',
        )
        self.slug = f"dashboard-auto-{self.user.id}-{self.source.id}"
        self.dashboard = Dashboard.objects.create(
            created_by=self.user,
            slug=self.slug,
            name='Source Cache',
            layout={'columns': 4},
            grid_columns=12,
        )
        Widget.objects.create(
            dashboard=self.dashboard,
            widget_type='metric_card',
            position_x=0, position_y=0, width=3, height=2,
            configuration={
                'measure': '_row_number', 'aggregation': 'count',
                'group_by': [], 'source_id': self.source.id,
                'source_table': 'ingestion_rawdata', 'auto_generated': True,
            },
            title='Count',
        )

    def test_get_populates_and_reuses_cache(self):
        url = f'/api/dashboard/auto-build/?source_id={self.source.id}'
        resp1 = self.client.get(url)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        key = dashboard_auto_cache_key(self.user.id, self.source.id)
        cached = cache.get(key)
        self.assertIsNotNone(cached, 'le dashboard doit être mis en cache')
        self.assertEqual(cached['dashboard']['id'], self.dashboard.id)
        self.assertGreaterEqual(len(cached['widgets']), 1)

        # Un second GET doit servir le cache identique
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['dashboard']['id'], self.dashboard.id)

    def test_add_widget_invalidates_cache(self):
        url = f'/api/dashboard/auto-build/?source_id={self.source.id}'
        self.client.get(url)
        key = dashboard_auto_cache_key(self.user.id, self.source.id)
        self.assertIsNotNone(cache.get(key))

        resp = self.client.post('/api/dashboard/add-widget/', {
            'source_id': self.source.id,
            'config': {
                'title': 'Custom', 'measure': '_row_number',
                'aggregation': 'count', 'group_by': [],
            },
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(cache.get(key), 'le cache doit être invalidé après un ajout')

        # Et le GET renvoie le widget ajouté
        cached = self.client.get(url)
        titles = [w['title'] for w in cached.data['widgets']]
        self.assertIn('Custom', titles)

    def test_delete_widget_invalidates_cache(self):
        widget = Widget.objects.create(
            dashboard=self.dashboard,
            widget_type='metric_card',
            position_x=6, position_y=0, width=3, height=2,
            configuration={
                'measure': '_row_number', 'aggregation': 'sum',
                'group_by': [], 'source_id': self.source.id,
                'source_table': 'ingestion_rawdata',
            },
            title='Manual',
        )
        self.client.get(f'/api/dashboard/auto-build/?source_id={self.source.id}')
        key = dashboard_auto_cache_key(self.user.id, self.source.id)
        self.assertIsNotNone(cache.get(key))

        resp = self.client.delete(f'/api/dashboard/widgets/{widget.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(cache.get(key), 'le cache doit être invalidé après suppression')