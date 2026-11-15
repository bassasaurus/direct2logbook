from datetime import date, timedelta
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from flights.models import Aircraft
from profile.models import Reminder
from profile.reminder_integrity import reminder_integrity_issues


class ReminderConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.bulk_create([get_user_model()(username='reminder-constraints')])[0]
        cls.aircraft = Aircraft.objects.bulk_create([Aircraft(user=cls.user, aircraft_type='C172')])[0]

    def insert(self, **values):
        return Reminder.objects.bulk_create([Reminder(user=self.user, **values)])[0]

    def rejected(self, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.insert(**values)

    def test_expiration_requires_title_and_date_and_kind_is_valid(self):
        self.rejected(kind='invalid')
        for title in ('', ' ', '\n\t'):
            self.rejected(kind='expiration', title=title, due_date=date(2026, 12, 1))
        self.rejected(kind='expiration', title='BFR')
        self.insert(kind='expiration', title='BFR', due_date=date(2026, 12, 1))

    def test_milestone_targets_are_required_and_positive_but_title_is_optional(self):
        for target in (None, 0, -1):
            self.rejected(kind='flight_time', target_hours=target)
        self.insert(kind='flight_time', target_hours=Decimal('0.1'))
        self.insert(kind='flight_time', target_hours=500)
        self.rejected(kind='expiration', title='BFR', due_date=date(2026, 12, 1), target_hours=-1)

    def test_type_goals_require_aircraft_and_crew_goals_require_valid_position(self):
        self.rejected(kind='time_in_type', target_hours=500)
        self.rejected(kind='crew_in_type', target_hours=500, aircraft=self.aircraft)
        self.rejected(kind='crew_in_type', target_hours=500, aircraft=self.aircraft, crew_position='invalid')
        self.insert(kind='time_in_type', target_hours=500, aircraft=self.aircraft)
        for role in Reminder.CrewPosition.values:
            self.insert(kind='crew_in_type', target_hours=500, aircraft=self.aircraft, crew_position=role)

    def test_company_requires_name_start_and_ordered_optional_end(self):
        start = date(2026, 1, 1)
        self.rejected(kind='company_time', target_hours=500, company_start_date=start)
        self.rejected(kind='company_time', target_hours=500, company='Airline')
        self.rejected(kind='company_time', target_hours=500, company='Airline', company_start_date=start,
                      company_end_date=start-timedelta(days=1))
        for end in (None, start, start+timedelta(days=1)):
            self.insert(kind='company_time', target_hours=500, company='Airline',
                        company_start_date=start, company_end_date=end)
        self.assertEqual(reminder_integrity_issues(apps, 'default'), [])

    def test_raw_updates_reject_invalid_data_without_changing_reminder(self):
        reminder = self.insert(kind='flight_time', target_hours=500)
        before = Reminder.objects.filter(pk=reminder.pk).values().get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reminder.objects.filter(pk=reminder.pk).update(target_hours=0)
        self.assertEqual(Reminder.objects.filter(pk=reminder.pk).values().get(), before)

    def test_aircraft_deletion_removes_only_its_linked_reminders(self):
        linked = self.insert(kind='time_in_type', target_hours=500, aircraft=self.aircraft)
        crew = self.insert(kind='crew_in_type', target_hours=500, aircraft=self.aircraft,
                           crew_position='pilot_in_command')
        unrelated = self.insert(kind='flight_time', target_hours=1000)
        other_aircraft = Aircraft.objects.bulk_create([Aircraft(user=self.user, aircraft_type='A320')])[0]
        other = self.insert(kind='time_in_type', target_hours=500, aircraft=other_aircraft)
        self.assertTrue(self.aircraft.can_delete())
        self.aircraft.delete()
        self.assertFalse(Reminder.objects.filter(pk__in=[linked.pk, crew.pk]).exists())
        self.assertTrue(Reminder.objects.filter(pk=unrelated.pk).exists())
        self.assertTrue(Reminder.objects.filter(pk=other.pk).exists())
        self.assertEqual(reminder_integrity_issues(apps, 'default'), [])

    def test_whole_user_deletion_still_removes_aircraft_and_reminders(self):
        self.insert(kind='time_in_type', target_hours=500, aircraft=self.aircraft)
        self.user.delete()
        self.assertFalse(Reminder.objects.exists())
        self.assertFalse(Aircraft.objects.filter(pk=self.aircraft.pk).exists())



class ReminderConstraintMigrationTests(TransactionTestCase):
    def test_invalid_reminder_aborts_without_rewriting_target_or_dismissal(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [('profile', '0014_profile_distance_unit')]
        after = [('profile', '0015_reminder_validity')]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user_model, reminder_model = old.get_model('auth', 'User'), old.get_model('profile', 'Reminder')
        user = user_model.objects.create(username='reminder-preflight')
        try:
            reminder = reminder_model.objects.create(user_id=user.pk, kind='flight_time', target_hours=-5,
                                                     dismissed_key='unchanged')
            snapshot = reminder_model.objects.filter(pk=reminder.pk).values().get()
            self.assertTrue(reminder_integrity_issues(old, 'default'))
            with self.assertRaisesMessage(RuntimeError, 'invalid reminder'):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(reminder_model.objects.filter(pk=reminder.pk).values().get(), snapshot)
            reminder_model.objects.filter(pk=reminder.pk).update(target_hours=500)  # Only this disposable fixture.
            MigrationExecutor(connection).migrate(after)
            self.assertEqual(reminder_model.objects.get(pk=reminder.pk).dismissed_key, 'unchanged')
        finally:
            user_model.objects.filter(pk=user.pk).delete()
            MigrationExecutor(connection).migrate(latest)
