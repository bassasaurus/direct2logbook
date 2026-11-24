from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient
from flights.models import Aircraft, Flight, Imported, TailNumber, Total
from home.pilot_time import pilot_time_report


@override_settings(SECURE_SSL_REDIRECT=False)
class ExpandedPilotTimeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='pilot-time')
        self.other = get_user_model().objects.create_user(username='other-pilot-time')
        self.user.profile.active = True
        self.user.profile.save()
        self.aircraft = {}
        self.tails = {}
        for category, klass, name in [('A', 'SEL', 'C172'), ('R', 'HELO', 'R44'), ('GL', '', 'GL1'),
                                     ('PL', '', 'PL1'), ('LTA', 'BALLOON', 'BAL1'), ('LTA', 'AIRSHIP', 'AIR1')]:
            aircraft = Aircraft.objects.create(user=self.user, aircraft_category=category,
                aircraft_class=klass, aircraft_type=name, self_launch_capable=category == 'GL')
            self.aircraft[name] = aircraft
            self.tails[name] = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N' + name, is_91=True)

    def flight(self, name, **kwargs):
        return Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=self.aircraft[name],
            registration=self.tails[name], date=date(2026, 11, 24), route='SEA-PDX', duration='1.2',
            **kwargs)])[0]

    def test_every_category_populates_hours_role_night_and_xc_without_simulator_time(self):
        for name in self.aircraft:
            self.flight(name, pilot_in_command=True, dual=True, cross_country=True,
                night='0.4', instrument='0.2', landings_night=2,
                launch_method='AEROTOW' if name == 'GL1' else '')
            self.flight(name, simulator=True, device_type='FFS', device_id='D1',
                pilot_in_command=True, dual=True, night='1.0', landings_night=9)
        report = pilot_time_report(self.user)
        for row in report['rows']:
            if row['code'] in ('A', 'R', 'GL', 'PL', 'LTA'):
                factor = 2 if row['code'] == 'LTA' else 1
                for index, expected in [(0, '1.2'), (1, '1.2'), (3, '1.2'), (5, '1.2'),
                                        (7, '1.2'), (9, '0.2'), (10, '0.4'), (12, '0.4')]:
                    self.assertEqual(row['cells'][index]['value'], Decimal(expected) * factor)
                self.assertEqual(row['cells'][11]['value'], 2 * factor)
        self.assertEqual(next(row for row in report['rows'] if row['code'] == 'FFS')['cells'][0]['value'], Decimal('7.2'))
        self.assertEqual(next(row for row in report['classes'] if row['code'] == 'BALLOON')['total'], Decimal('1.2'))
        self.assertEqual(next(row for row in report['classes'] if row['code'] == 'AIRSHIP')['total'], Decimal('1.2'))

    def test_aircraft_instrument_combines_actual_and_hood_without_device_time(self):
        for name in self.aircraft:
            for actual, hood in [('0.2', None), (None, '0.3'), ('0.1', '0.4'), (None, None), ('0.0', '0.0')]:
                self.flight(name, instrument=actual, simulated_instrument=hood,
                    launch_method='AEROTOW' if name == 'GL1' else '')
        for kind, hood in [('FFS', '0.7'), ('FTD', '0.8'), ('ATD', '0.9')]:
            self.flight('C172', simulator=True, device_type=kind, device_id=kind + '-1',
                atd_type='AATD' if kind == 'ATD' else '', simulated_instrument=hood)
        other_aircraft = Aircraft.objects.create(user=self.other, aircraft_type='OTHER',
            aircraft_category='A', aircraft_class='SEL')
        other_tail = TailNumber.objects.create(user=self.other, aircraft=other_aircraft, registration='NOTHER')
        Flight.objects.bulk_create([Flight(user=self.other, aircraft_type=other_aircraft, registration=other_tail,
            date=date.today(), route='SEA-PDX', duration='20.0', instrument='9.0', simulated_instrument='8.0')])
        before = list(Flight.objects.order_by('pk').values('pk', 'instrument', 'simulated_instrument', 'simulator'))
        report = pilot_time_report(self.user)
        rows = {row['code']: row for row in report['rows']}
        for code in ('A', 'R', 'GL', 'PL', 'LTA'):
            with self.subTest(category=code):
                factor = 2 if code == 'LTA' else 1
                self.assertEqual(rows[code]['cells'][9]['value'], Decimal('1.0') * factor)
                self.assertEqual(rows[code]['cells'][0]['value'], Decimal('6.0') * factor)
        for kind, expected in [('FFS', '0.7'), ('FTD', '0.8'), ('ATD', '0.9')]:
            self.assertEqual(rows[kind]['cells'][9]['value'], Decimal(expected))
            self.assertEqual(rows[kind]['cells'][0]['value'], Decimal('1.2'))
        self.assertEqual(list(Flight.objects.order_by('pk').values('pk', 'instrument', 'simulated_instrument', 'simulator')), before)

    def test_web_and_mobile_publish_the_same_combined_aircraft_instrument_total(self):
        self.flight('C172', instrument='0.2', simulated_instrument='0.3')
        self.flight('R44', instrument='0.1', simulated_instrument='0.2')
        self.flight('C172', simulator=True, device_type='FFS', device_id='FFS-1', simulated_instrument='0.7')
        self.client.force_login(self.user)
        web = self.client.get(reverse('home'))
        self.assertEqual(web.status_code, 200)
        self.assertEqual(web.context['airplane_ifr'], Decimal('0.5'))
        self.assertEqual(web.context['rotorcraft_ifr'], Decimal('0.3'))
        client = APIClient()
        client.force_authenticate(self.user)
        mobile = client.get('/api/mobile/stats/')
        self.assertEqual(mobile.status_code, 200)
        web_rows = {row['code']: row for row in web.context['iacra_rows']}
        mobile_rows = {row['code']: row for row in mobile.json()['iacra']['rows']}
        for code, expected in [('A', '0.5'), ('R', '0.3'), ('FFS', '0.7')]:
            self.assertEqual(web_rows[code]['cells'][9]['value'], Decimal(expected))
            self.assertEqual(Decimal(str(mobile_rows[code]['cells'][9]['value'])), Decimal(expected))

    def test_each_actual_glider_record_is_one_launch_regardless_of_landings_or_roles(self):
        first = self.flight('GL1', launch_method='AEROTOW', pilot_in_command=True, dual=True, landings_day=12)
        second = self.flight('GL1', launch_method='GROUND', solo=True)
        third = self.flight('GL1', launch_method='SELF', pilot_in_command=True)
        self.flight('GL1', simulator=True, device_type='FTD', device_id='S1')
        row = next(row for row in pilot_time_report(self.user)['launches'] if row['code'] == 'GL')
        self.assertEqual([row[key] for key in ('flights', 'pic', 'dual', 'aerotow', 'ground', 'self_launch')], [3, 2, 1, 1, 1, 1])
        # Editing changes the existing launch's method rather than adding a launch.
        Flight.objects.filter(pk=second.pk).update(launch_method='AEROTOW')
        Flight.objects.filter(pk=third.pk).delete()
        row = next(row for row in pilot_time_report(self.user)['launches'] if row['code'] == 'GL')
        self.assertEqual([row[key] for key in ('flights', 'aerotow', 'ground', 'self_launch')], [2, 2, 0, 0])
        self.assertTrue(Flight.objects.filter(pk=first.pk).exists())

    def test_imported_balances_add_known_hours_but_never_invent_launches_or_joint_metrics(self):
        self.flight('GL1', launch_method='GROUND', pilot_in_command=True)
        Imported.objects.bulk_create([Imported(user=self.user, aircraft_type=self.aircraft['GL1'],
            total_time='100.0', pilot_in_command='80.0', dual='20.0', cross_country='40.0', night='2.0', simulator='8.0')])
        report = pilot_time_report(self.user)
        glider = next(row for row in report['rows'] if row['code'] == 'GL')
        self.assertEqual(glider['cells'][0]['value'], Decimal('101.2'))
        self.assertEqual(glider['cells'][3]['value'], Decimal('81.2'))
        self.assertIsNone(glider['cells'][5]['value'])
        self.assertIsNone(glider['cells'][12]['value'])
        self.assertEqual(next(row for row in report['launches'] if row['code'] == 'GL')['flights'], 1)

    def test_unused_categories_and_classes_are_hidden_but_owned_aircraft_are_available(self):
        empty = get_user_model().objects.create_user(username='empty-pilot-time')
        self.assertEqual(pilot_time_report(empty)['rows'], [])
        self.assertEqual(pilot_time_report(empty)['classes'], [])
        report = pilot_time_report(self.user)
        self.assertNotIn('AMEL', [row['code'] for row in report['classes']])
        self.assertIn('PL', [row['code'] for row in report['rows']])
        self.assertNotIn('FFS', [row['code'] for row in report['rows']])

    def test_other_accounts_do_not_contribute_and_report_does_not_write_records(self):
        aircraft = Aircraft.objects.create(user=self.other, aircraft_type='SECRET', aircraft_category='GL')
        tail = TailNumber.objects.create(user=self.other, aircraft=aircraft, registration='NSECRET')
        Flight.objects.bulk_create([Flight(user=self.other, aircraft_type=aircraft, registration=tail,
            date=date.today(), route='SEA-PDX', duration='90.0', launch_method='AEROTOW')])
        self.flight('GL1', launch_method='GROUND')
        before = list(Flight.objects.order_by('pk').values())
        with CaptureQueriesContext(connection) as queries:
            report = pilot_time_report(self.user)
        self.assertTrue(all(query['sql'].lstrip().upper().startswith('SELECT') for query in queries))
        self.assertEqual(next(row for row in report['rows'] if row['code'] == 'GL')['cells'][0]['value'], Decimal('1.2'))
        self.assertEqual(list(Flight.objects.order_by('pk').values()), before)
        self.assertEqual(len(queries), 5)

    def test_home_and_mobile_share_the_same_report_and_counts(self):
        self.flight('GL1', launch_method='GROUND', pilot_in_command=True)
        report = pilot_time_report(self.user)
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['iacra_rows']), 8)
        web_rows = {row['code']: row for row in response.context['iacra_rows']}
        for row in report['rows']:
            self.assertEqual(web_rows[row['code']], row)
        self.assertContains(response, 'Ground Launches')
        self.assertNotContains(response, 'Glider flight and launch counts unavailable')
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get('/api/mobile/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['iacra'], report)
        self.assertEqual(response.json()['iacra']['launches'][0]['ground'], 1)

    def test_summary_labels_and_simulator_only_categories_remain_visible(self):
        Total.objects.create(user=self.user, total='GL', simulator='2.5')
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get('/api/mobile/stats/')
        self.assertEqual(next(row for row in response.data['totals'] if row['total'] == 'GL')['display_name'], 'Glider')
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertIn('GL', [row.total for row in response.context['totals']])

    def test_saved_category_summaries_reconcile_with_the_section_three_report(self):
        for name, code in [('GL1', 'GL'), ('PL1', 'PL'), ('BAL1', 'BALLOON'), ('AIR1', 'AIRSHIP')]:
            Flight.objects.create(user=self.user, aircraft_type=self.aircraft[name], registration=self.tails[name],
                date=date.today(), route='SEA-PDX', duration='2.3', pilot_in_command=True,
                launch_method='SELF' if code == 'GL' else '')
            Flight.objects.create(user=self.user, aircraft_type=self.aircraft[name], date=date.today(),
                simulator=True, device_type='FTD', device_id='DEVICE', duration='3.4')
            Imported.objects.create(user=self.user, aircraft_type=self.aircraft[name], total_time='5.6',
                pilot_in_command='4.0', simulator='1.2')
            cached = Total.objects.get(user=self.user, total=code)
            self.assertEqual(cached.total_time, Decimal('7.9'))
            self.assertEqual(cached.pilot_in_command, Decimal('6.3'))
            self.assertEqual(cached.simulator, Decimal('4.6'))
            report_class = next(row for row in pilot_time_report(self.user)['classes'] if row['code'] == code)
            self.assertEqual(report_class['total'], cached.total_time)
            self.assertEqual(report_class['pic'], cached.pilot_in_command)
        glider = next(row for row in pilot_time_report(self.user)['launches'] if row['code'] == 'GL')
        self.assertEqual(glider['flights'], 1)
        self.assertEqual(glider['self_launch'], 1)
