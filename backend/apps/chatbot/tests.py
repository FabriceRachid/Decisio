from django.test import TestCase

# Create your tests here.
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ia_interpretation.services import KPIInterpretationError


class ChatbotApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chatadmin',
            email='chatadmin@example.com',
            password='testpass123',
        )
        self.client.force_authenticate(user=self.user)

    def test_create_chat_session(self):
        response = self.client.post('/api/chatbot/sessions/', {'session_name': 'Direction'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['session_name'], 'Direction')
        self.assertEqual(response.data['message_count'], 0)

    @patch('apps.chatbot.services.persist_ai_analysis', return_value=17)
    @patch('apps.chatbot.services.interpret_kpis_with_openai')
    @patch('apps.chatbot.services.build_kpi_context_for_user')
    def test_send_message_returns_bot_response(self, mock_context, mock_interpret, _mock_persist):
        session_response = self.client.post('/api/chatbot/sessions/', {'session_name': 'Direction'}, format='json')
        session_id = session_response.data['id']

        mock_context.return_value = (
            [
                {
                    'id': 11,
                    'code': 'CA_MENS',
                    'name': 'Chiffre d affaires mensuel',
                    'latest_calculation': {'value': 42.6, 'status': 'on_target', 'period_label': 'Mars 2026'},
                }
            ],
            [],
        )
        mock_interpret.return_value = {
            'text': 'Constat principal : le chiffre d affaires progresse.',
            'model': 'gpt-4o',
            'tokens_used': 120,
            'processing_time_ms': 540,
        }

        response = self.client.post(
            f'/api/chatbot/sessions/{session_id}/messages/',
            {'content': 'Pourquoi le chiffre d affaires monte ?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user_message']['message_type'], 'user')
        self.assertEqual(response.data['bot_message']['message_type'], 'bot')
        self.assertIn('Constat principal', response.data['bot_message']['content'])
        self.assertEqual(response.data['bot_message']['attached_data']['domain'], 'dashboard')

    @patch('apps.chatbot.services._build_alerts_snapshot')
    def test_alert_question_uses_alert_orchestrator(self, mock_snapshot):
        session_response = self.client.post('/api/chatbot/sessions/', {'session_name': 'Alertes'}, format='json')
        session_id = session_response.data['id']

        mock_snapshot.return_value = {
            'alerts': [
                {
                    'id': 1,
                    'name': 'Marge sous seuil',
                    'kpi_name': 'Marge brute',
                    'alert_type': 'critical',
                    'trigger_count': 3,
                    'is_triggered': True,
                    'last_triggered_at': None,
                }
            ],
            'conflicts': [
                {
                    'id': 9,
                    'description': 'Valeurs contradictoires',
                    'severity': 'critical',
                    'priority': 10,
                    'source_name': 'ERP_Export_Sage',
                    'status': 'detected',
                }
            ],
            'summary': {
                'active_alerts': 1,
                'triggered_alerts': 1,
                'open_conflicts': 1,
                'critical_conflicts': 1,
            },
        }

        response = self.client.post(
            f'/api/chatbot/sessions/{session_id}/messages/',
            {'content': 'Resume les alertes critiques de cette semaine'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['bot_message']['model_used'], 'chatbot-alerts-heuristic')
        self.assertIn('alerte(s) KPI', response.data['bot_message']['content'])

    @patch('apps.chatbot.services.persist_ai_analysis', return_value=19)
    @patch('apps.chatbot.services.interpret_kpis_with_openai')
    @patch('apps.chatbot.services.build_kpi_context_for_user')
    def test_page_context_changes_domain_routing(self, mock_context, mock_interpret, _mock_persist):
        session_response = self.client.post('/api/chatbot/sessions/', {'session_name': 'Stocks'}, format='json')
        session_id = session_response.data['id']

        mock_context.return_value = (
            [{'id': 3, 'code': 'STOCK_COUV', 'name': 'Couverture stock', 'latest_calculation': {'value': 12, 'status': 'warning', 'period_label': 'Mars 2026'}}],
            [],
        )
        mock_interpret.return_value = {
            'text': 'Constat principal : la couverture stock se tend.',
            'model': 'gpt-4o',
            'tokens_used': 90,
            'processing_time_ms': 410,
        }

        response = self.client.post(
            f'/api/chatbot/sessions/{session_id}/messages/',
            {
                'content': 'Que faut-il traiter maintenant ?',
                'context': {'page': 'stocks', 'page_label': 'Stocks', 'filter_label': 'Mars 2026'},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['bot_message']['attached_data']['domain'], 'stocks')

    @patch('apps.chatbot.services.build_kpi_context_for_user', side_effect=KPIInterpretationError('Aucun KPI disponible'))
    def test_fallback_response_is_returned_when_kpi_context_is_missing(self, _mock_context):
        session_response = self.client.post('/api/chatbot/sessions/', {'session_name': 'Fallback'}, format='json')
        session_id = session_response.data['id']

        response = self.client.post(
            f'/api/chatbot/sessions/{session_id}/messages/',
            {'content': 'Pourquoi la marge baisse ?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['bot_message']['model_used'], 'chatbot-fallback')
        self.assertTrue(response.data['bot_message']['fallback_used'])
        self.assertIn('synthese heuristique', response.data['bot_message']['content'])
