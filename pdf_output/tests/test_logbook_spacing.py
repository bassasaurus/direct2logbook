import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from reportlab.pdfbase.pdfmetrics import stringWidth
from pdf_output import pdf_generate_task as module
from pdf_output.tests.test_pdf_rendering_security import render_sample


def long_route_sample(captured=None):
    rows = [SimpleNamespace(date=datetime.date(2026, 10, 27), aircraft_type='C172',
        registration='N1234', route='KJFK-KBOS-KORD-KDEN-KLAX-KSFO-KSEA-KPDX-KSLC',
        duration=1234.5, night=0, instrument=0, landings_day=1, landings_night=0,
        simulated_instrument=0, simulator=0, pilot_in_command=True,
        approach_set=SimpleNamespace(all=lambda: []), holding_set=SimpleNamespace(all=lambda: []))
        for _ in range(20)]
    build_pdf = module._build_pdf
    wrapper = module.PageWidthTable

    def capture(table):
        if captured is not None:
            captured.append(table)
        return wrapper(table)

    def build(user):
        with patch.object(module.Flight.objects, 'filter') as flights, \
             patch.object(module, 'PageWidthTable', side_effect=capture):
            flights.return_value.order_by.return_value = rows
            return build_pdf(user)

    with patch('pdf_output.tests.test_pdf_rendering_security._build_pdf', side_effect=build):
        return render_sample('Alex', 'Pilot')


class LogbookSpacingTests(SimpleTestCase):
    def test_long_route_keeps_date_and_type_text_inside_their_columns(self):
        tables = []
        result = long_route_sample(tables)
        self.assertTrue(result.startswith(b'%PDF-'))
        logbooks = [t for t in tables if t._cellvalues[0][:2] == ['Date', 'Type']]
        self.assertEqual(len(logbooks), 2)  # Existing 17-row page grouping remains.
        for table in logbooks:
            for index, text in [(0, '10/27/2026'), (1, 'C172'), (2, 'N1234'),
                                (3, 'KJFK-KBOS-KORD-KDEN-KLAX-KSFO-KSEA-KPDX-KSLC')]:
                style = table._cellStyles[1][index]
                required = stringWidth(text, style.fontname, style.fontsize) + style.leftPadding + style.rightPadding
                self.assertGreaterEqual(table._colWidths[index] + 0.001, required)
            self.assertEqual(table._cellStyles[1][0].rightPadding, 10)
            self.assertEqual(table._cellStyles[1][1].leftPadding, 8)
            self.assertEqual(table._cellStyles[1][2].rightPadding, 10)
            self.assertEqual(table._cellStyles[1][3].leftPadding, 8)
        footers = [t for t in tables if t._cellvalues[0][0] == 'Current page']
        self.assertEqual(len(footers), 2)
        for footer in footers:
            self.assertEqual(footer._colWidths, logbooks[0]._colWidths)
        self.assertEqual(logbooks[0]._colWidths, logbooks[1]._colWidths)
