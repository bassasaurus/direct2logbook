import os.path
import sys
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import Flight, Total
from django.core.paginator import Paginator
from django.db.models import Sum

objects = Flight.objects.all()

p = Paginator(objects, 20)

total_time = Flight.objects.all().aggregate(Sum('duration'))
total_time = round(total_time.get('duration__sum'), 1)

for page_num in p.page_range:

    records = p.page(page_num).object_list
    #calculates each page's total duration
    this_page = records.aggregate(Sum('duration'))
    this_page = round(this_page.get('duration__sum'), 1)

    '''subtracts 'this_page' from 'total_time' each iteration to get 'previous_page'
        to arrive at zero value for 'previous_page' on last page *first to last'''
    previous_page = round(total_time - this_page, 1)

    #rebuilds forwarded total from *last to first
    count_up = round(this_page + total_time, 1)

    for record in records:
        print(record.date, record.route, record.duration)

    print("this page ", page_num, round(this_page, 1))
    print("previous page ", round(previous_page, 1))
    print("total         ", count_up)
    print("--------------------------")
