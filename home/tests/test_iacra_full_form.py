from copy import deepcopy
from decimal import Decimal
from django.test import SimpleTestCase
from django.template.loader import render_to_string
from home.pilot_time import report_context
from home.tests.test_cross_country_totals import FirstTableParser


class FullIACRAFormTests(SimpleTestCase):
    def report(self):
        return dict(rows=[], classes=[], launches=[], devices=[], note='Recorded values only.', night_crew={'A': 0, 'R': 0})

    def test_empty_account_retains_all_form_categories_classes_devices_and_launches(self):
        context = report_context(self.report())
        self.assertEqual([row['code'] for row in context['iacra_rows']], ['A', 'R', 'PL', 'GL', 'LTA', 'FFS', 'FTD', 'ATD'])
        self.assertEqual([row['label'] for row in context['iacra_airplane_classes']], ['SEL', 'MEL', 'SES', 'MES'])
        self.assertEqual(len(context['iacra_device_classes']), 3)
        self.assertEqual([row['code'] for row in context['iacra_launches']], ['GL', 'LTA'])
        for row in context['iacra_rows']:
            for cell in row['cells']:
                self.assertEqual(cell['value'], None if cell['shaded'] else 0)
        html = render_to_string('home/iacra.html', context)
        parser = FirstTableParser()
        parser.feed(html)
        self.assertEqual(len(parser.rows), 10)
        self.assertTrue(all(len(row) == 17 for row in parser.rows[2:]))
        for title in ('Class Totals', 'Helicopter', 'Gyroplane', 'Balloon', 'Airship', 'Ground Launches', 'Powered Launches'):
            self.assertIn(title, html)

    def test_form_completion_preserves_recorded_and_unavailable_values_without_mutating_report(self):
        report = self.report()
        sample = report_context(report)['iacra_rows'][0]
        sample['cells'][0]['value'] = Decimal('12.3')
        sample['cells'][5]['value'] = None
        report['rows'] = [sample]
        report['classes'] = [dict(code='AIRSHIP', total=Decimal('3.4'))]
        before = deepcopy(report)
        context = report_context(report)
        self.assertEqual(context['iacra_rows'][0]['cells'][0]['value'], Decimal('12.3'))
        self.assertIsNone(context['iacra_rows'][0]['cells'][5]['value'])
        self.assertEqual(context['iacra_airship_total'], Decimal('3.4'))
        self.assertEqual(report, before)
        self.assertEqual(len(report['rows']), 1)
