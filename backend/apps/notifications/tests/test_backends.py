from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings

from apps.notifications.backends import BrevoEmailBackend, _split_from


@override_settings(BREVO_API_KEY='xkeysib-test')
@override_settings(DEFAULT_FROM_EMAIL='DecisioBI <no-reply@decisiobi.local>')
class BrevoEmailBackendTests(TestCase):
    def test_split_from(self):
        self.assertEqual(_split_from('Name <a@b.com>'), ('Name', 'a@b.com'))
        self.assertEqual(_split_from('a@b.com'), ('', 'a@b.com'))
        self.assertEqual(_split_from(''), ('', ''))

    @patch('apps.notifications.backends.requests.post')
    def test_send_message_builds_payload(self, mock_post):
        mock_post.return_value.status_code = 201
        backend = BrevoEmailBackend(fail_silently=False)

        email = EmailMultiAlternatives(
            subject='Test sujet',
            body='Contenu texte',
            from_email='DecisioBI <no-reply@decisiobi.local>',
            to=['user@example.com'],
        )
        email.attach_alternative('<h1>HTML</h1>', 'text/html')
        email.attach('file.pdf', b'%PDF-1.4 test', 'application/pdf')

        sent = backend.send_messages([email])

        self.assertEqual(sent, 1)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs['json']
        self.assertEqual(payload['sender'], {'name': 'DecisioBI', 'email': 'no-reply@decisiobi.local'})
        self.assertEqual(payload['to'], [{'email': 'user@example.com'}])
        self.assertEqual(payload['subject'], 'Test sujet')
        self.assertEqual(payload['htmlContent'], '<h1>HTML</h1>')
        self.assertEqual(len(payload['attachment']), 1)
        self.assertEqual(payload['attachment'][0]['name'], 'file.pdf')
        self.assertEqual(payload['attachment'][0]['contentType'], 'application/pdf')
        self.assertNotIn('password', payload)

    @patch('apps.notifications.backends.requests.post')
    def test_send_message_raises_on_api_error(self, mock_post):
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = '{"code":"bad_request"}'
        backend = BrevoEmailBackend(fail_silently=False)

        email = EmailMultiAlternatives(
            subject='Test',
            body='Contenu',
            to=['user@example.com'],
        )

        with self.assertRaises(RuntimeError):
            backend.send_messages([email])

    def test_missing_api_key_returns_zero(self):
        backend = BrevoEmailBackend(fail_silently=True)
        email = EmailMultiAlternatives(subject='T', body='B', to=['user@example.com'])
        self.assertEqual(backend.send_messages([email]), 0)

    def test_missing_api_key_raises(self):
        backend = BrevoEmailBackend(fail_silently=False)
        email = EmailMultiAlternatives(subject='T', body='B', to=['user@example.com'])
        with self.assertRaises(RuntimeError):
            backend.send_messages([email])
