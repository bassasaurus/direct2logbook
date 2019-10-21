
import csv
import io
import datetime
from flights.models import Flight, Aircraft, Approach, TailNumber
from dateutil.parser import parse


# converts values, if they exist, to boolean objects


def convertBool(row_id):

    if float(row_id) > 0:
        return True
    else:
        return False


def addFKAircraft(user, row_id):

    obj = Aircraft.objects.get_or_create(user=user, aircraft_type=str(row_id))

    return obj[0]


def addFKTailnumber(user, row_1, row_2):

    aircraft = Aircraft.objects.get(user=user, aircraft_type=str(row_1))

    obj = TailNumber.objects.get_or_create(user=user, aircraft=aircraft, registration=str(row_2))

    return obj[0]


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
            date=parse(row[0]).strftime("%Y-%d-%m"),
            # aircraft_type=addFKAircraft(user, row[1]),
            # registration=addFKTailnumber(user, row[1], row[2]),
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

        print(
            flight.date,
            flight.aircraft_type,
            flight.registration,
            flight.route,
            flight.duration,
            flight.pilot_in_command,
            flight.second_in_command,
            flight.cross_country,
            flight.night,
            flight.instrument,
            flight.landings_day,
            flight.landings_night,
            flight.simulated_instrument,
            flight.instructor,
            flight.dual,
            flight.solo,
            flight.simulator,
            flight.remarks
            )

        # flight.save()
