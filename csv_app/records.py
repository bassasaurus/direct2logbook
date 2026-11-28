"""Resolve owned aircraft/tailnumbers without rewriting existing logbook records."""
import csv
import io
import json
from collections import OrderedDict
from django.db import transaction

from flights.models import Aircraft, TailNumber
from .validation import CSVValidationError, parse_csv

PAGE_SIZE = 25


class RecordReviewRequired(CSVValidationError):
    """A changed saved record needs correction, without discarding the CSV."""


class RecordResolution:
    def __init__(self, user, content, saved=None):
        self.rows, _ = parse_csv(content)
        self.content = content
        self.saved = saved or {}
        self.aircraft = {item.pk: item for item in Aircraft.objects.filter(user=user)}
        self.tails = {item.pk: item for item in TailNumber.objects.filter(user=user).select_related('aircraft')}
        by_type = {item.aircraft_type.casefold(): item for item in self.aircraft.values()}
        by_reg = {item.registration.casefold(): item for item in self.tails.values()}
        sources = OrderedDict()
        pairs = OrderedDict()
        for row in self.rows:
            key = row['aircraft'].casefold()
            sources.setdefault(key, {'key': key, 'source': row['aircraft'], 'count': 0})['count'] += 1
            if row['registration']:
                pair_key = json.dumps([key, row['registration'].casefold()])
                pair = pairs.setdefault(pair_key, {'key': pair_key, 'source_type': row['aircraft'],
                    'source': row['registration'], 'type_key': key, 'required': False, 'count': 0})
                pair['required'] |= not row['simulator']
                pair['count'] += 1
        self.sources = list(sources.values())
        self.pairs = list(pairs.values())
        for index, source in enumerate(self.sources):
            source.update(index=index, aircraft=self.aircraft.get(self.saved.get('aircraft', {}).get(source['key']))
                          or by_type.get(source['key']))
        by_source = {source['key']: source for source in self.sources}
        for index, pair in enumerate(self.pairs):
            choice = self.saved.get('pairs', {}).get(pair['key'], {})
            aircraft = self.aircraft.get(choice.get('aircraft')) or by_source[pair['type_key']]['aircraft']
            tail = self.tails.get(choice.get('tailnumber')) if choice else by_reg.get(pair['source'].casefold())
            optional_skip = bool(choice) and choice.get('tailnumber') is None and not pair['required']
            pair.update(index=index, aircraft=aircraft, tailnumber=tail,
                        resolved=bool(aircraft and (optional_skip or tail and tail.aircraft_id == aircraft.pk)))
        self.missing_aircraft = [source for source in self.sources if source['aircraft'] is None]
        self.unresolved_pairs = [pair for pair in self.pairs if not pair['resolved']]

    @property
    def issues(self):
        return self.missing_aircraft or self.unresolved_pairs

    def normalized(self):
        if self.issues:
            raise CSVValidationError('Resolve the aircraft and tailnumbers before importing.')
        sources = {item['key']: item['aircraft'] for item in self.sources}
        pairs = {item['key']: item for item in self.pairs}
        used_aircraft, used_tails = {}, {}
        records = list(csv.reader(io.StringIO(self.content)))
        typed = iter(self.rows)
        for raw in records[1:]:
            if not any(value.strip() for value in raw):
                continue
            row = next(typed)
            key = row['aircraft'].casefold()
            pair = pairs.get(json.dumps([key, row['registration'].casefold()])) if row['registration'] else None
            aircraft = pair['aircraft'] if pair else sources[key]
            tail = pair['tailnumber'] if pair else None
            raw[1] = aircraft.aircraft_type
            raw[2] = tail.registration if tail else ''
            used_aircraft[aircraft.pk] = aircraft.aircraft_type
            if tail:
                used_tails[tail.pk] = {'registration': tail.registration, 'aircraft': aircraft.pk}
        output = io.StringIO()
        csv.writer(output).writerows(records)
        receipt = {**self.saved, 'snapshot': {'aircraft': {str(pk): name for pk, name in used_aircraft.items()},
                                           'tailnumbers': {str(pk): value for pk, value in used_tails.items()}}}
        return output.getvalue(), receipt


def validate_record_snapshot(batch, user, *, lock=False):
    if not batch.records_complete:
        raise CSVValidationError('Resolve the aircraft and tailnumbers before importing.')
    snapshot = batch.record_resolution.get('snapshot')
    if not snapshot:
        return  # Preserve previously queued/legacy imports.
    aircraft = Aircraft.objects.filter(user=user, pk__in=snapshot['aircraft'])
    tails = TailNumber.objects.filter(user=user, pk__in=snapshot['tailnumbers'])
    if lock:
        aircraft = aircraft.select_for_update()
        tails = tails.select_for_update()
    actual_aircraft = {str(item.pk): item.aircraft_type for item in aircraft}
    actual_tails = {str(item.pk): {'registration': item.registration, 'aircraft': item.aircraft_id} for item in tails}
    if actual_aircraft != snapshot['aircraft'] or actual_tails != snapshot['tailnumbers']:
        raise RecordReviewRequired('Aircraft or tailnumber details changed after review. Correct the pair to continue.')


@transaction.atomic
def reopen_record_review(user, batch_id, *, task_id=None):
    from django.utils import timezone
    from .models import CSVImportBatch
    batch = CSVImportBatch.objects.select_for_update().get(pk=batch_id, user=user)
    if batch.completed:
        return batch
    if task_id is not None:
        if batch.task_id != task_id or batch.status != CSVImportBatch.Status.PROCESSING:
            return batch
    elif batch.status != CSVImportBatch.Status.PREVIEW:
        return batch
    if batch.record_resolution.get('needs_review'):
        return batch  # Polling/repeated submissions must not extend the preview indefinitely.
    choices = {'aircraft': dict(batch.record_resolution.get('aircraft', {})), 'needs_review': True}
    # Keep stable aircraft identities when only the saved designator was renamed.
    for pk, name in batch.record_resolution.get('snapshot', {}).get('aircraft', {}).items():
        choices['aircraft'][name.casefold()] = int(pk)
    batch.record_resolution = choices
    batch.overlap_review = {}
    batch.records_complete = False
    batch.status = CSVImportBatch.Status.PREVIEW
    batch.error_message = 'Aircraft or tailnumber details changed. Correct the highlighted pair to continue. No flights were imported.'
    batch.created_at = timezone.now()  # Give this newly reopened review its normal 10-minute window.
    batch.updated_at = timezone.now()
    batch.save(update_fields=['record_resolution', 'overlap_review', 'records_complete', 'status',
                              'error_message', 'created_at', 'updated_at'])
    return batch
