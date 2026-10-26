from django.shortcuts import render, reverse, redirect
import csv
from django.http import HttpResponse, JsonResponse, Http404
from django import forms
from flights.models import Flight
from csv_app.csv_import import confirm_csv_import
from .models import CSVImportBatch
import uuid
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.db.models import Sum
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
                context.update(file=preview, preview_ready=True, row_count=len(rows), batch=batch)
            except UnicodeDecodeError:
                form.add_error('file', 'Save the CSV with UTF-8 encoding.')
            except CSVValidationError as exc:
                form.add_error('file', str(exc))
    return render(request, 'csv_app/inspect_csv.html', context)


@login_required
@require_POST
@csrf_protect
def csv_upload_view(request):
    try:
        batch_id = uuid.UUID(request.POST.get('batch_id', ''))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'message': 'Inspect a valid CSV file before importing.'}, status=400)
    try:
        batch, duplicate = confirm_csv_import(request, batch_id)
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
    return JsonResponse({'status': 'completed', 'row_count': count, 'already_completed': duplicate,
                         'message': f'Import complete: {count} flights. Review your aircraft and tailnumber details.'})
