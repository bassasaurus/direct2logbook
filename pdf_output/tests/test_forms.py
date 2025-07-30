from django.test import TestCase
from pdf_output.forms import SignatureForm
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image


class SignatureFormTest(TestCase):
    def test_signature_form_valid_data(self):
        # Create a simple valid image using Pillow
        image = BytesIO()
        img = Image.new("RGB", (1, 1), color="white")
        img.save(image, format="PNG")
        image.seek(0)

        file_data = SimpleUploadedFile(
            "signature.png",
            image.read(),
            content_type="image/png"
        )

        form = SignatureForm(data={}, files={'signature': file_data})
        print("Form errors:", form.errors)
        self.assertTrue(form.is_valid())
