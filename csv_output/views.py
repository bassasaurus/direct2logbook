from django.shortcuts import render
import csv
from django.http import HttpResponse
from flights.models import Flight

def csv_view(request):
    user = request.user
    # Create the HttpResponse object with the appropriate CSV header.

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}_{}_logbook.csv"'.format(user.first_name, user.last_name)

    flights = Flight.objects.filter(user=user)
    writer = csv.writer(response)
    writer.writerow([
                'date',
                'aircraft',
                'registration',
                'duration',
                'route',
                'pilot in command',
                'second in command',
                'cross country',
                'night',
                'instrument',
                ])

    for flight in flights:

        if flight.pilot_in_command:
            pic = str(flight.duration)
        else:
            pic = 0

        if flight.second_in_command:
            sic = str(flight.duration)
        else:
            sic = 0

        if flight.cross_country:
            xc = str(flight.duration)
        else:
            xc = 0

        if not flight.night:
            night = 0
        else:
            night = flight.night

        if not flight.instrument:
            inst = 0
        else:
            inst = flight.instrument

        writer.writerow([
                str(flight.date),
                str(flight.aircraft_type),
                str(flight.registration),
                str(flight.duration),
                str(flight.route),
                str(pic),
                str(sic),
                str(xc),
                str(night),
                str(inst),

                ])

    return response
