from django.test import SimpleTestCase

from csv_app.adapters import foreflight_approaches
from csv_app.mapping import read_source, normalize_mapping
from csv_app.rows import stage_rows
from csv_app.tests.test_adapters import source
from csv_app.validation import CSVValidationError, parse_csv


def structured_file(approaches):
    return source(['ForeFlight Logbook Import'], [[], ['Aircraft Table'],
        ['AircraftID', 'EquipmentType', 'TypeCode'], ['N12345', 'aircraft', 'C172'],
        [], ['Flights Table'], ['Date', 'AircraftID', 'From', 'To', 'TotalTime', 'PIC',
        'Holds', 'PilotComments', *[f'Approach{i+1}' for i in range(len(approaches))]],
        ['2026-10-20', 'N12345', 'IAH', 'IAH', '1.2', '1.2', '2', 'Training', *approaches]])


class ForeFlightApproachTests(SimpleTestCase):
    def test_combine_types_counts_and_preserve_source_details(self):
        table = read_source(structured_file(['2;ILS;12L;KIAH;Broke out at 350 AGL',
            '1;RNAV (GPS);18;KAXH;;Circle', '1;ILS CAT III;;;;']))
        mapping = {name: {'column': index} for name, index in table.suggestions().items()}
        parsed, _ = parse_csv(normalize_mapping(table, mapping))
        record = parsed[0]
        self.assertEqual(record['approaches'], 4)
        self.assertEqual(record['approach_details'], [
            {'approach_type': 'ILS', 'number': 2}, {'approach_type': 'RNAV', 'number': 1},
            {'approach_type': 'CATIII', 'number': 1}])
        self.assertTrue(record['hold'])
        self.assertIn('Training | Approach1: 2;ILS;12L;KIAH;Broke out at 350 AGL', record['remarks'])
        self.assertIn('Approach2: 1;RNAV (GPS);18;KAXH;;Circle', record['remarks'])
        consumed = table.consumed_columns(table.suggestions().values())
        for name in ('Approach1', 'Approach2', 'Approach3', 'PilotComments'):
            self.assertIn(str(table.headers.index(name)), consumed)

    def test_repeated_types_are_added_and_empty_cells_do_not_create_approaches(self):
        self.assertEqual(foreflight_approaches([('Approach1','1;ILS'), ('Approach2','2;ILS'),
            ('Approach3','')])[:2], ('3','ILS: 3'))
        self.assertEqual(foreflight_approaches([('Approach1','')]), ('0','',[]))
        self.assertEqual(foreflight_approaches([('Approach1','1;ASR/SRA')])[:2], ('1','ASR: 1'))

    def test_ambiguous_unknown_and_malformed_values_need_row_correction(self):
        for value in ('1;ILS OR LOC RWY 18L;18L;KAUS;;Circle', '1;GCA', '1;RNAV (RNP)',
                      '1;;18;KAXH', 'ILS', '-1;ILS', '0;ILS', '1.5;ILS',
                      '1;ILS;;;;;unexpected'):
            with self.subTest(value=value):
                count, types, notes = foreflight_approaches([('Approach1',value)])
                self.assertEqual(count, '')
                self.assertIn(value, notes[0])
                table = read_source(structured_file([value]))
                content = normalize_mapping(table, {name:{'column':index} for name,index in table.suggestions().items()})
                with self.assertRaisesRegex(CSVValidationError, 'Approach types:'):
                    parse_csv(content)
                # The editable derived field is enough to resolve the error;
                # no permanent source error traps the user after correction.
                data = stage_rows(content)
                data['rows'][0]['values'][data['header'].index('approach types')] = 'LOC: 1'
                parsed, _ = parse_csv(normalize_corrected(data))
                self.assertEqual(parsed[0]['approach_details'], [{'approach_type':'LOC','number':1}])
                self.assertIn(value, parsed[0]['remarks'])

    def test_duplicate_approach_headers_are_rejected(self):
        with self.assertRaisesRegex(CSVValidationError, 'Approach column names must be unique'):
            read_source(structured_file(['1;ILS', '1;VOR']).replace('Approach2','Approach1'))

    def test_invalid_type_does_not_hide_other_valid_approaches(self):
        count, types, notes = foreflight_approaches([('Approach1','2;ILS'), ('Approach2','1;GCA')])
        self.assertEqual(count, '')
        self.assertIn('ILS: 2', types)
        self.assertEqual(notes, ['Approach1: 2;ILS', 'Approach2: 1;GCA'])


def normalize_corrected(data):
    from csv_app.rows import included_content
    return included_content(data)
