
import csv
import io
from flights.models import Flight, Aircraft, TailNumber, Approach
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

    obj = TailNumber.objects.get_or_create(
        user=user, aircraft=aircraft, registration=str(row_2))

    return obj[0]




def csv_import(request, file):

    user = request.user

    # decoded_file = file.read().decode('utf-8')

    io_string = io.StringIO(file)

    next(io_string)  # skips header row

    for row in csv.reader(io_string, delimiter=','):

        # makes any empty entry default to 0
        for n, i in enumerate(row):
            if i == '':
                row[n] = 0

        flight = Flight(
            user=user,
            date=parse(row[0]).strftime("%Y-%m-%d"),
            aircraft_type=addFKAircraft(user, row[1]),
            registration=addFKTailnumber(user, row[1], row[2]),
            route=row[3],
            duration=row[4],
            pilot_in_command=convertBool(row[5]),
            second_in_command=convertBool(row[6]),
            cross_country=convertBool(row[7]),
            night=row[8],
            instrument=row[9],

            landings_day=int(row[11]),
            landings_night=int(row[12]),
            simulated_instrument=row[13],
            instructor=convertBool(row[14]),
            dual=convertBool(row[15]),
            solo=convertBool(row[16]),
            simulator=convertBool(row[17]),
            remarks=row[18],
        )

        flight.save()

        approach = Approach(
            flight_object=flight,
            approach_type='ILS',
            number=row[10]
        )

        approach.save()

        # print(
        #     flight.date,
        #     flight.aircraft_type,
        #     flight.registration,
        #     flight.route,
        #     flight.duration,
        #     flight.pilot_in_command,
        #     flight.second_in_command,
        #     flight.cross_country,
        #     flight.night,
        #     flight.instrument,
        #     # flight.approach,
        #     flight.landings_day,
        #     flight.landings_night,
        #     flight.simulated_instrument,
        #     flight.instructor,
        #     flight.dual,
        #     flight.solo,
        #     flight.simulator,
        #     flight.remarks
        # )
