from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from signature.models import Signature


@override_settings(SECURE_SSL_REDIRECT=False)
class PDFOutputViewsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pdf_testuser", password="testpass", email="pdf@example.com"
        )
        self.client.force_login(self.user)
        self.signature = Signature.objects.create(
            user=self.user,
            signature=(
                "data:image/png;base64,"
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR42mP8/x8AAwMCAO+aP1sAAAAASUVORK5CYII="
            ),
        )

    def test_signature_create_view_get(self):
        response = self.client.get(reverse("signature_create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "signature/signature_form.html")
        self.assertIn("signature", response.context["form"].fields)

    def test_signature_delete_view_get(self):
        response = self.client.get(
            reverse("signature_delete", args=[self.signature.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "signature/signature_confirm_delete.html")
        self.assertContains(response, "Delete")

    @patch("pdf_output.views.pdf_generate.delay")
    def test_pdf_view_get(self, mock_pdf_generate):
        response = self.client.get(reverse("pdf", args=[self.user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check your email")
        mock_pdf_generate.assert_called_once_with(self.user.pk)
