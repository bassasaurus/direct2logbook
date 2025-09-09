from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group
from pdf_output.models import Signature
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile


class PDFOutputViewsTest(TestCase):
    @patch("profile.signal_profile.stripe.Subscription.create", return_value=type("Sub", (), {"id": "sub_test", "trial_end": 0})())
    @patch("django.core.files.storage.default_storage.save", return_value="mocked/test-signature.png")
    def setUp(self, mock_save, mock_subscription_create):
        Group.objects.get_or_create(name='clients')
        self.user = User.objects.create_user(
            username='testuser', password='testpass', email='test@example.com')
        self.client.login(username='testuser', password='testpass')
        self.signature = Signature.objects.create(
            user=self.user,
            signature=SimpleUploadedFile(
                "test-signature.png", b"dummy image content", content_type="image/png")
        )

    def test_signature_create_view_get(self):
        response = self.client.get(reverse("signature_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draw a new signature")

    def test_signature_update_view_get(self):
        response = self.client.get(
            reverse("signature_update", args=[self.signature.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Update")

    def test_signature_delete_view_get(self):
        response = self.client.get(
            reverse("signature_delete", args=[self.signature.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete")

    @patch("pdf_output.views.pdf_generate.delay")
    def test_pdf_view_get(self, mock_pdf_generate):
        response = self.client.get(reverse("pdf", args=[self.user.id]))
        self.assertEqual(response.status_code, 200)
        mock_pdf_generate.assert_called_once_with(self.user.id)
