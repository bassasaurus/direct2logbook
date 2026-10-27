from contextlib import ExitStack
import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from reportlab.platypus import Paragraph

from pdf_output.pdf_generate_task import _build_pdf


def render_sample(first_name, last_name, capture=None, signature=None):
    """Real PDF renderer, synthetic rows, no database, email or storage access."""
    user = SimpleNamespace(pk=123, first_name=first_name, last_name=last_name)
    with ExitStack() as stack:
        for model in ('Total', 'Stat', 'Regs', 'Power', 'Weight', 'Endorsement'):
            stack.enter_context(patch('pdf_output.pdf_generate_task.' + model + '.objects.filter', return_value=[]))
        signatures = stack.enter_context(patch('pdf_output.pdf_generate_task.Signature.objects.filter'))
        signatures.return_value.exists.return_value = signature is not None
        stack.enter_context(patch('pdf_output.pdf_generate_task.Signature.objects.get',
                                  return_value=SimpleNamespace(signature=signature)))
        flights = stack.enter_context(patch('pdf_output.pdf_generate_task.Flight.objects.filter'))
        rows = []
        for day in range(1, 4):
            rows.append(SimpleNamespace(date=datetime.date(2026, 10, day), aircraft_type='C172',
                registration='N1234', route='KJFK-KBOS', duration=1.2,
                night=0, instrument=0, landings_day=1, landings_night=0,
                simulated_instrument=0, simulator=0, pilot_in_command=True,
                approach_set=SimpleNamespace(all=lambda: []), holding_set=SimpleNamespace(all=lambda: [])))
        flights.return_value.order_by.return_value = rows
        if capture is not None:
            stack.enter_context(patch('pdf_output.pdf_generate_task.Paragraph', side_effect=capture))
        return _build_pdf(user)


class PDFRenderingSecurityTests(SimpleTestCase):
    def test_user_name_markup_is_rendered_as_literal_text(self):
        first = '<b>Alex</b>'
        last = "O'Neil & Co"
        paragraphs = []

        def capture(text, *args, **kwargs):
            paragraph = Paragraph(text, *args, **kwargs)
            paragraphs.append(paragraph)
            return paragraph

        result = render_sample(first, last, capture=capture)
        self.assertTrue(result.startswith(b'%PDF-'))
        self.assertEqual(paragraphs[0].getPlainText(), f'Logbook for {first} {last}')
        self.assertNotIn('<b>Alex</b>', paragraphs[0].text)

    def test_malformed_tags_and_entities_do_not_break_pdf_generation(self):
        for first, last in [('A <font color="red">', 'B &unknown;'), ('<&', '> &amp;')]:
            with self.subTest(first=first):
                result = render_sample(first, last)
                self.assertTrue(result.startswith(b'%PDF-'))
                self.assertIn(b'%%EOF', result[-30:])

    def test_normal_names_and_logbook_rows_still_build(self):
        result = render_sample('Alex', 'Pilot')
        self.assertTrue(result.startswith(b'%PDF-'))
        self.assertGreater(len(result), 2000)

    def test_png_signature_is_embedded_by_the_upgraded_renderer(self):
        import base64
        from io import BytesIO
        from PIL import Image
        from reportlab.pdfgen.canvas import Canvas

        image = BytesIO()
        Image.new('RGB', (10, 10), color='white').save(image, format='PNG')
        signature = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode('ascii')
        draw_image = Canvas.drawImage
        calls = []

        def capture(canvas, *args, **kwargs):
            calls.append(args)
            return draw_image(canvas, *args, **kwargs)

        with patch.object(Canvas, 'drawImage', autospec=True, side_effect=capture):
            result = render_sample('Alex', 'Pilot', signature=signature)
        self.assertTrue(result.startswith(b'%PDF-'))
        self.assertGreaterEqual(len(calls), 2)
