from flights.models import *
from django.db.models import Sum

def duration_field_aggregate(field, object, Q_query):

    field = Flight.objects.filter(Q_query).aggregate(Sum('duration'))
    if not field.get('duration__sum'):
      object.field = 0
    else:
      object.total_time = field.get('duration__sum')

def boolean_field_aggregate(field, object, Q_query, query_field):

    field = Flight.objects.filter(Q_query, query_field=True).aggregate(Sum('duration'))
    if not field.get('duration__sum'):
      object.field = 0
    else:
      object.field= field.get('duration__sum')

def field_aggregate(field, object, Q_query):

    field = Flight.objects.filter(cat_class_query, field__gt=0).aggregate(Sum(field))
    if not field.get('field__sum'):
      object.field = 0
    else:
      object.field = field.get('field__sum')
