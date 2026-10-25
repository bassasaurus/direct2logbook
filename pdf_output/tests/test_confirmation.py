import re
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from kombu.exceptions import OperationalError
from pdf_output.models import PDFRequest


@override_settings(SECURE_SSL_REDIRECT=False)
class PDFConfirmationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='pdf_request_owner', email='pdf-owner@example.com',
        )
        self.other = get_user_model().objects.create_user(
            username='pdf_request_other', email='pdf-other@example.com',
        )
        profile = self.user.profile
        profile.customer_id = 'cus_owner'
        profile.subscription_id = 'sub_owner'
        profile.end_date = date.today() + timedelta(days=14)
        profile.active = True
        profile.monthly = True
        profile.save()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.url = reverse('pdf', args=[self.user.pk])
        patcher = patch('pdf_output.views.pdf_generate.apply_async')
        self.publish = patcher.start()
        self.addCleanup(patcher.stop)
        self.publish.return_value = SimpleNamespace(id='confirmed-pdf-task')

    def csrf_token(self):
        with patch('profile.views.stripe.checkout.Session.create',
                   return_value=SimpleNamespace(id='cs_test')):
            response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode())
        self.assertIsNotNone(match)
        return match.group(1)

    def test_successful_publish_returns_accepted_with_task_id(self):
        response = self.client.post(self.url, {'csrfmiddlewaretoken': self.csrf_token()})

        self.assertEqual(response.status_code, 202)
        job = PDFRequest.objects.get()
        self.assertEqual(response.json(), {
            'status': 'queued', 'task_id': job.task_id,
            'email': self.user.email,
            'status_url': reverse('pdf_status', args=[job.pk]),
        })
        self.publish.assert_called_once_with(
            args=(self.user.pk,), kwargs={'request_id': str(PDFRequest.objects.get().pk)},
            task_id=PDFRequest.objects.get().task_id, retry=False,
        )

    def test_broker_failure_does_not_confirm_submission(self):
        token = self.csrf_token()
        self.publish.side_effect = OperationalError('Broker unavailable')
        with self.assertLogs('django.pdf_output', level='ERROR'):
            response = self.client.post(self.url, {'csrfmiddlewaretoken': token})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'unconfirmed')
        self.assertNotIn('task_id', response.json())
        self.assertIn('may still have been queued', response.json()['message'])
        self.publish.assert_called_once_with(
            args=(self.user.pk,), kwargs={'request_id': str(PDFRequest.objects.get().pk)},
            task_id=PDFRequest.objects.get().task_id, retry=False,
        )

    def test_get_does_not_enqueue(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.publish.assert_not_called()

    def test_anonymous_request_does_not_enqueue(self):
        response = Client().post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)
        self.publish.assert_not_called()

    def test_missing_csrf_token_does_not_enqueue(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.publish.assert_not_called()

    def test_invalid_csrf_token_does_not_enqueue(self):
        self.csrf_token()
        response = self.client.post(self.url, {'csrfmiddlewaretoken': 'invalid'})

        self.assertEqual(response.status_code, 403)
        self.publish.assert_not_called()

    def test_url_and_body_cannot_select_another_users_export(self):
        response = self.client.post(reverse('pdf', args=[self.other.pk]), {
            'csrfmiddlewaretoken': self.csrf_token(), 'user_id': self.other.pk,
        })

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['email'], self.user.email)
        self.publish.assert_called_once_with(
            args=(self.user.pk,), kwargs={'request_id': str(PDFRequest.objects.get().pk)},
            task_id=PDFRequest.objects.get().task_id, retry=False,
        )
