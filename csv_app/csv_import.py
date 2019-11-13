
import csv
import io
from flights.models import Flight, Aircraft, TailNumber, MapData, Approach
from dateutil.parser import parse
import re


def assign_ils(row_id):
    if row_id > 0:
        return 'ILS'
    else:
        return ''


def convertBool(row_id):

    if float(row_id) > 0:
        return True
    else:
        return False


def save_route_data(user, route):

    route_data = []
    route = re.split('\W+', route)  # separate individual codes

    icao = MapData.objects.values_list('icao', flat=True)
    iata = MapData.objects.values_list('iata', flat=True)

    for code in route:  # XXXX, XXXX, XXXX
        code = code.upper()
        if code not in icao and code not in iata:
            pass
        else:
            iata_kwargs = {'iata': code}
            icao_kwargs = {'icao': code}
            map_object = (MapData.objects.filter(**iata_kwargs) | MapData.objects.filter(**icao_kwargs)).first()
        route_data.append(map_object)

    return route_data


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

        route_data = save_route_data(user, row[3])

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
            route_data=route_data,
        )

        flight_object_list.append(flight)

        flight.save()

        print(flight.date, flight.route, flight.route_data)

        approach = Approach(
            flight_object=flight,
            approach_type=assign_ils(row[10]),
            number=row[10]
        )

        approach.save()

    # Flight.objects.bulk_create(flight_object_list)
