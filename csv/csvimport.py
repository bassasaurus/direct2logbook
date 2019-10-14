import os.path
import sys
import csv
import django
import datetime

from flights.models import Flight, Aircraft, Approach, TailNumber

# converts values, if they exist, to boolean objects


def convertBool(row_id):

    if row_id:
        row_id = True
    else:
        row_id = False
    return row_id

# assigns row_id as aircraft object


def addFKAircraft(row_id):
    try:
        obj = Aircraft.objects.get(aircraft_type=row_id)
    except Aircraft.DoesNotExist:
        obj = Aircraft(aircraft_type=row_id)
        obj.save()
    return obj


def addFKTailnumber(row_id):
    try:
        obj = TailNumber.objects.get(registration=row_id)
    except TailNumber.DoesNotExist:
        obj = TailNumber(registration=row_id)
        obj.save()
    return obj


# os agnostic file path
userhome = os.path.expanduser('~')
path = os.path.join(userhome, 'django_/logbook/', 'logbook_current.csv')
with open(path, 'r') as logbook:

    reader = csv.reader(logbook)
    next(reader)  # skips header

    for row in reader:  # iterates rows

        # date to python datetime object
        date = datetime.datetime.strptime(row[0], '%m/%d/%Y').date()
        row[0] = date

        # makes any empty entry default to 0
        for n, i in enumerate(row):
            if i == '':
                row[n] = 0

        aircraft = addFKAircraft(row[1])

        tailnumber = addFKTailnumber(row[2])

        flight = Flight(
            date=row[0],
            aircraft=aircraft,
            registration=tailnumber,
            route=row[3],
            duration=row[4],
            pilot_in_command=convertBool(row[5]),
            second_in_command=convertBool(row[6]),
            cross_country=convertBool(row[7]),
            night=row[8],
            instrument=row[9],
            landings_day=int(row[10]),
            landings_night=int(row[11]),
            simulated_instrument=row[12],
            instructor=convertBool(row[13]),
            dual=convertBool(row[14]),
            solo=convertBool(row[15]),
            simulator=convertBool(row[16]),
            remarks=row[17],

        )
        flight.save()
