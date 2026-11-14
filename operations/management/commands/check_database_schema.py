from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, router


class Command(BaseCommand):
    help = 'Verify managed model tables exist, including legacy migration histories.'

    def handle(self, *args, **options):
        existing = set(connection.introspection.table_names(include_views=True))
        expected = {
            model._meta.db_table for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.swapped
            and router.allow_migrate_model(connection.alias, model)
        }
        missing = sorted(expected - existing)
        if missing:
            raise CommandError('Missing managed database tables: ' + ', '.join(missing))
        self.stdout.write('Managed database tables verified.')
