value_to_update = Total.objects.get(total='AMEL')
query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
field = Model.field

def field_duration_update(value_to_update, query, field, **kwargs):

    kwargs{value_to_update:'value_to_update', query:'query', field:'field'}

    field = Flight.objects.filter(query).aggregate(Sum('duration'))
    if not field.get('duration__sum'):
      value_to_update.field = 0
    else:
      value_to_update.total_time = field.get('duration__sum')
