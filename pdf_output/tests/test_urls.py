from django.test import SimpleTestCase
from django.urls import resolve, reverse

from pdf_output.views import PDFView
from signature.views import SignatureCreateView, SignatureDeleteView


class TestPDFOutputURLs(SimpleTestCase):
    def test_pdf_view_url_resolves(self):
        url = reverse("pdf", kwargs={"user_id": 1})
        self.assertEqual(resolve(url).func, PDFView)

    def test_signature_create_url_resolves(self):
        url = reverse("signature_create")
        self.assertEqual(resolve(url).func.view_class, SignatureCreateView)

    def test_signature_delete_url_resolves(self):
        url = reverse("signature_delete", kwargs={"pk": 1})
        self.assertEqual(resolve(url).func.view_class, SignatureDeleteView)
