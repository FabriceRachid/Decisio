import pytest
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from apps.ingestion.models import DataSource, RawData
from apps.ingestion.signals import trigger_auto_cleaning_on_completion


@pytest.mark.django_db
class TestDashboardAnalyticsAPI:
    def setup_method(self):
        post_save.disconnect(trigger_auto_cleaning_on_completion, sender=DataSource)
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='SecurePass123!',
        )
        self.viewer = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='SecurePass123!',
        )
        self.viewer.profile.role = 'viewer'
        self.viewer.profile.save(update_fields=['role'])

        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='SecurePass123!',
        )

    def teardown_method(self):
        post_save.connect(trigger_auto_cleaning_on_completion, sender=DataSource)

    def _build_source(self, user, name='ventes.csv'):
        return DataSource.objects.create(
            name=name,
            source_type='csv',
            uploaded_by=user,
            status='completed',
            row_count=4,
            column_count=5,
        )

    def test_dashboard_analytics_returns_rankings_for_authenticated_reader(self, api_client):
        source = self._build_source(self.viewer)
        RawData.objects.bulk_create([
            RawData(
                source=source,
                row_number=1,
                data={
                    'product': 'Farine 50kg',
                    'client': 'Topaz Distribution',
                    'region': 'Ouagadougou',
                    'amount': '1740000',
                    'quantity': '120',
                    'date': '2026-03-01',
                },
            ),
            RawData(
                source=source,
                row_number=2,
                data={
                    'product': 'Huile 5L',
                    'client': 'Marches du Faso',
                    'region': 'Bobo-Dioulasso',
                    'amount': '697000',
                    'quantity': '85',
                    'date': '2026-03-02',
                },
            ),
            RawData(
                source=source,
                row_number=3,
                data={
                    'product': 'Farine 50kg',
                    'client': 'Topaz Distribution',
                    'region': 'Ouagadougou',
                    'amount': '1260000',
                    'quantity': '90',
                    'date': '2026-04-01',
                },
            ),
        ])

        api_client.force_authenticate(user=self.viewer)
        response = api_client.get('/api/dashboard/analytics/')

        assert response.status_code == 200
        assert response.data['summary']['rows_count'] == 3
        assert response.data['summary']['sources_count'] == 1
        assert response.data['top_products'][0]['name'] == 'Farine 50kg'
        assert response.data['top_clients'][0]['name'] == 'Topaz Distribution'
        assert response.data['territories'][0]['name'] == 'Ouagadougou'
        assert len(response.data['sales_trend']) == 2

    def test_dashboard_analytics_filters_rows_by_owner_for_non_admin(self, api_client):
        own_source = self._build_source(self.owner, name='owner.csv')
        other_source = self._build_source(self.other_user, name='other.csv')

        RawData.objects.create(
            source=own_source,
            row_number=1,
            data={'product': 'Riz 25kg', 'client': 'Client A', 'region': 'Centre', 'amount': '1000'},
        )
        RawData.objects.create(
            source=other_source,
            row_number=1,
            data={'product': 'Produit cache', 'client': 'Client cache', 'region': 'Nord', 'amount': '9000'},
        )

        api_client.force_authenticate(user=self.owner)
        response = api_client.get('/api/dashboard/analytics/')

        assert response.status_code == 200
        assert response.data['summary']['rows_count'] == 1
        assert response.data['top_products'][0]['name'] == 'Riz 25kg'
        assert all(item['name'] != 'Produit cache' for item in response.data['top_products'])
