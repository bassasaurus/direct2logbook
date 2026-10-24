import base64
from io import BytesIO

from django.test import SimpleTestCase
from PIL import Image

from signature.forms import SignatureForm


class SignatureFormTest(SimpleTestCase):
    def test_signature_form_valid_data(self):
        image = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(image, format="PNG")
        signature = "data:image/png;base64," + base64.b64encode(
            image.getvalue()
        ).decode("ascii")

        form = SignatureForm(data={"signature": signature})

        self.assertTrue(form.is_valid(), form.errors)

    def test_signature_form_requires_signature(self):
        form = SignatureForm(data={"signature": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("signature", form.errors)
