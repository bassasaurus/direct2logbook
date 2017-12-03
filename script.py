import os.path
import sys
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import Flight, TailNumber, Aircraft

flight = Flight()
tailnumber = TailNumber()
aircraft = Aircraft()

tailqueryset = TailNumber.objects.all()
flightqueryset = Flight.objects.all()
aircraftqueryset = Aircraft.objects.all()


# add aircraft type to existing tailnumber
# for i in flightqueryset:

# 	aircraft_obj = Aircraft.objects.get(pk=i.aircraft.pk)
# 	tail_obj = TailNumber.objects.get(pk=i.registration.pk)
	
# 	tail_obj.aircraft = aircraft_obj
# 	tail_obj.save()
# 	print(tail_obj)


for item in tailqueryset:
	if (str(item.aircraft)) == 'PA28-200': #change string value for different aircraft types
		item.is_91 = True #change for different operations
		item.save()

