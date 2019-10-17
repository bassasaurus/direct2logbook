from django.shortcuts import render
import csv
from django.http import HttpResponseRedirect, HttpResponse
from django.template.response import TemplateResponse
from django import forms
from flights.models import Flight
from csv_app.csvimport import import_csv
import csv
import io


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
        # appr
        # hold
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
            # appr
            # hold
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


class UploadFileForm(forms.Form):
    file = forms.FileField()


def csv_inspect_view(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():

            # import_csv(request)

            file = request.FILES['file']

            decoded_file = file.read().decode('utf-8')

            io_string = io.StringIO(decoded_file)

            next(io_string) #skips header row

            file = csv.reader(io_string, delimiter=',')

            {'file' : file}

            return TemplateResponse(request, 'csv_app/inspect_csv.html', {'file' : file })
    else:
        form = UploadFileForm()
    return render(request, 'csv_app/inspect_csv.html', {'form': form})


def csv_upload_view(request):

    return render(request, 'csv_app/upload_csv.html')
