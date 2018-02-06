from flights.models import MapData, Flight, TailNumber, Aircraft
import re
from django.db.models import Q



def tailnumber_reg_error(queryset):

    error_list = []

    for tail in queryset:
        data =  (tail.is_121, tail.is_135, tail.is_91)
        if not any(data):
            kwargs = {'registration': tail}
            error_list.append(TailNumber.objects.get(**kwargs))

    return(error_list)

def tailnumber_aircraft_error(queryset):

    error_list = []

    for tail in queryset:
        if not tail.aircraft:
            error_list.append(tail)

    return error_list

def aircraft_power_error(queryset):
        error_list = []

        for aircraft in queryset:
            data =  (aircraft.piston, aircraft.turbine)
            if not any(data):
                kwargs = {'aircraft_type': aircraft}
                error_list.append(Aircraft.objects.get(**kwargs))

        return(error_list)

def aircraft_weight_error(queryset):
    error_list = []

    for aircraft in queryset:
        data =  (aircraft.superr, aircraft.heavy, aircraft.large, aircraft.medium, aircraft.small)
        if not any(data):
            kwargs = {'aircraft_type': aircraft}
            error_list.append(Aircraft.objects.get(**kwargs))

    return(error_list)

def aircraft_endorsement_error(queryset):
    error_list = []

    for aircraft in queryset:
        data =  (aircraft.simple, aircraft.high_performance, aircraft.compleks, aircraft.tailwheel, aircraft.requires_type)
        if not any(data):
            kwargs = {'aircraft_type': aircraft}
            error_list.append(Aircraft.objects.get(**kwargs))

    return(error_list)

def aircraft_category_error(queryset):
    error_list = []

    for aircraft in queryset:
        if not aircraft.aircraft_category:
            kwargs = {'aircraft_type': aircraft}
            error_list.append(Aircraft.objects.get(**kwargs))

    return(error_list)

def aircraft_class_error(queryset):
    error_list = []

    for aircraft in queryset:
        if not aircraft.aircraft_class:
            kwargs = {'aircraft_type': aircraft}
            error_list.append(Aircraft.objects.get(**kwargs))

    return(error_list)

def flight_aircraft_error(queryset):
    error_list = []

    for flight in queryset:
        if not flight.aircraft_type:
            kwargs = {'pk': flight.pk}
            error_list.append(Flight.objects.get(**kwargs))

    return(error_list)

def flight_tailnumber_error(queryset):
    error_list = []

    for flight in queryset:
        if not flight.registration:
            kwargs = {'pk': flight.pk}
            error_list.append(Flight.objects.get(**kwargs))

    return(error_list)

def flight_role_error(queryset):
    error_list = []

    for flight in queryset:
        if not flight.pilot_in_command and not flight.second_in_command and not flight.dual and not flight.instructor:
            kwargs = {'pk': flight.pk}
            error_list.append(Flight.objects.get(**kwargs))

    return(error_list)

def flight_cross_country_error(queryset):
    error_list = []

    for flight in queryset:
        if flight.duration >3.0 and not flight.cross_country:
            kwargs = {'pk': flight.pk}
            error_list.append(Flight.objects.get(**kwargs))

    return(error_list)
