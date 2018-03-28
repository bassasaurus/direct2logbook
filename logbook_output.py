import os.path
import sys
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import Flight, Total
from django.core.paginator import Paginator
from django.db.models import Sum

objects = Flight.objects.filter().order_by('date')

p = Paginator(objects, 30)

total = dict(total=0, pilot_in_command=0,
                second_in_command=0, cross_country=0,
                instructor=0, dual=0, solo=0, instrument=0,
                night=0, simulated_instrument=0,
                simulator=0, landings_day=0, landings_night=0,
                landings_total=0)

previous = dict(total=0, pilot_in_command=0,
                second_in_command=0, cross_country=0,
                instructor=0, dual=0, solo=0, instrument=0,
                night=0, simulated_instrument=0,
                simulator=0, landings_day=0, landings_night=0,
                landings_total=0)

for page_num in p.page_range:

    this_page = dict(total=0, pilot_in_command=0,
                    second_in_command=0, cross_country=0,
                    instructor=0, dual=0, solo=0, instrument=0,
                    night=0, simulated_instrument=0,
                    simulator=0, landings_day=0, landings_night=0,
                    landings_total=0)

    flights = p.page(page_num).object_list

    for flight in flights:

        row = dict(total=0, pilot_in_command=0,
                        second_in_command=0, cross_country=0,
                        instructor=0, dual=0, solo=0, instrument=0,
                        night=0, simulated_instrument=0,
                        simulator=0, landings_day=0, landings_night=0,
                        landings_total=0)

        this_page['total'] = round(this_page['total'] + flight.duration, 1)
        #field dependent
        if flight.pilot_in_command:
            this_page['pilot_in_command'] = round(this_page['pilot_in_command'] + flight.duration, 1)
            row['pilot_in_command'] = flight.duration
        if flight.second_in_command:
            this_page['second_in_command'] = round(this_page['second_in_command'] + flight.duration, 1)
            row['second_in_command'] = flight.duration
        if flight.cross_country:
            this_page['cross_country'] = round(this_page['cross_country'] + flight.duration, 1)
            row['cross_country'] = flight.duration

        print(flight.date, flight.route, flight.aircraft_type, flight.registration, flight.duration, row['pilot_in_command'],
                row['second_in_command'], row['cross_country'], flight.instructor, flight.night,
                flight.simulated_instrument, flight.simulator, flight.landings_day, flight.landings_night)

    total['total'] = round(this_page['total'] + total['total'], 1)
    total['pilot_in_command'] = round(this_page['pilot_in_command'] + total['pilot_in_command'], 1)
    total['second_in_command'] = round(this_page['second_in_command'] + total['second_in_command'], 1)
    total['cross_country'] = round(this_page['cross_country'] + total['cross_country'], 1)

    previous['total'] = round(total['total'] - this_page['total'], 1)
    previous['pilot_in_command'] = round(total['pilot_in_command'] - this_page['pilot_in_command'], 1)
    previous['second_in_command'] = round(total['second_in_command'] - this_page['second_in_command'], 1)
    previous['cross_country'] = round(total['cross_country'] - this_page['cross_country'], 1)

    print('---------------------')
    print('this page', this_page['total'], 'PIC', this_page['pilot_in_command'], 'SIC', this_page['second_in_command'], 'XC', this_page['cross_country'])
    print('previous', previous['total'], 'PIC', previous['pilot_in_command'], 'SIC', previous['second_in_command'], 'XC',previous['cross_country'])
    print('total', total['total'], 'PIC', total['pilot_in_command'], 'SIC', total['second_in_command'], 'XC', total['cross_country'])
    print('---------------------')
