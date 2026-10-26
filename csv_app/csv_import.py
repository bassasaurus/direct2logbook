from flights.models import Flight, Aircraft, TailNumber, MapData, Approach
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

logger = logging.getLogger('django.csv_app')
from django.core.mail import EmailMessage


def save_route_data(user, route):

    route_data = []
    route = re.split('\W+', route)  # separate individual codes

    icao = MapData.objects.values_list('icao', flat=True)
    iata = MapData.objects.values_list('iata', flat=True)

    for code in route:  # XXXX, XXXX, XXXX
        code = code.upper()
        if code not in icao and code not in iata:
            pass
        else:
            iata_kwargs = {'iata': code}
            icao_kwargs = {'icao': code}
            map_object = (MapData.objects.filter(**iata_kwargs) | MapData.objects.filter(**icao_kwargs)).first()
            route_data.append(map_object)

    return route_data


def email_confirmation(request):

    subject = "Your logbook import is complete!"
    body = '''
        There are still a few small things to do:

        Errors, or items that need more information will be "red".

        1. Go to "Aircraft" and update the properties of each aircraft type.
        2. Then, update the properties of each tailnumber.

        Login to get started!

        https://www.direct2logbook.com/accounts/login

        We hope you'll enjoy using Direct2Logbook as much as we enjoyed making it!
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
        for index, row in enumerate(rows, start=2):
            values = row.copy()
            aircraft, _ = Aircraft.objects.get_or_create(user=user, aircraft_type=values.pop('aircraft'))
            registration, _ = TailNumber.objects.get_or_create(
                user=user, registration=values.pop('registration'), defaults={'aircraft': aircraft},
            )
            if registration.aircraft_id != aircraft.pk:
                raise CSVValidationError(f'Row {index}: registration belongs to a different aircraft type.')
            approaches = values.pop('approaches')
            flight = Flight(user=user, aircraft_type=aircraft, registration=registration, **values)
            try:
                flight.full_clean(exclude=['route_data', 'app_markers', 'app_polylines'])
            except ValidationError as exc:
                raise CSVValidationError(f'Row {index}: {"; ".join(exc.messages)}') from exc
            flight.save()  # Keep normal map, statistics, and totals signals.
            if approaches:
                Approach.objects.create(flight_object=flight, approach_type='ILS', number=approaches)
        transaction.on_commit(lambda: _notify_import_complete(request))
    return len(rows)


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
    if batch.is_expired:
        raise CSVPreviewExpired('This CSV preview has expired. Upload and inspect the file again.')
    count = csv_import(request, batch.content)
    batch.row_count = count
    batch.completed = True
    batch.completed_at = timezone.now()
    batch.content = ''
    batch.status = CSVImportBatch.Status.COMPLETED
    batch.updated_at = timezone.now()
    batch.error_message = ''
    batch.save(update_fields=['row_count', 'completed', 'completed_at', 'content', 'status', 'updated_at', 'error_message'])
    return batch, False
