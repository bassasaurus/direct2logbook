import os.path
import sys
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import Flight, Total
from django.core.paginator import Paginator
from django.db.models import Sum

objects = Flight.objects.all()

p = Paginator(objects, 30)

total = Total.objects.get(total='All')

#use Total model to count down using result as previous page and error checking
previous = dict(total_time=total.total_time, pilot_in_command=total.pilot_in_command,
                    second_in_command=total.second_in_command, cross_country=total.cross_country,
                    instructor=total.instructor, dual=total.dual, solo=total.solo, instrument=total.instrument,
                    night=total.night, simulated_instrument=total.simulated_instrument,
                    simulator=total.simulator, landings_day=total.landings_day, landings_night=total.landings_night,
                    landings_total=total.landings_total)

count_up = dict(total=float(), pilot_in_command=float(),
                second_in_command=float(), cross_country=float(),
                instructor=float(), dual=float(), solo=float(), instrument=float(),
                night=float(), simulated_instrument=float(),
                simulator=float(), landings_day=int(), landings_night=int(),
                landings_total=int())

for page_num in p.page_range:

    this_page = dict(total=float(), pilot_in_command=float(),
                    second_in_command=float(), cross_country=float(),
                    instructor=float(), dual=float(), solo=float(), instrument=float(),
                    night=float(), simulated_instrument=float(),
                    simulator=float(), landings_day=int(), landings_night=int(),
                    landings_total=int())

    flights = p.page(page_num).object_list

    for flight in flights:
        # print(flight.date, flight.route, flight.duration, flight.pilot_in_command,
        #         flight.second_in_command, flight.cross_country, flight.instructor, flight.night,
        #         flight.simulated_instrument, flight.simulator, flight.landings_day, flight.landings_night)
        if flight.pilot_in_command:
            this_page['pilot_in_command'] = round(this_page['pilot_in_command'] + flight.duration, 1)
            previous['pilot_in_command'] = round(previous['pilot_in_command'] -  flight.duration, 1)
        count_up['pilot_in_command'] = round(this_page['pilot_in_command'] + previous['pilot_in_command'], 1)
        if flight.second_in_command:
            this_page['second_in_command'] = round(this_page['second_in_command'] + flight.duration, 1)
            previous['second_in_command'] = round(previous['second_in_command'] -  flight.duration, 1)
        count_up['pilot_in_command'] = round(this_page['pilot_in_command'] + previous['pilot_in_command'], 1)

    #calculates totals for each page's fields
    page_total = flights.aggregate(Sum('duration'))
    this_page['total'] = round(page_total.get('duration__sum'), 1)
    previous['total_time'] = round(previous['total_time'] -  page_total.get('duration__sum'), 1)
    #I have no idea why it works like this, but it
    count_up['total'] = round(this_page['total'] + previous['total_time'], 1)

    print('---------------------')
    print('this page', this_page['total'], 'PIC', this_page['pilot_in_command'], 'SIC', this_page['second_in_command'])
    print('previous', previous['total_time'], 'PIC', previous['pilot_in_command'], 'SIC', previous['second_in_command'])
    print('total', count_up['total'], 'PIC', count_up['pilot_in_command'], 'SIC', count_up['second_in_command'])
    print('---------------------')
