import os.path
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

import csv

from flights.models import MapData

def dms2dd(degrees, minutes, seconds, direction):

    dd = float(degrees) + float(minutes)/60 + float(seconds)/(60*60);
    if direction == 'W' or direction == 'S':
        dd *= -1
    return dd

def parse(row):
    #format 60-54-10.4300N
    coords = row.split('-')
    #slice to seperate
    degrees = coords[0]
    minutes = coords[1]
    seconds = coords[2]
    #get direction from lat_seconds 4000N
    direction = seconds[-1]
    #remove letter
    seconds = seconds[:-1]

    digital_degrees = dms2dd(degrees, minutes, seconds, direction)

    return digital_degrees

#os agnostic file path
userhome = os.path.expanduser('~')
faa_db = os.path.join(userhome, 'django_/direct2/', 'faa.csv')
with open(faa_db, 'r') as data:

    reader = csv.reader(data)
    # next(reader) # skips header
    for row in reader:
        map_data = MapData(
            name = row[0],
            city = row[1],
            state = row[2],
            country = row[3],
            iata = row[4].strip("'"),
            icao = row[5],

            latitude = parse(row[6]),
            longitude = parse(row[7]),

            elevation = row[8],
        )
        # map_data.save()
        # print(map_data.iata)

icao = MapData.objects.values_list('icao', flat=True)
iata = MapData.objects.values_list('iata', flat=True)

world_db = os.path.join(userhome, 'django_/direct2/', 'openflightsdb.csv')
with open(world_db, 'r', encoding = "ISO-8859-1") as data:

    reader = csv.reader(data)
    # next(reader) # skips header

    for row in reader:
        if row[2] == 'United States':
            pass
        else:
            mapdata = MapData(
                name = row[0],
                city = row[1],
                country = row[2],
                iata = row[3],
                icao = row[4],
                latitude = row[5],
                longitude = row[6],
                elevation = row[7],
            )
            mapdata.save()

            # print(row[3], row[4])
            # print(mapdata.name, mapdata.iata, mapdata.icao)
