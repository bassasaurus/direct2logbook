"""Collect a consistent baseline without invoking writes or recalculations."""
from datetime import date
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from flights.classification_audit import classification_baseline


class Command(BaseCommand):
    help = 'Read-only aircraft classifications and independent Total/Stat reconciliation; never repairs or recalculates stored rows.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS)
        parser.add_argument('--user-id', type=int)
        parser.add_argument('--as-of', type=date.fromisoformat, help='Rolling comparison date, YYYY-MM-DD (default: today).')
        parser.add_argument('--output', type=Path, help='Create a new JSON baseline file; refuses to overwrite an existing baseline.')

    def handle(self, *args, **options):
        alias = options['database']
        if alias not in connections:
            raise CommandError('Unknown database alias.')
        connection = connections[alias]
        if connection.in_atomic_block:
            raise CommandError('Run the audit outside an existing transaction so it can establish a consistent snapshot.')
        if connection.vendor != 'postgresql':
            raise CommandError('This baseline command requires PostgreSQL for a consistent read-only snapshot.')
        try:
            with transaction.atomic(using=alias):
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                report = classification_baseline(alias, options['user_id'], options['as_of'])
                report['database_name'] = str(connection.settings_dict['NAME'])
            serialized = json.dumps(report, cls=DjangoJSONEncoder, indent=2, sort_keys=True) + '\n'
            output = options['output']
            if output:
                # New private file; original baseline is never replaced.
                with output.open('x', encoding='utf-8') as stream:
                    output.chmod(0o600)
                    stream.write(serialized)
                self.stdout.write(f'Baseline saved: {output}')
            else:
                self.stdout.write(serialized)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Read-only audit: {report['snapshots']['Aircraft']['count']} aircraft; "
            f"{report['snapshots']['Flight']['count']} flight/device records; "
            f"{report['snapshots']['Imported']['count']} imported balances. No records changed.")
        self.stdout.write(f"Classification findings: {sum(report['finding_counts'].values())}; "
                          f"summary/integrity findings: {len(report['issues'])}. See the report for details.")
