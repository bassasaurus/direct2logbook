"""Populate an existing, empty app-review account with anonymized logbook data.

Run with --dry-run first. Never creates credentials or changes the source account.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from flights.models import Aircraft, Approach, Flight, Holding, Imported, TailNumber


def copy_fields(instance, excluded=()):
    """Copy concrete scalar fields, excluding primary keys and explicitly excluded fields."""
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
        if not field.primary_key and field.name not in excluded
    }


class Command(BaseCommand):
    help = "Clone all flights into an empty reviewer account, anonymizing identifiers."

    def add_arguments(self, parser):
        parser.add_argument("--source-user", required=True)
        parser.add_argument("--review-user", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--confirm", action="store_true", help="Required to write changes.")

    def handle(self, *args, **options):
        User = get_user_model()
        source_name = options["source_user"]
        review_name = options["review_user"]
        if source_name == review_name:
            raise CommandError("Source and reviewer must be different users.")
        try:
            source = User.objects.get(username=source_name)
            reviewer = User.objects.get(username=review_name)
        except User.DoesNotExist as exc:
            raise CommandError("Both users must already exist.") from exc

        source_flights = Flight.objects.filter(user=source)
        counts = {
            "aircraft": Aircraft.objects.filter(user=source).count(),
            "tail_numbers": TailNumber.objects.filter(user=source).count(),
            "flights": source_flights.count(),
            "approaches": Approach.objects.filter(flight_object__user=source).count(),
            "holdings": Holding.objects.filter(flight_object__user=source).count(),
            "imported": Imported.objects.filter(user=source).count(),
        }
        self.stdout.write(str(counts))
        if options["dry_run"]:
            self.stdout.write("DRY RUN: no records changed.")
            return
        if not options["confirm"]:
            raise CommandError("Use --dry-run to inspect or --confirm to populate.")
        if not counts["flights"]:
            raise CommandError("Source has no flights.")

        with transaction.atomic():
            # Lock the target user to serialize concurrent invocations.
            User.objects.select_for_update().get(pk=reviewer.pk)
            if any(model.objects.filter(user=reviewer).exists()
                   for model in (Aircraft, TailNumber, Flight, Imported)):
                raise CommandError("Reviewer already has logbook data; refusing to overwrite.")

            aircraft_map = {}
            for original in Aircraft.objects.filter(user=source).order_by("pk"):
                data = copy_fields(original, {"user", "image"})
                data.update(user_id=reviewer.pk, image=None)
                clone = Aircraft.objects.create(**data)
                aircraft_map[original.pk] = clone.pk

            tail_map = {}
            for index, original in enumerate(TailNumber.objects.filter(user=source).order_by("pk"), 1):
                # Fixed-width, fictional identifiers; do not retain actual registrations.
                data = copy_fields(original, {"user", "aircraft", "registration"})
                data.update(
                    user_id=reviewer.pk,
                    aircraft_id=aircraft_map[original.aircraft_id],
                    registration=f"RV{index:08d}",
                )
                if len(data["registration"]) > TailNumber._meta.get_field("registration").max_length:
                    raise CommandError("Too many registrations for anonymized identifier field.")
                clone = TailNumber.objects.create(**data)
                tail_map[original.pk] = clone.pk

            flight_map = {}
            sensitive = {
                "user", "aircraft_type", "registration", "remarks",
                "route_airport_choices", "route_data", "map_error",
                "duplicate_error", "aircraft_type_error", "registration_error",
                "crew_error", "app_markers", "app_polylines",
            }
            for original in source_flights.order_by("pk").iterator():
                data = copy_fields(original, sensitive)
                data.update(
                    user_id=reviewer.pk,
                    aircraft_type_id=aircraft_map[original.aircraft_type_id],
                    registration_id=tail_map[original.registration_id],
                    remarks="Review sample flight",
                    route_airport_choices={},
                    route_data=None,
                    map_error=None,
                    duplicate_error=None,
                    aircraft_type_error=None,
                    registration_error=None,
                    crew_error=None,
                    app_markers=[],
                    app_polylines=[],
                )
                clone = Flight.objects.create(**data)
                flight_map[original.pk] = clone.pk

            for original in Approach.objects.filter(flight_object_id__in=flight_map).iterator():
                data = copy_fields(original, {"flight_object"})
                data["flight_object_id"] = flight_map[original.flight_object_id]
                Approach.objects.create(**data)

            for original in Holding.objects.filter(flight_object_id__in=flight_map).iterator():
                data = copy_fields(original, {"flight_object"})
                data["flight_object_id"] = flight_map[original.flight_object_id]
                Holding.objects.create(**data)

            for original in Imported.objects.filter(user=source).iterator():
                data = copy_fields(original, {"user", "aircraft_type"})
                data.update(user_id=reviewer.pk, aircraft_type_id=aircraft_map[original.aircraft_type_id])
                Imported.objects.create(**data)

        self.stdout.write(self.style.SUCCESS(
            "Review logbook populated. Rebuild derived totals/statistics with the app's normal calculation workflow."
        ))
