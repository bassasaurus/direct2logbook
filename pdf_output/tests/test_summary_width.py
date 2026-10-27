from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
import datetime

from django.test import SimpleTestCase
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib.pagesizes import landscape, letter

from pdf_output.pdf_generate_task import PageWidthTable
from pdf_output.tests.test_pdf_rendering_security import render_sample


def summary_fixture():
    return SimpleNamespace(total='Airplane Single Engine Land', aircraft_type='C172', total_time=12345.6,
        pilot_in_command=12345.6, second_in_command=1234.5, cross_country=12345.6,
        instructor=1234.5, dual=123.4, solo=123.4, instrument=123.4, night=1234.5,
        simulated_instrument=123.4, simulator=12.3, landings_day=12345, landings_night=1234,
        last_flown=datetime.date(2026, 10, 27), last_30=123.4, last_60=234.5,
        last_90=345.6, last_180=456.7, last_yr=789.0, last_2yr=1234.5, ytd=678.9)


def populated_sample():
    fixture = summary_fixture()

    class SummaryRows(list):
        def get(self, **kwargs):
            return fixture

    from pdf_output import pdf_generate_task as module
    # render_sample installs empty query mocks; replace those only when building.
    original_build = module._build_pdf

    def build(user):
        with patch.object(module.Total.objects, 'filter', return_value=SummaryRows([fixture])), \
             patch.object(module.Stat.objects, 'filter', return_value=[fixture]):
            return original_build(user)

    with patch('pdf_output.tests.test_pdf_rendering_security._build_pdf', side_effect=build):
        return render_sample('Alex', 'Pilot')


class SummaryWidthTests(SimpleTestCase):
    def setUp(self):
        self.canvas = Canvas(BytesIO())

    def test_wide_table_keeps_every_column_in_one_row_and_scales_to_frame(self):
        row = ['Airplane Single Engine Land'] + ['12345.6'] * 22
        table = Table([row], colWidths=[80]*23)
        fitted = PageWidthTable(table)
        width, height = fitted.wrapOn(self.canvas, 720, 500)
        self.assertAlmostEqual(width, 720)
        self.assertAlmostEqual(fitted.scale, 720/(80*23))
        self.assertEqual(table._cellvalues, [row])
        self.assertGreater(height, 0)

    def test_narrow_table_is_not_enlarged(self):
        fitted = PageWidthTable(Table([['Type', 'Time']], colWidths=[50, 50]))
        self.assertEqual(fitted.wrapOn(self.canvas, 720, 500)[0], 100)
        self.assertEqual(fitted.scale, 1)

    def test_tall_scaled_table_splits_with_repeated_headers_without_losing_rows(self):
        rows = [['Header']*23] + [[f'row-{i}']*23 for i in range(100)]
        fitted = PageWidthTable(Table(rows, colWidths=[80]*23, repeatRows=1))
        fitted.wrapOn(self.canvas, 720, 200)
        parts = fitted.splitOn(self.canvas, 720, 200)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0].table._cellvalues[0], rows[0])
        self.assertEqual(parts[1].table._cellvalues[0], rows[0])
        self.assertEqual(parts[0].table._cellvalues[1:] + parts[1].table._cellvalues[1:], rows[1:])
        self.assertLessEqual(parts[0].wrapOn(self.canvas, 720, 200)[1], 200)
        buffer = BytesIO()
        SimpleDocTemplate(buffer, pagesize=landscape(letter)).build([fitted])
        self.assertTrue(buffer.getvalue().startswith(b'%PDF-'))

    def test_populated_logbook_builds_with_single_table_summaries(self):
        result = populated_sample()
        self.assertTrue(result.startswith(b'%PDF-'))
        self.assertIn(b'%%EOF', result[-30:])
