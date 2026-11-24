"""Exercise real PDF layout with stacked approaches and per-page totals."""
import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from flights.approach_choices import ALL_APPROACH_CHOICES

from pdf_output import pdf_generate_task as module
from pdf_output.tests.test_pdf_rendering_security import render_sample


MULTIPLE_APPROACHES = [('ILS', 2), ('LNAV/VNAV', 1), ('RNP AR', 1), ('CATIII', 1), ('LDA/GS', 2)]


def approach_sample(row_count=40, approaches=MULTIPLE_APPROACHES, captured=None, draw_pages=None):
    """Synthetic flights rendered without database, storage, or email access."""
    rows = []
    for index in range(row_count):
        entries = approaches(index) if callable(approaches) else approaches
        entries = [SimpleNamespace(approach_type=code, number=count) for code, count in entries]
        rows.append(SimpleNamespace(date=datetime.date(2026, 11, 24) - datetime.timedelta(days=index),
            aircraft_type='B737', registration=f'N{10000 + index}', route='SEA-ORD-MEM',
            duration=Decimal('1.2'), night=Decimal('0.3'), instrument=Decimal('0.2'),
            landings_day=1, landings_night=0, simulated_instrument=0, simulator=False,
            pilot_in_command=True, approach_set=SimpleNamespace(all=lambda entries=entries: entries),
            holding_set=SimpleNamespace(all=lambda: [])))
    build_pdf, table_wrapper, draw_table = module._build_pdf, module.PageWidthTable, module.Table.drawOn

    def capture(table):
        if captured is not None:
            captured.append(table)
        return table_wrapper(table)

    def draw(table, canvas, *args, **kwargs):
        if draw_pages is not None:
            draw_pages[id(table)] = canvas.getPageNumber()
        return draw_table(table, canvas, *args, **kwargs)

    def build(user):
        with patch.object(module.Flight.objects, 'filter') as flights, \
             patch.object(module, 'PageWidthTable', side_effect=capture), \
             patch.object(module.Table, 'drawOn', autospec=True, side_effect=draw):
            flights.return_value.order_by.return_value = rows
            return build_pdf(user)

    with patch('pdf_output.tests.test_pdf_rendering_security._build_pdf', side_effect=build):
        return render_sample('Sample', 'Pilot')


def logbooks(tables):
    return [table for table in tables if table._cellvalues[0][:2] == ['Date', 'Type']]


class ApproachPaginationTests(SimpleTestCase):
    def test_every_supported_type_and_legacy_type_fits_without_losing_entries(self):
        entries = [(code, 1) for code, _ in ALL_APPROACH_CHOICES if code]
        tables, draw_pages = [], {}
        approach_sample(1, approaches=entries, captured=tables, draw_pages=draw_pages)
        table = logbooks(tables)[0]
        paragraph = table._cellvalues[1][10][0]
        self.assertEqual(paragraph.text.count('<br/>'), len(entries) - 1)
        for code, count in entries:
            self.assertIn(f'{code} × {count}', paragraph.getPlainText())
        footer = next(t for t in tables if t._cellvalues[0][0] == 'Current page')
        self.assertEqual(draw_pages[id(table)], draw_pages[id(footer)])

    def test_multiple_types_are_stacked_without_expanding_the_column(self):
        tables, simple_tables = [], []
        result = approach_sample(1, captured=tables)
        approach_sample(1, approaches=[('ILS', 2)], captured=simple_tables)
        table, simple = logbooks(tables)[0], logbooks(simple_tables)[0]
        self.assertTrue(result.startswith(b'%PDF-'))
        self.assertEqual(table._colWidths[10], 100)
        self.assertEqual(table._colWidths, simple._colWidths)
        paragraph = table._cellvalues[1][10][0]
        self.assertEqual(paragraph.text.count('<br/>'), len(MULTIPLE_APPROACHES) - 1)
        for code, count in MULTIPLE_APPROACHES:
            self.assertIn(f'{code} × {count}', paragraph.getPlainText())
        self.assertGreater(table._rowHeights[1], simple._rowHeights[1])

    def test_pagination_uses_row_height_and_keeps_totals_on_the_same_pages(self):
        tables, simple_tables, draw_pages = [], [], {}
        approach_sample(captured=tables, draw_pages=draw_pages)
        approach_sample(approaches=[], captured=simple_tables)
        pages = logbooks(tables)
        self.assertGreater(len(pages), len(logbooks(simple_tables)))
        self.assertGreater(max(len(t._cellvalues) - 1 for t in logbooks(simple_tables)), 17)
        rows = [row for table in pages for row in table._cellvalues[1:]]
        self.assertEqual([row[2] for row in rows], [f'N{10000 + i}' for i in range(40)])
        footers = [t for t in tables if t._cellvalues[0][0] == 'Current page']
        self.assertEqual(len(footers), len(pages))
        running = Decimal('0')
        for index, (table, footer) in enumerate(zip(pages, footers)):
            count = len(table._cellvalues) - 1
            self.assertEqual(draw_pages[id(table)], draw_pages[id(footer)])
            self.assertEqual(footer._colWidths, table._colWidths)
            current = Decimal('1.2') * count
            self.assertEqual(Decimal(footer._cellvalues[0][4]), current)
            self.assertEqual(int(footer._cellvalues[0][12]), count)
            if index:
                self.assertEqual(footer._cellvalues[1][0], 'Amount Forwarded')
                self.assertEqual(Decimal(footer._cellvalues[1][4]), running)
            running += current
            self.assertEqual(Decimal(footer._cellvalues[-1][4]), running)
        self.assertEqual(running, Decimal('48.0'))
        self.assertEqual(len({draw_pages[id(table)] for table in pages}), len(pages))

    def test_approach_text_is_escaped_before_becoming_paragraph_markup(self):
        tables = []
        approach_sample(1, approaches=[('<b>ILS</b>', 2)], captured=tables)
        paragraph = logbooks(tables)[0]._cellvalues[1][10][0]
        self.assertEqual(paragraph.getPlainText(), '<b>ILS</b> × 2')
        self.assertIn('&lt;b&gt;', paragraph.text)
