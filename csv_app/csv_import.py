
import csv
import io
from flights.models import Flight, Aircraft, TailNumber, Approach
from dateutil.parser import parse

# converts values, if they exist, to boolean objects


def assign_ils(row_id):
    if row_id > 0:
        return 'ILS'
    else:
        return 'None'


def convertBool(row_id):

    if float(row_id) > 0:
        return True
    else:
        return False


def csv_import(request, file):

    user = request.user

    io_string = io.StringIO(file)
    next(io_string)  # skips header row

    flight_object_list = []

    for row in csv.reader(io_string, delimiter=','):

        # makes any empty entry default to 0
        for n, i in enumerate(row):
            if i == '':
                row[n] = 0

        if Aircraft.objects.filter(user=user, aircraft_type=row[1]).exists():
            pass

        else:
            Aircraft.objects.create(user=user, aircraft_type=str(row[1]))

        if TailNumber.objects.filter(user=user, registration=row[2]).exists():
            pass

        else:
            aircraft = Aircraft.objects.get(user=user, aircraft_type=row[1])
            TailNumber.objects.create(
                user=user, aircraft=aircraft, registration=str(row[2]))

        aircraft_type = Aircraft.objects.get(user=user, aircraft_type=str(row[1]))
        registration = TailNumber.objects.get(user=user, registration=str(row[2]))

        flight = Flight(
            user=user,
            date=parse(row[0]).strftime("%Y-%m-%d"),
            aircraft_type=aircraft_type,
            registration=registration,
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

        flight_object_list.append(flight)

        # approach = Approach(
        #     flight_object=flight,
        #     approach_type=assign_ils(row[10]),
        #     number=row[10]
        # )
        #
        # approach.save()

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
    Flight.objects.bulk_create(flight_object_list)
