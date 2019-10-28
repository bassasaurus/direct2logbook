
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
    writer = csv.writer(new_file)

    for row in file:
        writer.writerow([
            str(row[0]),
            str(row[1]),
            str(row[2])
        ])

    new_file.seek(0, 0)  # gives reader a place to start
    new_csv = csv.reader(new_file, delimiter=',')

    for i in new_csv:
        print(i)

    return(new_file)
