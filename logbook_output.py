import os.path
import sys
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import Flight
from django.core.paginator import Paginator
from django.db.models import Sum

objects = Flight.objects.all()

p = Paginator(objects, 20)

aggregate_total = 0

for i in p.page_range:

    records = p.page(i).object_list

    total = records.aggregate(Sum('duration'))
    page_total = round(total.get('duration__sum'), 1)

    aggregate_total = round((page_total + aggregate_total), 1)

    for record in records:
        print(record.date, record.route, record.duration)

    print( "page ", i, page_total)
    print("aggregate total ", aggregate_total)
    print("--------------------------")
