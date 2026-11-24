from decimal import Decimal

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from home.iacra import COLUMNS, iacra_tables
from home.tests.test_cross_country_totals import FirstTableParser


class IACRASectionThreeTests(SimpleTestCase):
    def test_faa_categories_and_nonapplicable_cells(self):
        rows = iacra_tables({})['iacra_rows']
        self.assertEqual([row['label'] for row in rows], [
            'Airplanes', 'Rotorcraft', 'Powered Lift', 'Gliders',
            'Lighter-Than-Air', 'FFS', 'FTD', 'ATD'])
        expected = [set(), set(), set(), {6, 7, 8, 10, 11, 12, 13, 14, 15},
                    set(), {2, 3, 4, 5, 6, 7, 8},
                    {2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15},
                    {2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15}]
        for row, shaded in zip(rows, expected):
            self.assertEqual(len(row['cells']), 16)
            self.assertEqual({i for i, cell in enumerate(row['cells']) if cell['shaded']}, shaded)

    def test_all_supported_metrics_keep_faa_column_order(self):
        keys = ['airplane_total', 'airplane_dual', 'airplane_solo', 'airplane_pic',
                'airplane_sic', 'airplane_xc_dual', 'airplane_xc_solo',
                'airplane_xc_pic', 'airplane_xc_sic', 'airplane_ifr',
                'airplane_night_dual', 'airplane_ldg_night', 'airplane_night_pic',
                'airplane_night_sic', 'airplane_night_ldg_pic', 'airplane_night_ldg_sic']
        context = {key: Decimal(i) for i, key in enumerate(keys) if key}
        row = iacra_tables(context)['iacra_rows'][0]
        self.assertEqual([cell['label'] for cell in row['cells']], list(COLUMNS))
        self.assertEqual([cell['value'] for cell in row['cells']],
                         [Decimal(i) if key else None for i, key in enumerate(keys)])

    def test_device_classification_is_not_guessed_from_legacy_sim_time(self):
        result = iacra_tables({'sim_total': Decimal('100.0')})
        for row in result['iacra_rows'][5:]:
            self.assertTrue(all(cell['value'] is None for cell in row['cells']))

    def test_class_totals_preserve_pic_sic_and_instruction(self):
        context = {prefix + '_' + role: Decimal(i * 3 + j)
                   for i, prefix in enumerate(('asel', 'amel', 'ases', 'ames'))
                   for j, role in enumerate(('pic', 'sic', 'dual'))}
        classes = iacra_tables(context)['iacra_airplane_classes']
        self.assertEqual([item['label'] for item in classes], ['SEL', 'MEL', 'SES', 'MES'])
        for i, item in enumerate(classes):
            self.assertEqual([item['pic'], item['sic'], item['instruction']],
                             [Decimal(i * 3 + j) for j in range(3)])

    def test_render_distinguishes_zero_unavailable_and_shaded(self):
        html = render_to_string('home/iacra.html', iacra_tables({'airplane_total': Decimal('0')}))
        parser = FirstTableParser()
        parser.feed(html)
        self.assertEqual(parser.rows[2][1]['text'].strip(), '0.0')
        self.assertEqual(parser.rows[2][12]['text'].strip(), '—')
        self.assertEqual(parser.rows[5][7]['attrs']['class'], 'iacra-shaded')
        self.assertIn('role="region"', html)
        self.assertIn('tabindex="0"', html)
        self.assertIn('js/iacra.js', html)

    def test_headers_cover_seventeen_columns_without_overlap(self):
        parser = FirstTableParser()
        parser.feed(render_to_string('home/iacra.html', iacra_tables({})))
        occupied = set()
        for r, row in enumerate(parser.rows):
            col = 0
            for cell in row:
                while (r, col) in occupied:
                    col += 1
                for rr in range(r, r + int(cell['attrs'].get('rowspan', 1))):
                    for cc in range(col, col + int(cell['attrs'].get('colspan', 1))):
                        self.assertNotIn((rr, cc), occupied)
                        occupied.add((rr, cc))
                col += int(cell['attrs'].get('colspan', 1))
        self.assertEqual(occupied, {(r, c) for r in range(10) for c in range(17)})
