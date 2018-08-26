from flights.models import Flight, Aircraft, Total
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime

today = datetime.date.today()

cat_class = {
    'all': Total.objects.get(total='ALL'),
    'asel': Total.objects.get(total='ASEL'),
    'amel': Total.objects.get(total='AMEL'),
    'ases': Total.objects.get(total='ASES'),
    'ames': Total.objects.get(total='AMES'),
    'helo': Total.objects.get(total='HELO'),
    'gyro': Total.objects.get(total='GYRO'),
    'test': Total.objects.get(total="TEST")
    }

asel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
amel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
helo_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'helicopter') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'rotorcraft')
gyro_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'gyroplane') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'rotorcraft')


def aggregate_field_value(cat_class, query, field):
    kwargs = {'cat_class' : cat_class, 'query': query, 'field': field}

    object = cat_class[cat_class]

    field = Flight.objects.filter(cat_class_query).aggregate(Sum('duration'))
    if not field.get('duration__sum'):
      object.field = 0
    else:
      object.field = round(field.get('duration__sum'),1)

      cat_class.save()

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def total_updater(sender, **kwargs):
    print('total_updater')
    boolean_fields = ['pilot_in_command', 'second_in_command', 'cross_country',
    'instructor', 'dual', 'solo', 'simulator']

    float_fields = ['total_time', 'instrument', 'simulated_instrument', 'night']

    for field in float_fields:
        aggregate_field_value(cat_class['TEST'], amel_query, field)
