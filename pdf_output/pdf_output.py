from flights.models import Flight
from django.core.paginator import Paginator
from django.db.models import Sum
from django.core.cache import cache
import numbers

from datetime import datetime

import copy

def strip_all(string):
    string = str(string).replace("'","").strip("[").strip("]").replace(",","")
    return string

def make_table_row(iterable):
    list = []
    text = 'text'
    number = 'number'
    for i in iterable:
        if isinstance(i, numbers.Number) or i == '-':
            i = '<td ' + 'class="' + number + '"' + '>' + str(i) + "</td>"
        else:
            i = '<td ' + 'class="' + text + '"' + '>' + str(i) + "</td>"
        list.append(i)
        row = str(strip_all(list))
    return strip_all(row)

def pdf_output(objects):

    template = dict(total=0, pilot_in_command=0,
                    second_in_command=0, cross_country=0,
                    instructor=0, dual=0, solo=0, instrument=0,
                    night=0, simulated_instrument=0,
                    simulator=0, landings_day=0, landings_night=0,
                    landings_total=0, remarks = '')

    #clears contents of previously generated file
    file = open('pdf_output/templates/pdf_output/log_table.html', 'w')
    file.write('')

    file.close()

    p = Paginator(objects, 25)

    previous = copy.copy(template)

    total = copy.copy(template)

    for page_num in p.page_range:

        this_page = copy.copy(template)

        flights = p.page(page_num).object_list

        file = open('pdf_output/templates/pdf_output/log_table.html', 'a')
        file.write('<table class="table-striped">')

        file.write(strip_all("""<thead><th class="text">Date</th><th class="text">Type</th><th class="text">Reg</th>
        <th class="text">Route</th><th colspan="" class="number">Duration</th><th class="number">PIC</th><th class="number">SIC</th><th class="number">X Country</th><th class="number">CFI</th>
          <th class="number">Dual</th><th class="number">Solo</th><th class="number">Night</th><th class="number">Sim Inst</th>
          <th class="number">Day Ldg</th><th class="number">Night Ldg</th></thead>""") + '\n')

        # file.write(strip_all("""<tr><td colspan="4"></td><td class="number">Single</td><td class="number">Multi</td></tr>""") + '\n')
        for flight in flights:

            log_list = []

            row = copy.copy(template)

            this_page['total'] = round(this_page['total'] + flight.duration, 1)
            #field dependent
            if flight.pilot_in_command:
                this_page['pilot_in_command'] = round(this_page['pilot_in_command'] + flight.duration, 1)
                row['pilot_in_command'] = flight.duration
            else:
                row['pilot_in_command'] = '-'
            if flight.second_in_command:
                this_page['second_in_command'] = round(this_page['second_in_command'] + flight.duration, 1)
                row['second_in_command'] = flight.duration
            else:
                row['second_in_command'] = '-'
            if flight.cross_country:
                this_page['cross_country'] = round(this_page['cross_country'] + flight.duration, 1)
                row['cross_country'] = flight.duration
            else:
                row['cross_country'] = '-'
            if flight.instructor:
                this_page['instructor'] = round(this_page['instructor'] + flight.duration, 1)
                row['instructor'] = flight.duration
            else:
                row['instructor'] = '-'
            if flight.dual:
                this_page['dual'] = round(this_page['dual'] + flight.duration, 1)
                row['dual'] = flight.duration
            else:
                row['dual'] = '-'
            if flight.solo:
                this_page['solo'] = round(this_page['solo'] + flight.duration, 1)
                row['solo'] = flight.duration
            else:
                row['solo'] = '-'
            if not flight.night:
                row['night'] = '-'
            else:
                this_page['night'] = round(this_page['night'] + flight.night, 1)
                row['night'] = flight.night
            if not flight.simulated_instrument:
                row['simulated_instrument'] = '-'
            else:
                this_page['simulated_instrument'] = round(this_page['simulated_instrument'] + flight.simulated_instrument, 1)
                row['simulated_instrument'] = flight.simulated_instrument
            if not flight.landings_day:
                row['landings_day'] = '-'
            else:
                this_page['landings_day'] = round(this_page['landings_day'] + flight.landings_day, 1)
                row['landings_day'] = flight.landings_day
            if not flight.landings_night:
                row['landings_night'] = '-'
            else:
                this_page['landings_night'] = round(this_page['landings_night'] + flight.landings_night, 1)
                row['landings_night'] = flight.landings_night
            if not flight.simulator:
                row['simulator'] = '-'
            else:
                this_page['simulator'] = round(this_page['simulator'] + flight.simulator, 1)
                row['simulator'] = flight.simulator
            if not flight.remarks:
                remarks = ''
            else:
                row['remarks'] = flight.remarks

            date = flight.date.strftime("%m-%d-%Y")

            '''
                add this to log_line:
                {% for approach in flight.approach_set.all %}
                    <small>{{ approach.approach_type }}-{{ approach.number }}</small>
                {% endfor %}
            '''
            log_line = (date, flight.aircraft_type, flight.registration, flight.route, flight.duration, row['pilot_in_command'],
                    row['second_in_command'], row['cross_country'], row['instructor'], row['dual'], row['solo'], row['night'],
                    row['simulated_instrument'], row['landings_day'], row['landings_night'])

            log_line = "<tr>" + make_table_row(log_line) + "</tr>"

            file.write(log_line + '\n')

        total['total'] = round(this_page['total'] + total['total'], 1)
        total['pilot_in_command'] = round(this_page['pilot_in_command'] + total['pilot_in_command'], 1)
        total['second_in_command'] = round(this_page['second_in_command'] + total['second_in_command'], 1)
        total['cross_country'] = round(this_page['cross_country'] + total['cross_country'], 1)
        total['instructor'] = round(this_page['instructor'] + total['instructor'], 1)
        total['dual'] = round(this_page['dual'] + total['dual'], 1)
        total['solo'] = round(this_page['solo'] + total['solo'], 1)
        total['night'] = round(this_page['night'] + total['night'], 1)
        total['simulated_instrument'] = round(this_page['simulated_instrument'] + total['simulated_instrument'], 1)
        total['landings_day'] = round(this_page['landings_day'] + total['landings_day'], 1)
        total['landings_night'] = round(this_page['landings_night'] + total['landings_night'], 1)

        previous['total'] = round(total['total'] - this_page['total'], 1)
        previous['pilot_in_command'] = round(total['pilot_in_command'] - this_page['pilot_in_command'], 1)
        previous['second_in_command'] = round(total['second_in_command'] - this_page['second_in_command'], 1)
        previous['cross_country'] = round(total['cross_country'] - this_page['cross_country'], 1)
        previous['instructor'] = round(total['instructor'] - this_page['instructor'], 1)
        previous['dual'] = round(total['dual'] - this_page['dual'], 1)
        previous['solo'] = round(total['solo'] - this_page['solo'], 1)
        previous['night'] = round(total['night'] - this_page['night'], 1)
        previous['simulated_instrument'] = round(total['simulated_instrument'] - this_page['simulated_instrument'], 1)
        previous['landings_day'] = round(total['landings_day'] - this_page['landings_day'], 1)
        previous['landings_night'] = round(total['landings_night'] -this_page['landings_night'], 1)


        this_page_footer = ('This Page', this_page['total'], this_page['pilot_in_command'], this_page['second_in_command'], this_page['cross_country'], this_page['instructor'], this_page['dual'], this_page['solo'], this_page['night'], this_page['simulated_instrument'], this_page['landings_day'], this_page['landings_night'])
        this_page_footer = '<tr><td style="border: 0px" colspan="3"></td>' + make_table_row(this_page_footer) + '</tr>'
        file.write(this_page_footer + '\n')

        previous_footer = ('Previous', previous['total'], previous['pilot_in_command'], previous['second_in_command'], previous['cross_country'], previous['instructor'], previous['dual'], previous['solo'], previous['night'], previous['simulated_instrument'], previous['landings_day'], previous['landings_night'])
        previous_footer = '<tr><td style="border: 0px" colspan="3"></td>' + make_table_row(previous_footer) + '</tr>'
        file.write(previous_footer + '\n')

        total_footer = ('Total', total['total'], total['pilot_in_command'], total['second_in_command'], total['cross_country'], total['instructor'], total['dual'], total['solo'], total['night'], total['simulated_instrument'], total['landings_day'], total['landings_night'])
        total_footer = '<tr><td style="border: 0px" colspan="3"></td>' + make_table_row(total_footer) + '</tr>'
        file.write(total_footer + '\n')

        file.write("</table>")
    file.close()
