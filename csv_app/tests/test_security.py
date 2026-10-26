from unittest.mock import patch
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from types import SimpleNamespace
import uuid


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='csv_security')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_all_csv_endpoints_require_login(self):
        for name in ('csv_download', 'csv_inspect', 'csv_upload'):
            self.assertEqual(Client().get(reverse(name)).status_code, 302)

    @patch('csv_app.views.queue_csv_import')
    def test_get_cannot_start_import(self, importer):
        self.assertEqual(self.client.get(reverse('csv_upload')).status_code, 405)
        importer.assert_not_called()

    @patch('csv_app.views.queue_csv_import')
    def test_post_requires_csrf(self, importer):
        self.assertEqual(self.client.post(reverse('csv_upload')).status_code, 403)
        importer.assert_not_called()

    @patch('csv_app.views.queue_csv_import')
    def test_authenticated_csrf_post_uses_current_user_and_batch_token(self, importer):
        page = self.client.get(reverse('csv_inspect'))
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)
        batch_id = uuid.uuid4()
        importer.return_value = (SimpleNamespace(pk=batch_id, row_count=1, completed=False, status='queued', error_message=''), False)
        response = self.client.post(reverse('csv_upload'), {'csrfmiddlewaretoken': token, 'batch_id': str(batch_id)})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(importer.call_args.args[0].pk, self.user.pk)
        self.assertEqual(importer.call_args.args[1], batch_id)
