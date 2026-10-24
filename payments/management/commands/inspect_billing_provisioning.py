from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from payments.services import inspect_stale_provisioning


class Command(BaseCommand):
    help = (
        "Inspect potentially abandoned billing provisioning attempts "
        "without modifying records or contacting Stripe."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=15,
            help="Minimum processing age in minutes (default: 15).",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]

        if minutes <= 0:
            raise CommandError(
                "--minutes must be a positive integer."
            )

        records = inspect_stale_provisioning(
            stale_after=timedelta(minutes=minutes),
        )

        if not records:
            self.stdout.write(
                self.style.SUCCESS(
                    "No potentially abandoned provisioning attempts found."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(records)} potentially abandoned "
                "provisioning attempt(s):"
            )
        )

        for record in records:
            duration = record["processing_duration"]

            if duration is None:
                duration_display = "Unknown"
            else:
                total_seconds = int(duration.total_seconds())
                duration_display = (
                    f"{total_seconds // 60} minutes"
                )

            self.stdout.write(
                f"User: {record['user_id']} | "
                f"Provisioning: {record['provisioning_id']} | "
                f"Duration: {duration_display} | "
                f"Token: {record['processing_token']} | "
                "Reconciliation required: Yes"
            )
