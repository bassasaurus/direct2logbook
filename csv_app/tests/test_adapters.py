"""Native-shaped cases reconstructed from documented headers, not customer data.

Evidence: Coradine/logten-api; MyFlightbookWeb/.../Import/{LogTenPro,ForeFlight}.cs;
MyFlightbookWeb/Public/ImportTemplate.csv; NC Software Windows Style/Export docs;
AstroPhysX/flightline-tracker/app/services/logbook_service.py expected columns.
See RELIABILITY.md for source URLs and format limitations.
"""
import csv
import io
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from csv_app.adapters import full_route
from csv_app.mapping import read_source, normalize_mapping
from csv_app.forms import ColumnMappingForm
from csv_app.validation import CSVValidationError, parse_csv
from csv_app.models import CSVImportBatch
from csv_app.csv_import import confirm_csv_import
from csv_app.tests.test_mapping import choices
from csv_app.tests.record_fixtures import seed_records
from decimal import Decimal
from csv_app.tests.airport_fixtures import seed_airports
from flights.models import Flight, Aircraft, Total


def source(headers, records, delimiter=','):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter)
    writer.writerow(headers)
    writer.writerows(records)
    return output.getvalue()


LTP = ['flight_flightDate','aircraft_aircraftID','aircraftType_type','flight_from','flight_route','flight_to',
       'flight_totalTime','flight_pic','flight_sic','flight_crossCountry','flight_simulator','flight_type']
MFB = ['Date','Tail Number','Model','Total Flight Time','PIC','SIC','X-Country','IMC','FS Day Landings',
       'FS Night Landings','Ground Simulator','Route','Comments']
LP = ['DATE','AIRCRAFT MAKE & MODEL','AIRCRAFT IDENT','ROUTE OF FLIGHT','DURATION','PILOT IN COMMAND',
      'SECOND IN COMMAND','CROSS COUNTRY','NIGHT','INSTRUMENT','LANDINGS DAY','LANDINGS NIGHT','SIMULATOR','LEGS']


def ff_file(equipment='aircraft', aircraft_rows=None, flights=None):
    return source(['ForeFlight Logbook Import'], [[], ['Aircraft Table'],
       ['Text','Text','Text'], ['AircraftID','EquipmentType','TypeCode'],
       *(aircraft_rows if aircraft_rows is not None else [['N12345',equipment,'C172']]), [], ['Flights Table'],
       ['Date','Text','Text','Text','Text','Decimal','Decimal'],
       ['Date','AircraftID','From','To','Route','TotalTime','PIC'],
       *(flights if flights is not None else [['2026-11-20','N12345','KIAH','KCLL','','1.5','1.5']])])


class AdapterReaderTests(SimpleTestCase):
    def test_myflightbook_combines_from_to_and_requires_acknowledgement_of_source_ids(self):
        headers = ['Date','Tail Number','Model','From','To','Total Flight Time','PIC',
                   'Landings','FS Day Landings','FS Night Landings','Flight ID','Flight Properties']
        table = read_source(source(headers,[['11/20/2026','N12345','C172','KIAH','KIAH',
                                            '1.5','1.5','3','2','0','1','Informational summary']]))
        self.assertEqual(table.source_key,'myflightbook')
        selected = table.suggestions()
        self.assertEqual(table.records[0][selected['route']], 'KIAH-KIAH')
        self.assertEqual(table.headers[selected['day landing']], 'FS Day Landings')
        form = ColumnMappingForm(dict(choices(table),time_units='hours'),table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('ignore_unused',form.errors)
        reasons = {r['name']:r['unused_reason'] for r in form.source_columns()}
        self.assertIn('not a Direct2Logbook record ID',reasons['Flight ID'])
        self.assertIn('does not identify separate day/night',reasons['Landings'])
        self.assertIn('display summary',reasons['Flight Properties'])
        self.assertNotIn(headers.index('Flight ID'),selected.values())

    def test_myflightbook_sim_registration_is_only_removed_for_actual_device_time(self):
        headers = ['Date','Tail Number','Model','Total Flight Time','Ground Simulator']
        table = read_source(source(headers,[['2026-11-20','SIM','B737','0','2.0'],
                                            ['2026-11-21','N12345','C172','1.5',''],
                                            ['2026-11-22','SIM','C172','1.5','']]))
        index = table.suggestions()['registration']
        self.assertEqual([r[index] for r in table.records], ['', 'N12345', 'SIM'])
        form = ColumnMappingForm(dict(choices(table),time_units='hours',ignore_unused='on'),table=table)
        used = {r['name']:r['used'] for r in form.source_columns()}
        self.assertTrue(used['Tail Number'])

    def test_logten_selected_aircraft_fields_match_verified_api_names(self):
        headers = ['flight_flightDate','flight_selectedAircraftID','flight_selectedAircraftType',
            'flight_from','flight_to','flight_totalTime','flight_pic',
            'flight_scheduledDepartureTime','flight_takeoffTime','flight_landingTime',
            'flight_selectedCrewCommander','flight_holds','flight_selectedApproach1',
            'flight_outTime','flight_inTime']
        table = read_source(source(headers,[['2026-11-01','N12345','C172','KIAH','KCLL',
            '90','90','08:00','08:15','09:15','Someone Else','1','ILS','07:50','09:25']], '\t'))
        self.assertEqual(table.source_key,'logten')
        suggested = table.suggestions()
        self.assertEqual(table.headers[suggested['aircraft']], 'flight_selectedAircraftType')
        self.assertEqual(table.headers[suggested['registration']], 'flight_selectedAircraftID')
        self.assertNotIn('block out',suggested)
        self.assertNotIn('block in',suggested)
        self.assertNotIn('approaches',suggested)
        self.assertEqual(table.headers[suggested['pilot in command']], 'flight_pic')
        data = dict(choices(table),ignore_unused='on')
        form = ColumnMappingForm(data,table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('time_units',form.errors)
        data['time_units']='minutes'
        form = ColumnMappingForm(data,table=table)
        self.assertTrue(form.is_valid(),form.errors)
        parsed = parse_csv(normalize_mapping(table,form.cleaned_data['mapping'],'minutes'))[0][0]
        self.assertEqual(str(parsed['duration']),'1.5')

    def test_logten_conflicting_aircraft_aliases_require_explicit_mapping(self):
        table = read_source(source(['flight_flightDate','aircraft_aircraftID','flight_selectedAircraftID',
            'aircraftType_type','flight_selectedAircraftType','flight_totalTime'],
            [['2026-11-01','N12345','N54321','C172','PA28','1.5']]))
        self.assertNotIn('aircraft',table.suggestions())
        self.assertNotIn('registration',table.suggestions())

    def test_logbook_pro_readable_headings_preserve_roles_and_instrument_meanings(self):
        headers = ['Date','Aircraft Type','Aircraft Ident','Route','Duration','PIC','SIC',
            'Dual Received','Dual Given','Solo','Night','Cross Country','Actual Instrument',
            'Simulated Instrument','Flight Simulator','Day Takeoffs','Day Landings',
            'Night Takeoffs','Night Landings','Approaches','Remarks']
        table = read_source(source(headers,[['11/20/2026','C172','N12345','KIAH-KCLL',
            '1.5','1.5','','','1.5','','0.3','1.5','0.2','0.1','','1','1','0','0','1','Training']]))
        self.assertEqual(table.source_key, 'logbook-pro')
        matches = table.suggestions()
        for field, heading in {'registration':'Aircraft Ident','dual':'Dual Received',
                'instructor':'Dual Given','instrument':'Actual Instrument',
                'simulated instrument':'Simulated Instrument','day landing':'Day Landings',
                'night landing':'Night Landings'}.items():
            self.assertEqual(table.headers[matches[field]], heading)
        form = ColumnMappingForm(dict(choices(table),time_units='hours',ignore_unused='on'),table=table)
        self.assertTrue(form.is_valid(), form.errors)
        parsed = parse_csv(normalize_mapping(table,form.cleaned_data['mapping'],'hours'))[0][0]
        self.assertTrue(parsed['instructor'])
        self.assertFalse(parsed['dual'])
        self.assertEqual(str(parsed['instrument']), '0.2')
        self.assertEqual(str(parsed['simulated_instrument']), '0.1')
        self.assertEqual(parsed['landings_day'], 1)
        self.assertNotIn(headers.index('Day Takeoffs'), matches.values())
        self.assertNotIn(headers.index('Night Takeoffs'), matches.values())

    def test_logbook_pro_simulator_hours_supply_duration_without_aircraft_flight_time(self):
        headers = ['Date','Aircraft Type','Aircraft Ident','Route','Duration','Dual Received',
                   'Flight Simulator','Device Type','Device ID','Simulated Instrument']
        table = read_source(source(headers,[['11/20/2026','B737','','','0','2.0',
                                            '2.0','FFS','Training Device 7','1.5']]))
        self.assertEqual(table.source_key, 'logbook-pro')
        form = ColumnMappingForm(dict(choices(table),time_units='hours',ignore_unused='on'),table=table)
        self.assertTrue(form.is_valid(), form.errors)
        parsed = parse_csv(normalize_mapping(table,form.cleaned_data['mapping'],'hours'))[0][0]
        self.assertTrue(parsed['simulator'])
        self.assertEqual(str(parsed['duration']), '2.0')
        self.assertTrue(parsed['dual'])
        self.assertEqual(parsed['device_type'], 'FFS')
        self.assertEqual(parsed['registration'], '')

    def test_explicit_aircraft_columns_are_not_replaced_with_account_lookup(self):
        table = read_source(source(['Date', 'AircraftType', 'AircraftModel', 'TailNumber', 'TotalFlightTime'],
            [['2026-11-20', 'DA40NG', 'DA40', 'N400TS', '1.5']]))
        self.assertEqual(table.source_key, 'myflightbook')
        self.assertNotIn('Matched Aircraft Type', table.headers)
        self.assertNotIn('aircraft', table.suggestions())  # User chooses between real file columns.
        self.assertEqual(table.candidates()['aircraft'], [1, 2])

    def test_delimiters_and_bom_with_quoted_embedded_punctuation(self):
        for delimiter in (',','\t',';'):
            table = read_source('\ufeff'+source(['Date','Aircraft','Duration','Notes'],
                    [['2026-11-20','C172','1.5','comma, semicolon; tab\t quote "']], delimiter))
            self.assertEqual(table.delimiter, delimiter)
            self.assertEqual(table.records[0][3], 'comma, semicolon; tab\t quote "')

    def test_delimiter_uses_header_not_punctuation_in_remarks(self):
        table = read_source(source(['Date', 'Aircraft', 'Duration', 'Remarks'],
            [['2026-11-20', 'C172', '1.5', 'one;two;three;four;five;six;seven']]))
        self.assertEqual(table.delimiter, ',')
        self.assertEqual(table.row_count, 1)

    def test_derived_route_consumes_endpoints_and_intermediate_column(self):
        table = read_source(source(LTP, [['2026-11-20','N12345','C172','KIAH','KCLL','KMCO','01:30','01:30','','01:30','','0']], '\t'))
        used = table.consumed_columns(table.suggestions().values())
        for name in ('flight_from', 'flight_route', 'flight_to'):
            self.assertIn(str(LTP.index(name)), used)

    def test_duplicate_intermediate_routes_require_a_choice(self):
        table = read_source(source(LTP + ['flight_route'],
            [['2026-11-20','N12345','C172','KIAH','KCLL','KMCO','01:30','01:30','','01:30','','0','KORD']], '\t'))
        self.assertNotIn('route', table.suggestions())
        self.assertNotIn('Complete Route', table.headers)

    def test_year_first_slash_dates_are_normalized(self):
        table = read_source(source(LP, [['2026/11/20','C172','N12345','KIAH-KCLL','1.5','1.5','0','1.5','0','0','1','0','0','1']]))
        form = ColumnMappingForm(dict(choices(table), time_units='hours', ignore_unused='on'), table=table)
        self.assertTrue(form.is_valid(), form.errors)
        output = normalize_mapping(table, form.cleaned_data['mapping'], 'hours')
        self.assertIn('2026-11-20', output)

    def test_logten_combines_endpoints_and_native_fields(self):
        table = read_source(source(LTP,[['2026-11-20','N12345','C172','KIAH','KCLL','KMCO','01:30','01:30','','01:30','','0']], '\t'))
        self.assertEqual(table.source_key,'logten')
        suggested = table.suggestions()
        self.assertEqual(table.headers[suggested['aircraft']], 'aircraftType_type')
        self.assertEqual(table.records[0][suggested['route']], 'KIAH-KCLL-KMCO')
        self.assertFalse(table.needs_time_units)
        self.assertNotIn('departure', suggested)

    def test_bare_numeric_native_times_require_confirmation(self):
        table = read_source(source(MFB,[['11/20/2026','N12345','C172','90','90','0','90','0','1','0','0','KIAH-KCLL','']]))
        form = ColumnMappingForm(choices(table), table=table)
        self.assertFalse(form.is_valid())
        self.assertIn('time_units',form.errors)
        data = choices(table)
        data.update(time_units='minutes',ignore_unused='on')
        form = ColumnMappingForm(data,table=table)
        self.assertTrue(form.is_valid(),form.errors)
        output = normalize_mapping(table,form.cleaned_data['mapping'],'minutes')
        self.assertEqual(str(parse_csv(output)[0][0]['duration']),'1.5')

    def test_hours_minutes_do_not_get_converted_twice(self):
        table = read_source(source(LTP,[['2026-11-20','N12345','C172','KIAH','','KCLL','01:30','90','','90','','0']], '\t'))
        data = choices(table); data.update(time_units='minutes',ignore_unused='on')
        form = ColumnMappingForm(data,table=table)
        self.assertTrue(form.is_valid(),form.errors)
        parsed = parse_csv(normalize_mapping(table,form.cleaned_data['mapping'],'minutes'))[0][0]
        self.assertEqual(str(parsed['duration']),'1.5')
        self.assertTrue(parsed['pilot_in_command'])

    def test_foreflight_join_sections_type_hints_and_physical_line_numbers(self):
        table = read_source(ff_file())
        self.assertEqual(table.source_key,'foreflight')
        row = next(row for row in table.records if any(row))
        suggestions = table.suggestions()
        self.assertEqual(row[suggestions['aircraft']], 'C172')
        self.assertEqual(row[suggestions['registration']], 'N12345')
        self.assertEqual(row[suggestions['route']], 'KIAH-KCLL')
        self.assertEqual(table.row_count,1)
        self.assertEqual(next(i for i,r in enumerate(table.records,2) if any(r)),11)

    def test_conflicting_or_missing_aircraft_join_does_not_guess(self):
        for rows in [[['N12345','aircraft','C172'],['N12345','aircraft','PA28']], [['N54321','aircraft','PA28']]]:
            table = read_source(ff_file(aircraft_rows=rows))
            row = next(r for r in table.records if any(r))
            self.assertEqual(row[table.suggestions()['aircraft']], '')

    def test_native_ifr_is_not_actual_instrument(self):
        table = read_source(source(MFB+['IFR'],[['11/20/2026','N12345','C172','1.5','1.5','0','1.5','0.2','1','0','0','KIAH-KCLL','','1.5']]))
        self.assertEqual(table.suggestions()['instrument'],MFB.index('IMC'))

    def test_duplicate_hour_columns_are_not_silently_chosen(self):
        table = read_source(source(LTP+['flight_totalTime'],
             [['2026-11-20','N12345','C172','KIAH','','KCLL','1.5','1.5','','1.5','','0','2.0']], '\t'))
        self.assertNotIn('duration', table.suggestions())

    def test_generic_unambiguous_columns_do_not_claim_native_format(self):
        table = read_source(source(['Date','Type','Reg','Duration'],[['2026-11-20','C172','N12345','1.5']]))
        self.assertEqual(table.source_key,'')

    def test_routes_avoid_duplicate_endpoints_and_keep_round_trips(self):
        self.assertEqual(full_route('KIAH','KIAH-KCLL-KMCO','KMCO'),'KIAH-KCLL-KMCO')
        self.assertEqual(full_route('KIAH','KCLL','KIAH'),'KIAH-KCLL-KIAH')

    def test_local_flights_keep_both_endpoints_without_intermediate_stops(self):
        for code in ('AXH', 'KAXH', 'IAH', 'KIAH'):
            with self.subTest(code=code):
                self.assertEqual(full_route(code, '', code), f'{code}-{code}')
        table = read_source(source(LTP, [
            ['2026-11-20','N12345','C172','AXH','','AXH','01:30','01:30','','','','0']]))
        self.assertEqual(table.records[0][table.suggestions()['route']], 'AXH-AXH')


@override_settings(SECURE_SSL_REDIRECT=False)
class NativeAdapterWizardTests(TestCase):
    def test_myflightbook_source_id_cannot_overwrite_django_flight_and_sim_is_not_a_tailnumber(self):
        from csv_app.csv_import import csv_import
        from csv_app.tests.test_atomic_import import content
        from flights.models import TailNumber
        csv_import.run(SimpleNamespace(user=self.user),content())
        original = Flight.objects.get(user=self.user)
        before = list(Flight.objects.filter(pk=original.pk).values())[0]
        headers = ['Date','Tail Number','Model','From','To','Total Flight Time','PIC',
                   'Dual Received','Ground Simulator','Flight ID','Device Type','Device ID']
        raw = source(headers,[
            ['11/20/2026','N12345','C172','KIAH','KCLL','1.5','1.5','','',str(original.pk),'',''],
            ['11/21/2026','SIM','C172','','','0','','2.0','2.0',str(original.pk),'FFS','Trainer 8'],
        ])
        response = self.client.post(reverse('csv_inspect'),{
            'file':SimpleUploadedFile('mfb.csv',raw.encode())})
        batch = response.context['batch']
        response = self.client.post(reverse('csv_mapping',args=[batch.pk]),
            dict(choices(read_source(raw)),time_units='hours',ignore_unused='on'))
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertEqual(Flight.objects.filter(user=self.user).count(),3)
        self.assertEqual(list(Flight.objects.filter(pk=original.pk).values())[0],before)
        self.assertFalse(TailNumber.objects.filter(user=self.user,registration='SIM').exists())
        self.assertIsNone(Flight.objects.get(user=self.user,simulator=True).registration)
        total = Total.objects.get(user=self.user,total='All')
        self.assertEqual(str(total.total_time),'3.0')
        self.assertEqual(str(total.simulator),'2.0')

    def test_logten_selected_aircraft_and_confirmed_minutes_preserve_flight_device_totals(self):
        headers = ['flight_flightDate','flight_selectedAircraftID','flight_selectedAircraftType',
            'flight_from','flight_to','flight_totalTime','flight_pic','flight_dualReceived',
            'flight_simulator','flight_type','Device Type','Device ID','flight_selectedCrewCommander']
        raw = source(headers,[
            ['2026-11-01','N12345','C172','KIAH','KCLL','90','90','','','0','','','Someone Else'],
            ['2026-11-02','','C172','','','0','','120','120','3','FFS','Trainer','Someone Else'],
        ], '\t')
        response = self.client.post(reverse('csv_inspect'),{
            'file':SimpleUploadedFile('verified-lt.tsv',raw.encode())})
        self.assertTrue(response.context['mapping_choice'])
        batch = response.context['batch']
        table = read_source(raw)
        response = self.client.post(reverse('csv_mapping',args=[batch.pk]),
            dict(choices(table),time_units='minutes',ignore_unused='on'))
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        total = Total.objects.get(user=self.user,total='All')
        self.assertEqual(str(total.total_time),'1.5')
        self.assertEqual(str(total.simulator),'2.0')
        self.assertEqual(str(total.pilot_in_command),'1.5')
        self.assertEqual(str(total.dual),'0.0')
        self.assertEqual(Flight.objects.filter(user=self.user).count(),2)
        self.assertFalse(Flight.objects.get(user=self.user,simulator=True).pilot_in_command)

    def test_logbook_pro_readable_headings_import_through_mapping_with_separate_device_totals(self):
        headers = ['Date','Aircraft Type','Aircraft Ident','Route','Duration','PIC',
                   'Dual Received','Dual Given','Flight Simulator','Device Type','Device ID']
        raw = source(headers, [
            ['11/20/2026','C172','N12345','KIAH-KMCO','1.5','1.5','','1.5','','',''],
            ['11/21/2026','C172','N12345','KIAH-KIAH','1.2','','1.2','','','',''],
            ['11/22/2026','C172','','','0','','2.0','','2.0','FFS','Device 7'],
        ])
        response = self.client.post(reverse('csv_inspect'), {
            'file':SimpleUploadedFile('lp-readable.csv',raw.encode())})
        self.assertTrue(response.context['mapping_choice'])
        batch = response.context['batch']
        table = read_source(raw)
        data = dict(choices(table), time_units='hours', ignore_unused='on')
        response = self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        total = Total.objects.get(user=self.user,total='All')
        self.assertEqual(str(total.total_time),'2.7')
        self.assertEqual(str(total.simulator),'2.0')
        self.assertEqual(str(total.pilot_in_command),'1.5')
        self.assertEqual(str(total.dual),'1.2')
        self.assertEqual(str(total.instructor),'1.5')
        self.assertEqual(Flight.objects.filter(user=self.user).count(),3)
        self.assertIsNone(Flight.objects.get(user=self.user,simulator=True).registration)

    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('native-adapters')
        seed_records(self.user)
        self.client.force_login(self.user)

    def upload(self,text):
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('logbook.txt',text.encode())})
        self.assertTrue(response.context['mapping_choice'])
        return response.context['batch'],read_source(text,user=self.user),response

    def map(self,batch,table,units='hours'):
        data=choices(table);data.update(time_units=units,ignore_unused='on')
        return self.client.post(reverse('csv_mapping',args=[batch.pk]),data)

    def test_logbook_pro_semicolon_maps_and_imports_once_with_totals(self):
        text=source(LP,[['11/20/2026','C172','N12345','IAH-CLL','1.5','1.5','0','1.5','0.2','0.3','1','0','0','1']],';')
        batch,table,response=self.upload(text)
        self.assertContains(response,'Plain numeric times are in')
        for product in ('Logbook Pro','LogTen','ForeFlight','MyFlightbook'):
            self.assertNotContains(response,product)
        response=self.map(batch,table)
        self.assertTrue(response.context['preview_ready'])
        receipt,duplicate=confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertFalse(duplicate)
        self.assertTrue(receipt.completed)
        _,duplicate=confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertTrue(duplicate)
        self.assertEqual(Flight.objects.count(),1)
        self.assertEqual(str(Total.objects.get(user=self.user,total='All').total_time),'1.5')

    def test_missing_units_cannot_advance_or_queue(self):
        batch,table,_=self.upload(source(MFB,[['11/20/2026','N12345','C172','90','90','0','90','0','1','0','0','IAH-CLL','']]))
        data=choices(table);data['ignore_unused']='on'
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertIn('time_units',response.context['mapping_form'].errors)
        self.assertEqual(self.client.post(reverse('csv_upload'),{'batch_id':batch.pk}).status_code,400)

    def test_partial_sic_requires_review_before_saving(self):
        text=source(LTP,[['2026-11-20','N12345','C172','KIAH','','KCLL','06:00','','01:30','06:00','','0']], '	')
        batch,table,_=self.upload(text)
        response=self.map(batch,table)
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response,'Logged 1.5 of 6.0 hours')
        self.assertFalse(Flight.objects.exists())
        batch.refresh_from_db()
        self.assertFalse(batch.rows_complete)
        with self.assertRaises(CSVValidationError):
            confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)

    def test_nonflight_entry_requires_explicit_exclusion(self):
        batch,table,_=self.upload(source(LTP,[['2026-11-20','N12345','C172','KIAH','','KCLL','01:30','','01:30','','','1']], '\t'))
        response=self.map(batch,table)
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response,'not a flight or training session')

    def test_simulator_only_time_becomes_device_duration_and_stays_out_of_flight_total(self):
        batch,table,_=self.upload(source(MFB+['Device Type','Device ID','Dual'],[['11/20/2026','','C172','0','0','0','0','0','0','0','240','','','FFS','CSV test device','240']]))
        response=self.map(batch,table,'minutes')
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        flight=Flight.objects.get()
        self.assertTrue(flight.simulator)
        self.assertIsNone(flight.registration)
        self.assertEqual(str(flight.duration),'4.0')
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time,0)

    def test_foreflight_joins_aircraft_and_builds_complete_route(self):
        batch,table,_=self.upload(ff_file())
        response=self.map(batch,table)
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertEqual(Flight.objects.get().route,'KIAH-KCLL')
        self.assertEqual(Flight.objects.get().aircraft_type.aircraft_type,'C172')

    def test_foreflight_atd_metadata_is_preserved_without_creating_tailnumber(self):
        batch,table,_=self.upload(ff_file(equipment='AATD',flights=[['2026-11-20','N12345','','','','2.0','2.0']]))
        response=self.map(batch,table)
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        f=Flight.objects.get()
        self.assertEqual((f.device_type,f.atd_type,f.device_id),('ATD','AATD','N12345'))
        self.assertTrue(f.simulator)
        self.assertIsNone(f.registration)

    def test_foreflight_structured_approaches_import_related_records_and_totals(self):
        from csv_app.tests.test_foreflight_approaches import structured_file
        batch,table,_=self.upload(structured_file(['2;ILS;12L;KIAH;Training', '1;RNAV (GPS);18;KAXH;;Circle']))
        response=self.map(batch,table)
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        flight=Flight.objects.get()
        self.assertEqual(sorted(flight.approach_set.values_list('approach_type','number')), [('ILS',2),('RNAV',1)])
        self.assertTrue(flight.hold)
        self.assertTrue(flight.holding_set.filter(hold=True).exists())
        self.assertIn('Circle',flight.remarks)
        self.assertEqual(Total.objects.get(user=self.user,total='All').total_time, Decimal('1.2'))

    def test_uncertain_duplicate_mapping_stays_pending(self):
        batch,table,_=self.upload(source(MFB+['PIC'],[['11/20/2026','N12345','C172','1.5','1.5','0','1.5','0','1','0','0','IAH-CLL','','0']]))
        self.assertNotIn('pilot in command',table.suggestions())
        response=self.map(batch,table)
        # Ambiguous required roles cannot be silently ignored.
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response, 'Select PIC, SIC, Solo, or Dual')

    def test_two_digit_years_need_confirmation_before_expansion(self):
        batch,table,_=self.upload(source(MFB,[['11/20/20','N12345','C172','1.5','1.5','0','1.5','0','1','0','0','IAH-CLL','']]))
        response=self.map(batch,table)
        self.assertIn('confirm_short_years',response.context['mapping_form'].errors)
        data=choices(table);data.update(time_units='hours',ignore_unused='on',confirm_short_years='on')
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertIn('2020-11-20',batch.content)

    def test_missing_simulator_hours_cannot_become_zero_hour_actual_flight(self):
        batch,table,_=self.upload(source(LTP,[['2026-11-20','N12345','C172','KIAH','','KCLL','','','','','','3']], '\t'))
        response=self.map(batch,table)
        self.assertTrue(response.context['row_choice'])
        self.assertContains(response,'Enter Duration and Sim hours')
        self.assertFalse(Flight.objects.exists())

    def test_partial_time_can_be_accepted_by_explicit_row_correction(self):
        from csv_app.tests.test_row_corrections import CSVRowCorrectionTests
        batch,table,_=self.upload(source(LTP,[['2026-11-20','N12345','C172','KIAH','','KCLL','06:00','','01:30','06:00','','0']], '\t'))
        self.map(batch,table)
        batch.refresh_from_db()
        data=CSVRowCorrectionTests.post_data(self,batch,{(2,6):'6.0'})
        response=self.client.post(reverse('csv_rows',args=[batch.pk]),data)
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertEqual(str(Flight.objects.get().duration),'6.0')
        self.assertTrue(Flight.objects.get().second_in_command)

    def test_nonflight_exclusion_can_complete_remaining_flight(self):
        from csv_app.tests.test_row_corrections import CSVRowCorrectionTests
        records=[['2026-11-20','N12345','C172','KIAH','','KCLL','01:30','','01:30','','','0'],
                 ['2026-11-21','N12345','C172','KIAH','','KCLL','01:30','','01:30','','','1']]
        batch,table,_=self.upload(source(LTP,records,'\t'))
        self.map(batch,table);batch.refresh_from_db()
        response=self.client.post(reverse('csv_rows',args=[batch.pk]),CSVRowCorrectionTests.post_data(self,batch,exclude=[3]))
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(response.context['excluded_count'],1)
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertEqual(Flight.objects.count(),1)

    def test_unknown_source_columns_must_be_deliberately_ignored(self):
        batch,table,_=self.upload(source(MFB+['Unmapped custom hours'],
             [['11/20/2026','N12345','C172','1.5','1.5','0','1.5','0','1','0','0','IAH-CLL','','0.5']]))
        data=choices(table);data['time_units']='hours'
        response=self.client.post(reverse('csv_mapping',args=[batch.pk]),data)
        self.assertIn('ignore_unused',response.context['mapping_form'].errors)
        self.assertContains(response,'Unmapped custom hours')


    def test_stock_template_without_model_uses_owned_tailnumber_aircraft(self):
        headers=[name for name in MFB if name != 'Model']
        record=['11/20/2026','N12345','1.5','1.5','0','1.5','0','1','0','0','IAH-CLL','']
        batch,table,_=self.upload(source(headers,[record]))
        response=self.map(batch,table)
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(SimpleNamespace(user=self.user),batch.pk)
        self.assertEqual(Flight.objects.get().aircraft_type.aircraft_type,'C172')

    def test_stock_template_never_looks_up_another_users_aircraft(self):
        other=get_user_model().objects.create_user('foreign-adapter-records')
        a=Aircraft.objects.create(user=other,aircraft_type='PA28')
        from flights.models import TailNumber
        TailNumber.objects.create(user=other,aircraft=a,registration='N77777')
        headers=[name for name in MFB if name != 'Model']
        record=['11/20/2026','N77777','1.5','1.5','0','1.5','0','1','0','0','IAH-CLL','']
        batch,table,_=self.upload(source(headers,[record]))
        response=self.map(batch,table)
        self.assertTrue(response.context['row_choice'])
        self.assertEqual(response.context['correction_rows'][0]['values'][1],'')
