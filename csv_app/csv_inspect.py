
import csv
import io
import datetime
from flights.models import Flight, Aircraft, Approach, TailNumber
from dateutil.parser import parse

def format_route(field):

    return field

def check_decimal(field):

    return field

def csv_inspect(file):

    new_file = io.StringIO()
    writer = csv.writer(new_file, delimiter=',')

    for row in file:
        writer.writerow([
            row[0],
            row[1],
            row[2],
        ])

    return(new_file)
