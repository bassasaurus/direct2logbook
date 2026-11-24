from datetime import date
from decimal import Decimal
import hashlib
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from flights.forms import AircraftForm
from flights.models import Aircraft, Flight, Imported, Power, TailNumber
from api.serializers import AircraftSerializer
from api.revisions import aircraft_revision


class AircraftCharacteristicsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='characteristics')

    def payload(self, category='A', klass='SEL', engine='electric'):
        data = {'aircraft_type': 'TEST', 'aircraft_category': category, 'aircraft_class': klass,
                'small': True}
        if engine:
            data[engine] = True
        return data

    def test_every_tracked_category_requires_exactly_one_engine(self):
        for category, klass in (('A', 'SEL'), ('R', 'HELO'), ('R', 'GYRO'), ('PL', ''), ('LTA', 'AIRSHIP')):
            for engine in ('piston', 'turbine', 'electric'):
                serializer = AircraftSerializer(data=self.payload(category, klass, engine), context={})
                # Existing owner context is required for authenticated creation.
                from types import SimpleNamespace
                serializer.context['request'] = SimpleNamespace(user=self.user)
                self.assertTrue(serializer.is_valid(), serializer.errors)
            form = AircraftForm(data={'aircraft_type': 'TEST', 'aircraft_category': category,
                'aircraft_class': klass, 'weight_category': 'small'}, user=self.user)
            self.assertFalse(form.is_valid())
            self.assertIn('engine', form.errors)
        form = AircraftForm(data={**self.payload(), 'piston': True}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('engine', form.errors)

    def test_glider_and_balloon_hide_clear_and_do_not_require_engine(self):
        from django.template.loader import render_to_string
        for category, klass in (('GL', ''), ('LTA', 'BALLOON')):
            form = AircraftForm(data={'aircraft_type': 'TEST', 'aircraft_category': category,
                'aircraft_class': klass, 'weight_category': 'small', 'engine': 'electric',
                'self_launch_capable': category == 'GL'}, user=self.user)
            self.assertTrue(form.is_valid(), form.errors)
            aircraft = form.save(commit=False)
            self.assertFalse(any((aircraft.piston, aircraft.turbine, aircraft.electric)))
            self.assertEqual(aircraft.self_launch_capable, category == 'GL')
            html = render_to_string('aircraft/aircraft_form.html', {'form': form})
            self.assertIn('data-aircraft-engine hidden', html)

    def test_electric_time_and_imports_are_summarized_separately_from_simulator(self):
        aircraft = Aircraft.objects.create(user=self.user, **self.payload())
        tail = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='NELEC', is_91=True)
        Flight.objects.create(user=self.user, aircraft_type=aircraft, registration=tail,
            route='SEA-PDX', date=date.today(), duration='1.7', pilot_in_command=True)
        Flight.objects.create(user=self.user, aircraft_type=aircraft,
            date=date.today(), duration='2.1', simulator=True, pilot_in_command=True)
        Imported.objects.create(user=self.user, aircraft_type=aircraft, total_time='10.0', pilot_in_command='10.0')
        self.assertEqual(Power.objects.get(user=self.user, role='PIC').electric, Decimal('11.7'))
        self.assertEqual(Power.objects.get(user=self.user, role='Total').electric, Decimal('11.7'))
        aircraft.electric = False
        aircraft.turbine = True
        aircraft.save()
        self.assertEqual(Power.objects.get(user=self.user, role='Total').electric, 0)
        self.assertEqual(Power.objects.get(user=self.user, role='Total').turbine, Decimal('11.7'))

    def test_unaffected_aircraft_revision_matches_the_installed_app_schema(self):
        aircraft = Aircraft.objects.create(user=self.user, **self.payload(engine='piston'))
        old_values = {field.attname: str(getattr(aircraft, field.attname)) for field in aircraft._meta.concrete_fields
                      if field.attname not in ('is_default', 'electric', 'self_launch_capable', 'default_crew_role', 'default_cross_country')}
        old_values.update(medium='False', light_sport='False')
        old_revision = hashlib.sha256(json.dumps(old_values, sort_keys=True).encode()).hexdigest()
        self.assertEqual(aircraft_revision(aircraft), old_revision)

    def test_legacy_medium_request_becomes_small_and_retired_choices_are_not_exposed(self):
        from types import SimpleNamespace
        serializer = AircraftSerializer(data={**self.payload(engine='piston'), 'small': False, 'medium': True},
            context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        aircraft = serializer.save(user=self.user)
        self.assertTrue(aircraft.small)
        self.assertNotIn('medium', serializer.data)
        self.assertNotIn('light_sport', serializer.data)
        self.assertEqual([key for key, _ in AircraftForm().fields['weight_category'].choices],
                         ['small', 'large', 'heavy', 'superr'])

    def test_glider_clears_inapplicable_flags_through_forms_and_api_including_partial_updates(self):
        from types import SimpleNamespace
        flags = dict(requires_type=True, compleks=True, high_performance=True, tailwheel=True, simple=True)
        form = AircraftForm(user=self.user, data={'aircraft_type': 'GL1', 'aircraft_category': 'GL',
            'aircraft_class': '', 'weight_category': 'small', **flags})
        self.assertTrue(form.is_valid(), form.errors)
        aircraft = form.save()
        self.assertFalse(any(getattr(aircraft, field) for field in flags))
        serializer = AircraftSerializer(aircraft, data=flags, partial=True,
            context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        aircraft.refresh_from_db()
        self.assertFalse(any(getattr(aircraft, field) for field in flags))
        # Converting an existing airplane clears old airplane-only attributes.
        plane = Aircraft.objects.create(user=self.user, aircraft_type='PLANE', aircraft_category='A',
            aircraft_class='SEL', piston=True, small=True, **flags)
        serializer = AircraftSerializer(plane, data={'aircraft_category': 'GL', 'aircraft_class': ''},
            partial=True, context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        glider = serializer.save()
        self.assertFalse(any(getattr(glider, field) for field in flags))
        from flights.aircraft_characteristics import normalize_characteristics
        for category, klass in [('A', 'SEL'), ('R', 'HELO'), ('PL', ''), ('LTA', 'AIRSHIP')]:
            result = normalize_characteristics({'aircraft_category': category, 'aircraft_class': klass, **flags})
            for field in flags:
                self.assertEqual(result[field], field != 'simple' and (category == 'A' or field == 'requires_type' and category in ('R', 'PL')))

    def test_equipment_rules_apply_to_web_create_and_api_partial_updates(self):
        from types import SimpleNamespace
        for category, klass in [('A', 'SEL'), ('R', 'HELO'), ('R', 'GYRO'), ('GL', ''), ('PL', ''), ('LTA', 'BALLOON'), ('LTA', 'AIRSHIP')]:
            with self.subTest(category=category, klass=klass):
                flags = dict(requires_type=False, tailwheel=True, simple=True, compleks=True, high_performance=True)
                data = dict(aircraft_type=('T' + category + klass)[:10], aircraft_category=category,
                            aircraft_class=klass, engine='piston', weight_category='small', **flags)
                form = AircraftForm(user=self.user, data=data)
                self.assertTrue(form.is_valid(), form.errors)
                aircraft = form.save()
                for field in ('tailwheel', 'compleks', 'high_performance'):
                    self.assertEqual(getattr(aircraft, field), category == 'A')
                self.assertEqual(aircraft.requires_type, category == 'PL')
                self.assertFalse(aircraft.simple)
                serializer = AircraftSerializer(aircraft, data={**flags, 'requires_type': True}, partial=True,
                    context={'request': SimpleNamespace(user=self.user)})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                aircraft = serializer.save()
                self.assertEqual(aircraft.requires_type, category in ('A', 'R', 'PL'))
                for field in ('tailwheel', 'compleks', 'high_performance'):
                    self.assertEqual(getattr(aircraft, field), category == 'A')
                self.assertFalse(aircraft.simple)

    def test_retired_simple_metadata_and_hours_survive_normal_aircraft_edits(self):
        from types import SimpleNamespace
        from flights.models import Endorsement, Total
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172', aircraft_category='A',
            aircraft_class='SEL', piston=True, small=True, simple=True)
        tail = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='NLEGACY', is_91=True)
        Flight.objects.create(user=self.user, aircraft_type=aircraft, registration=tail, route='SEA-PDX',
            date=date.today(), duration='1.3', pilot_in_command=True)
        form = AircraftForm(instance=aircraft, user=self.user, data=dict(aircraft_type='C172',
            aircraft_category='A', aircraft_class='SEL', engine='piston', weight_category='small'))
        self.assertTrue(form.is_valid(), form.errors)
        aircraft = form.save()
        self.assertTrue(aircraft.simple)
        serializer = AircraftSerializer(aircraft, data={'simple': False}, partial=True,
            context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.save().simple)
        self.assertEqual(Endorsement.objects.get(user=self.user, endorsement='Simple').total, Decimal('1.3'))
        self.assertEqual(Total.objects.get(user=self.user, total='ASEL').total_time, Decimal('1.3'))
        from home.views import HomeView
        view = HomeView()
        view.request = SimpleNamespace(user=self.user)
        context = view.get_context_data()
        self.assertFalse(context['endorsements'].filter(endorsement='Simple').exists())


class AircraftWakeMigrationTests(TransactionTestCase):
    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.latest = self.executor.loader.graph.leaf_nodes()
        self.executor.migrate([('flights', '0077_aircraft_categories_8710')])
        self.old = self.executor.loader.project_state([('flights', '0077_aircraft_categories_8710')]).apps

    def tearDown(self):
        # Leave the test database on its current schema even after a guard test.
        from django.db.migrations.recorder import MigrationRecorder
        if not MigrationRecorder(connection).migration_qs.filter(app='flights', name='0078_engine_and_wake_classes').exists():
            self.old.get_model('flights', 'Aircraft').objects.filter(light_sport=True).update(light_sport=False)
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.latest)
        super().tearDown()

    def test_converts_medium_and_rebuilds_weight_totals_without_touching_flights(self):
        User = self.old.get_model('auth', 'User')
        OldAircraft = self.old.get_model('flights', 'Aircraft')
        OldFlight = self.old.get_model('flights', 'Flight')
        user = User.objects.create(username='migration-owner')
        aircraft = OldAircraft.objects.create(user_id=user.pk, aircraft_type='TEST', medium=True, turbine=True)
        tail = self.old.get_model('flights', 'TailNumber').objects.create(user_id=user.pk, aircraft_id=aircraft.pk, registration='NMIG')
        OldFlight.objects.create(user_id=user.pk, aircraft_type_id=aircraft.pk, registration_id=tail.pk,
                                date=date.today(), route='SEA-PDX', duration='1.7')
        OldFlight.objects.create(user_id=user.pk, aircraft_type_id=aircraft.pk, date=date.today(),
                                simulator=True, duration='2.1')
        self.old.get_model('flights', 'Imported').objects.create(user_id=user.pk, aircraft_type_id=aircraft.pk, total_time='10.0')
        self.old.get_model('flights', 'Weight').objects.create(user_id=user.pk, weight='Medium', total='11.7')
        before = list(OldFlight.objects.order_by('pk').values())
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([('flights', '0078_engine_and_wake_classes')])
        MigratedAircraft = self.executor.loader.project_state([('flights', '0078_engine_and_wake_classes')]).apps.get_model('flights', 'Aircraft')
        aircraft = MigratedAircraft.objects.get(pk=aircraft.pk)
        self.assertTrue(aircraft.small)
        self.assertTrue(aircraft.turbine)
        self.assertFalse(aircraft.electric)
        self.assertEqual(before, list(self.executor.loader.project_state([('flights', '0078_engine_and_wake_classes')]).apps.get_model('flights', 'Flight').objects.order_by('pk').values()))
        from flights.models import Weight
        self.assertEqual(Weight.objects.get(user_id=user.pk, weight='Small').total, Decimal('11.7'))
        self.assertFalse(Weight.objects.filter(weight__in=('Medium', 'LSA')).exists())

    def test_unexpected_light_sport_record_stops_before_data_is_dropped(self):
        user = self.old.get_model('auth', 'User').objects.create(username='unexpected-lsa')
        OldAircraft = self.old.get_model('flights', 'Aircraft')
        aircraft = OldAircraft.objects.create(user_id=user.pk, aircraft_type='REVIEW', light_sport=True)
        with self.assertRaisesRegex(RuntimeError, 'Light-Sport aircraft exist'):
            MigrationExecutor(connection).migrate([('flights', '0078_engine_and_wake_classes')])
        self.assertTrue(OldAircraft.objects.get(pk=aircraft.pk).light_sport)

    def test_older_simulator_migration_remains_valid_on_its_historical_schema(self):
        from importlib import import_module
        from types import SimpleNamespace
        user = self.old.get_model('auth', 'User').objects.create(username='historical-simulator')
        aircraft = self.old.get_model('flights', 'Aircraft').objects.create(user_id=user.pk,
            aircraft_type='TEST', small=True, piston=True, aircraft_category='A', aircraft_class='SEL')
        tail = self.old.get_model('flights', 'TailNumber').objects.create(user_id=user.pk, aircraft_id=aircraft.pk, registration='NHIST')
        OldFlight = self.old.get_model('flights', 'Flight')
        for duration, simulator in (('1.7', False), ('2.1', True)):
            OldFlight.objects.create(user_id=user.pk, aircraft_type_id=aircraft.pk, registration_id=tail.pk,
                date=date.today(), route='SEA-PDX', duration=duration, simulator=simulator, pilot_in_command=True)
        totals = self.old.get_model('flights', 'Total').objects
        total = totals.create(user_id=user.pk, total='All')
        before = list(OldFlight.objects.order_by('pk').values())
        migration = import_module('flights.migrations.0074_separate_simulator_summaries')
        schema = SimpleNamespace(connection=connection)
        migration.restore(self.old, schema)
        self.assertEqual(totals.get(pk=total.pk).total_time, Decimal('3.8'))
        migration.rebuild(self.old, schema)
        self.assertEqual(totals.get(pk=total.pk).total_time, Decimal('1.7'))
        self.assertEqual(totals.get(pk=total.pk).simulator, Decimal('2.1'))
        once = list(totals.order_by('pk').values())
        migration.rebuild(self.old, schema)
        self.assertEqual(once, list(totals.order_by('pk').values()))
        self.assertEqual(before, list(OldFlight.objects.order_by('pk').values()))
