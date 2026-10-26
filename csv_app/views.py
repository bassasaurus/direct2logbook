from django.shortcuts import render, reverse, redirect
import csv
from django.http import HttpResponse, JsonResponse, Http404
from django import forms
from flights.models import Flight
from .submission import queue_csv_import
from .models import CSVImportBatch
import uuid
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.db import transaction
from django.views.decorators.csrf import csrf_protect
from django.db.models import Sum, F
from .validation import parse_csv, CSVValidationError, CSVPreviewExpired, MAX_BYTES
import logging

logger = logging.getLogger('django.csv_app')


@login_required
@require_GET
def csv_download_view(request):
    user = request.user
    # Create the HttpResponse object with the appropriate CSV header.

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}_{}_logbook.csv"'.format(
        user.first_name, user.last_name)

    flights = Flight.objects.filter(user=user)
    writer = csv.writer(response)
    writer.writerow([
        'date',
        'aircraft',
        'registration',
        'route',
        'duration',
        'pilot in command',
        'second in command',
        'cross country',
        'night',
        'instrument',
        'approaches',
        'day landing',
        'night landing',
        'simulated instrument',
        'instructor',
        'dual',
        'solo',
        'simulator',
        'remarks',

    ])

    for flight in flights:

        if flight.pilot_in_command:
            pic = flight.duration
        else:
            pic = 0

        if flight.second_in_command:
            sic = flight.duration
        else:
            sic = 0

        if flight.cross_country:
            xc = flight.duration
        else:
            xc = 0

        if not flight.night:
            night = 0
        else:
            night = flight.night

        if not flight.instrument:
            ifr = 0
        else:
            ifr = flight.instrument

        if not flight.landings_day:
            day_ldg = 0
        else:
            day_ldg = flight.landings_day

        if not flight.landings_night:
            night_ldg = 0
        else:
            night_ldg = flight.landings_night

        if not flight.simulated_instrument:
            sim_inst = 0
        else:
            sim_inst = flight.simulated_instrument

        if not flight.instructor:
            cfi = 0
        else:
            cfi = flight.duration

        if not flight.dual:
            dual = 0
        else:
            dual = flight.duration

        if not flight.solo:
            solo = 0
        else:
            solo = flight.duration

        if not flight.simulator:
            sim = 0
        else:
            sim = flight.duration

        writer.writerow([
            str(flight.date),
            str(flight.aircraft_type),
            str(flight.registration),
            str(flight.route),
            flight.duration,
            pic,
            sic,
            xc,
            night,
            ifr,
            flight.approach_set.aggregate(total=Sum('number'))['total'] or 0,
            day_ldg,
            night_ldg,
            sim_inst,
            cfi,
            dual,
            solo,
            sim,
            flight.remarks
        ])

    return response


class InspectForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        upload = self.cleaned_data['file']
        if upload.size > MAX_BYTES:
            raise forms.ValidationError('The CSV must be no larger than 2 MB.')
        return upload


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def csv_inspect_view(request):
    form = InspectForm(request.POST or None, request.FILES or None)
    context = {
        'inspect_form': form, 'title': 'CSV Upload',
        'home_link': reverse('home'), 'parent_link': reverse('profile'),
        'parent_name': 'Profile',
        'latest_import': CSVImportBatch.objects.filter(
            user=request.user, completed=False, status__in=[CSVImportBatch.Status.QUEUED,
                CSVImportBatch.Status.PROCESSING, CSVImportBatch.Status.UNCONFIRMED],
        ).order_by(F('submitted_at').desc(nulls_last=True), '-created_at').first(),
    }
    if request.method == 'POST':
        request.session.pop('file', None)
        if form.is_valid():
            try:
                raw = form.cleaned_data['file'].read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise CSVValidationError('The CSV must be no larger than 2 MB.')
                content = raw.decode('utf-8-sig')
                rows, preview = parse_csv(content)
                batch = CSVImportBatch.objects.create(user=request.user, content=content, row_count=len(rows))
                context.update(file=preview, preview_ready=True, row_count=len(rows), batch=batch, latest_import=None)
            except UnicodeDecodeError:
                form.add_error('file', 'Save the CSV with UTF-8 encoding.')
            except CSVValidationError as exc:
                form.add_error('file', str(exc))
    return render(request, 'csv_app/inspect_csv.html', context)


@transaction.non_atomic_requests
@login_required
@require_POST
@csrf_protect
def csv_upload_view(request):
    try:
        batch_id = uuid.UUID(request.POST.get('batch_id', ''))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'message': 'Inspect a valid CSV file before importing.'}, status=400)
    try:
        batch, duplicate = queue_csv_import(request.user, batch_id)
        count = batch.row_count
    except CSVPreviewExpired as exc:
        return JsonResponse({'message': str(exc)}, status=410)
    except CSVValidationError as exc:
        return JsonResponse({'message': str(exc) + ' No flights were imported.'}, status=400)
    except Http404:
        raise
    except Exception:
        logger.exception('CSV import failed user_id=%s', request.user.pk)
        return JsonResponse({'message': 'Completion could not be confirmed. Retry this same confirmation to check without importing duplicates.'}, status=503)
    payload = csv_import_status_data(batch)
    payload['already_submitted'] = duplicate
    payload['already_completed'] = batch.completed and duplicate
    code = 200 if batch.completed else (503 if batch.status == CSVImportBatch.Status.UNCONFIRMED else
                                       409 if batch.status == CSVImportBatch.Status.FAILED else 202)
    return JsonResponse(payload, status=code)


def csv_import_status_data(batch):
    messages = {
        'preview': 'Your CSV preview is ready to import.',
        'queued': f'Import queued: {batch.row_count} flights. You can leave this page and check back later.',
        'unconfirmed': 'Queue submission could not be confirmed. Check progress here before starting another import.',
        'processing': f'Importing {batch.row_count} flights. Changes will appear together when the import finishes.',
        'completed': f'Import complete: {batch.row_count} flights. Review your aircraft and tailnumber details.',
        'failed': batch.error_message or 'The import could not finish. Upload and inspect the file again.',
    }
    status = CSVImportBatch.Status.COMPLETED if batch.completed else batch.status
    return {
        'status': status, 'row_count': batch.row_count,
        'imported_count': batch.row_count if batch.completed else 0,
        'message': messages[status],
        'status_url': reverse('csv_import_status', args=[batch.pk]),
    }


@login_required
@require_GET
def csv_import_status(request, batch_id):
    from django.shortcuts import get_object_or_404
    batch = get_object_or_404(CSVImportBatch, pk=batch_id, user=request.user)
    response = JsonResponse(csv_import_status_data(batch))
    response['Cache-Control'] = 'no-store'
    return response
