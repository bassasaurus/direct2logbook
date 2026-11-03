import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.management.base import BaseCommand, CommandError

from flights.airport_sync import BASE_URL, MAX_DOWNLOAD, parse_sources, source_hash, sync_airports


class TrustedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlparse(newurl)
        if target.scheme != 'https' or target.hostname != urlparse(BASE_URL).hostname:
            raise ValueError('Refusing airport download redirect to an untrusted destination')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(name):
    request = Request(BASE_URL + name + '.csv', headers={'User-Agent': 'Direct2Logbook-AirportSync/1.0'})
    with build_opener(TrustedRedirects()).open(request, timeout=45) as response:
        payload = response.read(MAX_DOWNLOAD + 1)
    if len(payload) > MAX_DOWNLOAD:
        raise ValueError('Airport download exceeds 50 MiB')
    return payload


class Command(BaseCommand):
    help = 'Preview an additive OurAirports refresh; --apply writes changes. Never deletes airports or edits flights.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--apply', action='store_true')
        mode.add_argument('--dry-run', action='store_true', help='Preview only (the default).')
        for name in ('airports', 'countries', 'regions'):
            parser.add_argument('--' + name + '-file', type=Path)
        parser.add_argument('--report', type=Path, help='Write the full proposed/applied changes and skipped matches as JSON.')

    def handle(self, *args, **options):
        files = {name: options[name + '_file'] for name in ('airports', 'countries', 'regions')}
        if any(files.values()) and not all(files.values()):
            raise CommandError('Provide all three local CSV files, or omit them to download the official datasets.')
        target = options['report']
        temp_path = None
        try:
            # Check the report destination before starting an apply transaction.
            if target:
                with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, prefix='.airport-sync-', delete=False) as temp:
                    temp_path = Path(temp.name)
            sources = {}
            for name, path in files.items():
                if path:
                    with path.open('rb') as source:
                        data = source.read(MAX_DOWNLOAD + 1)
                    if len(data) > MAX_DOWNLOAD:
                        raise ValueError('Local CSV exceeds 50 MiB')
                    sources[name] = data
                else:
                    sources[name] = download(name)
            records, skipped = parse_sources(sources['airports'], sources['countries'], sources['regions'])
            report = sync_airports(records, skipped, apply=options['apply'])
            report['source_sha256'] = {name: source_hash(data) for name, data in sources.items()}
            report['source'] = BASE_URL
            if target:
                temp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                os.replace(temp_path, target)
                temp_path = None
        except (OSError, ValueError) as error:
            raise CommandError(str(error)) from error
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)
        verb = 'Applied' if options['apply'] else 'Preview only'
        self.stdout.write(f"{verb}: new={report['created']}, updated={report['updated']}, unchanged={report['unchanged']}, "
                          f"aliases_added={report['aliases_added']}, skipped={len(report['skipped'])}, "
                          f"retained_missing={report['retained_missing']}. No airports deleted; no flights changed.")
        if target:
            self.stdout.write(f'Full report: {target}')
        if report['skipped']:
            self.stdout.write('Skipped matches were left untouched. Use --report to see every reason.')
