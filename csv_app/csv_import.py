from flights.models import Flight, Aircraft, TailNumber, MapData, Approach, Holding
import re
from logbook.celery import app
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from .models import CSVImportBatch
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from email.utils import make_msgid
import logging
from .validation import parse_csv, CSVValidationError, CSVPreviewExpired
from .records import validate_record_snapshot
from .rows import validate_import_requirements
from .overlaps import validate_overlap_review, OverlapReviewRequired
from .duplicates import submitted_copy
from flights.summary_batch import batch_flight_summaries

logger = logging.getLogger('django.csv_app')
from django.core.mail import EmailMessage


def save_route_data(user, route):
    from flights.airport_resolution import resolve_route, map_values
    return map_values(resolve_route(route))['route_data']


def email_confirmation(request):

    subject = "Your logbook import is complete!"
    body = '''
Your flights have been added to your logbook.

Review your imported flights:
https://direct2logbook.com/flights/logbook/

Thank you for using Direct2Logbook.
'''
    email = EmailMessage(
        subject,
        body,
        'noreply@direct2logbook.com',

        [request.user.email],
        reply_to=['no-reply@direct2logbook.com'],
        headers={'Message-ID': make_msgid(domain='direct2logbook.com')},
    )
    if email.send(fail_silently=False) != 1:
        logger.warning('CSV completion email was not submitted user_id=%s', request.user.pk)


def _notify_import_complete(request):
    try:
        email_confirmation(request)
    except Exception:
        # Imported data stays committed even if notification fails.
        logger.exception('CSV completion email failed user_id=%s', request.user.pk)


@app.task
def csv_import(request, file):
    rows, _ = parse_csv(file)  # Parse the whole file before touching flight data.
    user = request.user
    with transaction.atomic():
        # Serialize imports for this user, including existing totals signals.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        with batch_flight_summaries(user):
            _save_flights(user, rows)
        transaction.on_commit(lambda: _notify_import_complete(request))
    return len(rows)


def _save_flights(user, rows):
    for index, row in enumerate(rows, start=2):
        values = row.copy()
        aircraft, _ = Aircraft.objects.get_or_create(user=user, aircraft_type=values.pop('aircraft'))
        registration_name = values.pop('registration')
        registration = None
        if registration_name:
            registration, _ = TailNumber.objects.get_or_create(
                user=user, registration=registration_name, defaults={'aircraft': aircraft})
            if registration.aircraft_id != aircraft.pk:
                raise CSVValidationError(f'Row {index}: registration belongs to a different aircraft type.')
        if values.get('device_type') or values.get('device_id') or values.get('instrument_credit_eligible'):
            from flights.simulator_validation import validate_simulator_entry
            errors = validate_simulator_entry(values, aircraft_category=aircraft.aircraft_category)
            if values.get('cross_country'):
                errors['cross_country'] = 'Select either Sim or Cross-country.'
            if errors:
                raise CSVValidationError(f'Row {index}: {"; ".join(errors.values())}')
        from .flight_rules import flight_errors
        errors = flight_errors(row, aircraft, registration)
        if errors:
            raise CSVValidationError(f'Row {index}: {"; ".join(errors.values())}')
        values.pop('approaches')
        details = values.pop('approach_details')
        flight = Flight(user=user, aircraft_type=aircraft, registration=registration, **values)
        try:
            flight.full_clean(exclude=['route_data', 'app_markers', 'app_polylines'])
        except ValidationError as exc:
            raise CSVValidationError(f'Row {index}: {"; ".join(exc.messages)}') from exc
        flight.save()  # Keep row validation/maps; summaries rebuild once at batch end.
        for detail in details:
            Approach.objects.create(flight_object=flight, **detail)
        if flight.hold:
            Holding.objects.create(flight_object=flight, hold=True)


@transaction.atomic
def confirm_csv_import(request, batch_id, expected_task_id=None):
    # Match the import's user-first lock ordering. All duplicate confirmations
    # wait for the original transaction and then read its committed outcome.
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    try:
        batch = CSVImportBatch.objects.select_for_update().get(pk=batch_id, user=request.user)
    except CSVImportBatch.DoesNotExist:
        raise Http404('Import not found')
    if batch.completed:
        return batch, True
    if expected_task_id is not None and (
        batch.task_id != expected_task_id or batch.status != CSVImportBatch.Status.PROCESSING
    ):
        return batch, True  # A stale/duplicate worker must never reopen this batch.
    previous = submitted_copy(request.user, batch.source_digest, exclude=batch.pk)
    if previous is not None:
        return previous, True
    if batch.is_expired:
        raise CSVPreviewExpired('This CSV preview has expired. Upload and inspect the file again.')
    if not batch.mapping_complete:
        raise CSVValidationError('Match the columns before importing.')
    if not batch.rows_complete:
        raise CSVValidationError('Correct or exclude invalid rows before importing.')
    if batch.date_order == 'pending':
        raise CSVValidationError('Choose a date format before importing.')
    validate_record_snapshot(batch, request.user, lock=True)
    validate_import_requirements(batch, request.user)
    try:
        validate_overlap_review(batch, request.user)
    except OverlapReviewRequired:
        if expected_task_id is not None:
            raise OverlapReviewRequired('Your logbook changed after review. No entries were imported. Upload the file again to review possible duplicates.') from None
        raise
    count = csv_import(request, batch.content)
    batch.row_count = count
    batch.completed = True
    batch.completed_at = timezone.now()
    batch.content = ''
    batch.row_data = {}
    batch.status = CSVImportBatch.Status.COMPLETED
    batch.updated_at = timezone.now()
    batch.error_message = ''
    batch.save(update_fields=['row_count', 'completed', 'completed_at', 'content', 'row_data', 'status', 'updated_at', 'error_message'])
    return batch, False
