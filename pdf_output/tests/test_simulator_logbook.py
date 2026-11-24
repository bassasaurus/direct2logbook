"""Render mixed aircraft and device sessions; assert the printed hour columns."""
import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from pdf_output import pdf_generate_task as module
from pdf_output.tests.test_pdf_rendering_security import render_sample


def mixed_session_pdf(captured=None):
    rows = []
    for kind, hours in [('', '2.0'), ('Legacy Sim', '1.0'), ('FFS', '3.0'), ('FTD', '1.5'), ('ATD', '0.5')]:
        rows.append(SimpleNamespace(date=datetime.date(2026, 11, 20), aircraft_type='B737',
            registration='N737' if not kind or kind == 'Legacy Sim' else None,
            device_id='' if kind == 'Legacy Sim' else (kind + '-12' if kind else ''),
            route='IAH-LAX' if not kind else '', duration=Decimal(hours),
            night=Decimal('0.5'), instrument=Decimal('0.2'), landings_day=1, landings_night=1,
            simulated_instrument=Decimal('0.3'), simulator=bool(kind), pilot_in_command=True,
            second_in_command=False, dual=True, solo=False, instructor=False, cross_country=not bool(kind),
            approach_set=SimpleNamespace(all=lambda: []), holding_set=SimpleNamespace(all=lambda: [])))
    build = module._build_pdf
    table_wrapper = module.PageWidthTable
    def capture(table):
        if captured is not None:
            captured.append(table)
        return table_wrapper(table)
    def render(user):
        with patch.object(module.Flight.objects, 'filter') as flights, patch.object(module, 'PageWidthTable', side_effect=capture):
            flights.return_value.order_by.return_value = rows
            return build(user)
    with patch('pdf_output.tests.test_pdf_rendering_security._build_pdf', side_effect=render):
        return render_sample('Sample', 'Pilot')


class SimulatorLogbookPDFTests(SimpleTestCase):
    def test_aircraft_and_device_hours_are_printed_in_separate_columns(self):
        tables = []
        result = mixed_session_pdf(tables)
        self.assertTrue(result.startswith(b'%PDF-'))
        table = next(t for t in tables if t._cellvalues[0][:2] == ['Date', 'Type'])
        aircraft, *devices = table._cellvalues[1:]
        self.assertEqual(aircraft[4], '2.0')
        self.assertEqual(aircraft[5], '2.0')
        self.assertEqual(aircraft[18], '0.0')
        self.assertEqual([row[2] for row in devices], ['N737', 'FFS-12', 'FTD-12', 'ATD-12'])
        self.assertEqual([row[18] for row in devices], ['1.0', '3.0', '1.5', '0.5'])
        for row in devices:
            for index in (4, 5, 6, 7, 8, 9, 14, 15, 16, 17):
                self.assertEqual(row[index], '0.0', (index, row))
            self.assertEqual(row[12:14], ['0', '0'])
        footer = next(t for t in tables if t._cellvalues[0][0] == 'Current page')
        self.assertEqual(footer._cellvalues[0][4], '2.0')
        self.assertEqual(footer._cellvalues[0][18], '6.0')
