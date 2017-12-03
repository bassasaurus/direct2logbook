import os.path
import sys
import csv
import django
import datetime

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import MapData


#os agnostic file path
userhome = os.path.expanduser('~')
path = os.path.join(userhome, 'django_/direct2/', 'openflightsdb.csv')
with open(path, 'r') as data:

    reader = csv.reader(data)
    # next(reader) # skips header

    for row in reader: # iterates rows

        mapdata = MapData(
            airport_id = row[0],
            name = row[1],
            city = row[2],
            country = row[3],
            iata = row[4],
            icao = row[5],
            latitude = row[6],
            longitude = row[7],
            altitude = row[8],
        )
        mapdata.save()
