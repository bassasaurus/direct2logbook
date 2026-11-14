from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from flights.models import Aircraft, Flight, TailNumber


class PopulateReviewAccountTests(TestCase):
    def test_copies_latest_100_and_only_their_reference_records(self):
        source = get_user_model().objects.create_user(username="sample_source")
        reviewer = get_user_model().objects.create_user(username="sample_reviewer")
        aircraft = Aircraft.objects.create(
            user=source, aircraft_type="C172", aircraft_category="A",
            aircraft_class="SEL", piston=True, simple=True, small=True,
        )
        tail = TailNumber.objects.create(
            user=source, aircraft=aircraft, registration="N1234", is_91=True,
        )
        unused = Aircraft.objects.create(user=source, aircraft_type="UNUSED")
        TailNumber.objects.create(user=source, aircraft=unused, registration="N9999")
        today = date.today()
        # Bulk insertion keeps fixture creation from repeatedly calculating summaries.
        Flight.objects.bulk_create([
            Flight(user=source, aircraft_type=aircraft, registration=tail,
                   date=today - timedelta(days=index), route="",
                   duration=1, pilot_in_command=True, remarks="Private source notes")
            for index in range(101)
        ])
        dry_output = StringIO()
        call_command("populate_review_account", source_user=source.username,
                     review_user=reviewer.username, dry_run=True, stdout=dry_output)
        self.assertIn("'flights': 100", dry_output.getvalue())
        self.assertIn("'aircraft': 1", dry_output.getvalue())
        self.assertFalse(Flight.objects.filter(user=reviewer).exists())

        output = StringIO()
        call_command("populate_review_account", source_user=source.username,
                     review_user=reviewer.username, confirm=True, stdout=output)
        copied = Flight.objects.filter(user=reviewer)
        self.assertEqual(copied.count(), 100)
        self.assertEqual(set(copied.values_list("date", flat=True)),
                         {today - timedelta(days=index) for index in range(100)})
        self.assertEqual(Aircraft.objects.filter(user=reviewer).count(), 1)
        self.assertEqual(TailNumber.objects.filter(user=reviewer).count(), 1)
        self.assertEqual(set(copied.values_list("remarks", flat=True)), {"Review sample flight"})
        self.assertEqual(Flight.objects.filter(user=source).count(), 101)
        self.assertIn("Copied 100/100 flights.", output.getvalue())
        self.assertIn("Review logbook populated with 100 flights.", output.getvalue())
