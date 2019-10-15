
import csv
import io
import datetime
from flights.models import Flight, Aircraft, Approach, TailNumber
from dateutil.parser import parse


# converts values, if they exist, to boolean objects


def convertBool(row_id):

    if row_id:
        row_id = True
    else:
        row_id = False
    return row_id

# assigns row_id as aircraft object


def addFKAircraft(row_id, user):
    try:
        obj = Aircraft.objects.filter(user=user).get(aircraft_type=str(row_id))
    except Aircraft.DoesNotExist:
        obj = Aircraft(user=user, aircraft_type=row_id)
        obj.save()
    return obj


def addFKTailnumber(row_id, user):
    try:
        obj = TailNumber.objects.filter(user=user).get(registration=row_id)
    except TailNumber.DoesNotExist:
        obj = TailNumber(user=user, registration=row_id)
        obj.save()
    return obj


def import_csv(request):
    user = request.user

    file = request.FILES['file']

    decoded_file = file.read().decode('utf-8')

    io_string = io.StringIO(decoded_file)

    next(io_string) #skips header row

    for row in csv.reader(io_string, delimiter=','):

        # makes any empty entry default to 0
        for n, i in enumerate(row):
            if i == '':
                row[n] = 0

        flight = Flight(
            user=user,
            date=parse(row[0]),
            aircraft=addFKAircraft(user, row[1]),
            registration=addFKTailnumber(user, row[2]),
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

        print(flight.date, flight.route)

        # flight.save()
