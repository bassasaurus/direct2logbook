from flights.models import *
from accounts.models import Profile
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
from django.core.exceptions import ObjectDoesNotExist
from django.dispatch import receiver
from flights.queryset_helpers import *

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def weight_update(sender, instance, **kwargs):

    user = instance.user

    flight = Flight.objects.filter(user=user)
    imported = Imported.objects.filter(user=user)

    superr_query = Q(aircraft_type__superr=True)
    heavy_query = Q(aircraft_type__heavy=True)
    large_query = Q(aircraft_type__large=True)
    medium_query = Q(aircraft_type__medium=True)
    small_query = Q(aircraft_type__small=True)
    # lsa_query = Q(aircraft_type__lsa=True)

    if not flight.filter(superr_query) and not imported.filter(superr_query):
        pass
    else:
        superr = Weight.objects.get_or_create(user=user, weight='Super')[0]
        superr.total = avoid_none(flight.filter(superr_query), 'duration') + avoid_none(imported.filter(superr_query), 'total_time')
        superr.save()

    if not flight.filter(heavy_query) and not imported.filter(heavy_query):
        pass
    else:
        heavy = Weight.objects.get_or_create(user=user, weight='Heavy')[0]
        heavy.total = avoid_none(flight.filter(heavy_query), 'duration') + avoid_none(imported.filter(heavy_query), 'total_time')
        heavy.save()

    if not flight.filter(large_query) and not imported.filter(large_query):
        pass
    else:
        large = Weight.objects.get_or_create(user=user, weight='Large')[0]
        large.total = avoid_none(flight.filter(large_query), 'duration') + avoid_none(imported.filter(large_query), 'total_time')
        large.save()

    if not flight.filter(large_query) and not imported.filter(large_query):
        pass
    else:
        large = Weight.objects.get_or_create(user=user, weight='Large')[0]
        large.total = avoid_none(flight.filter(large_query), 'duration') + avoid_none(imported.filter(large_query), 'total_time')
        large.save()

    if not flight.filter(medium_query) and not imported.filter(medium_query):
        pass
    else:
        medium = Weight.objects.get_or_create(user=user, weight='Medium')[0]
        medium.total = avoid_none(flight.filter(medium_query), 'duration') + avoid_none(imported.filter(medium_query), 'total_time')
        medium.save()

    if not flight.filter(small_query) and not imported.filter(small_query):
        pass
    else:
        small = Weight.objects.get_or_create(user=user, weight='Small')[0]
        small.total = avoid_none(flight.filter(small_query), 'duration') + avoid_none(imported.filter(small_query), 'total_time')
        small.save()

    # if not flight.filter(lsa_query) and not imported.filter(lsa_query):
    #     pass
    # else:
    #     lsa = Weight.objects.get_or_create(user=user, weight='LSA')[0]
    #     lsa.total = avoid_none(flight.filter(lsa_query), 'duration') + avoid_none(imported.filter(lsa_query), 'total_time')
    #     lsa.save()

@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def regs_update(sender, instance, **kwargs):

    user = instance.user

    flight = Flight.objects.filter(user=user)
    imported = Imported.objects.filter(user=user)

    airline_query = Q(registration__is_121=True)
    charter_query = Q(registration__is_135=True)
    private_query = Q(registration__is_91=True)

    if not flight.filter(pilot_in_command=True).filter(airline_query):
        pass
    else:
        airline_pic = Regs.objects.get_or_create(user=user, reg_type='121')[0]
        airline_pic.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True).filter(airline_query), 'duration') + avoid_none(imported.filter(is_121=True), 'pilot_in_command')
        airline_pic.save()

    if not flight.filter(second_in_command=True).filter(airline_query):
        pass
    else:
        airline_sic = Regs.objects.get_or_create(user=user, reg_type='121')[0]
        airline_sic.second_in_command = avoid_none(flight.filter(second_in_command=True).filter(airline_query), 'duration') + avoid_none(imported.filter(is_121=True), 'second_in_command')
        airline_sic.save()

    if not flight.filter(pilot_in_command=True).filter(charter_query):
        pass
    else:
        charter_pic = Regs.objects.get_or_create(user=user, reg_type='135')[0]
        charter_pic.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True).filter(charter_query), 'duration') + avoid_none(imported.filter(is_135=True), 'pilot_in_command')
        charter_pic.save()

    if not flight.filter(second_in_command=True).filter(charter_query):
        pass
    else:
        charter_sic = Regs.objects.get_or_create(user=user, reg_type='135')[0]
        charter_sic.second_in_command = avoid_none(flight.filter(second_in_command=True).filter(charter_query), 'duration') + avoid_none(imported.filter(is_135=True), 'second_in_command')
        charter_sic.save()

    if not flight.filter(pilot_in_command=True).filter(private_query):
        pass
    else:
        private_pic = Regs.objects.get_or_create(user=user, reg_type='91')[0]
        private_pic.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True).filter(private_query), 'duration') + avoid_none(imported.filter(is_91=True), 'pilot_in_command')
        private_pic.save()

    if not flight.filter(second_in_command=True).filter(private_query):
        pass
    else:
        private_sic = Regs.objects.get_or_create(user=user, reg_type='91')[0]
        private_sic.second_in_command = avoid_none(flight.filter(second_in_command=True).filter(private_query), 'duration') + avoid_none(imported.filter(is_91=True), 'second_in_command')
        private_sic.save()

@receiver(pre_save, sender=Profile)
def create_power_instances(sender, instance, **kwargs):

    user = instance.user

    Power.objects.get_or_create(user=user, role='PIC')
    Power.objects.get_or_create(user=user, role='SIC')
    Power.objects.get_or_create(user=user, role='Total')

@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def power_update(sender, instance, **kwargs):

    user = instance.user

    flight = Flight.objects.filter(user=user)
    imported = Imported.objects.filter(user=user)

    turbine_query = Q(aircraft_type__turbine=True)
    piston_query = Q(aircraft_type__piston=True)

    if not flight.filter(turbine_query) and not imported.filter(turbine_query):
        pass
    else:
        pic = Power.objects.get_or_create(user=user, role='PIC')[0]
        pic.turbine = avoid_none(flight.filter(pilot_in_command=True).filter(turbine_query), 'duration') + avoid_none(imported.filter(turbine_query), 'pilot_in_command')
        pic.save()

        sic = Power.objects.get_or_create(user=user, role='SIC')[0]
        sic.turbine = avoid_none(flight.filter(second_in_command=True).filter(turbine_query), 'duration') + avoid_none(imported.filter(turbine_query), 'second_in_command')
        sic.save()

    if not flight.filter(piston_query) and not imported.filter(piston_query):
        pass
    else:
        pic = Power.objects.get_or_create(user=user, role='PIC')[0]
        pic.piston = avoid_none(flight.filter(pilot_in_command=True).filter(piston_query), 'duration') + avoid_none(imported.filter(turbine_query), 'pilot_in_command')
        pic.save()

        sic = Power.objects.get_or_create(user=user, role='SIC')[0]
        sic.piston = avoid_none(flight.filter(second_in_command=True).filter(piston_query), 'duration') + avoid_none(imported.filter(turbine_query), 'second_in_command')
        sic.save()


    total = Power.objects.get_or_create(user=user, role='Total')[0]

    total.turbine = pic.turbine + sic.turbine
    total.piston = pic.piston + sic.piston

    total.save()

@receiver(pre_save, sender=Profile)
def create_endorsement_instances(sender, instance, **kwargs):

    user = instance.user

    Endorsement.objects.get_or_create(user=user, endorsement="Simple")
    Endorsement.objects.get_or_create(user=user, endorsement="Complex")
    Endorsement.objects.get_or_create(user=user, endorsement='High Performance')
    Endorsement.objects.get_or_create(user=user, endorsement='Tailwheel')
    Endorsement.objects.get_or_create(user=user, endorsement='Type Rating')

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def endorsement_update(sender, instance, **kwargs):

    user = instance.user

    simple_query = Q(aircraft_type__simple=True)
    compleks_query = Q(aircraft_type__compleks=True)
    high_performance_query = Q(aircraft_type__high_performance=True)
    tailwheel_query = Q(aircraft_type__tailwheel=True)
    type_rating_query = Q(aircraft_type__requires_type=True)

    try:
        simple = Endorsement.objects.get(user=user, endorsement="Simple")
        simple_total = Flight.objects.filter(user=user).filter(simple_query).aggregate(Sum('duration'))
        if simple_total.get('duration__sum') is None:
            simple_total = 0
        else:
            simple_total = round(simple_total.get('duration__sum'),1)
        simple.total = simple_total
        simple.save()

    except ObjectDoesNotExist:
        pass

    try:
        compleks = Endorsement.objects.get(user=user, endorsement="Complex")

        compleks_total = Flight.objects.filter(user=user).filter(compleks_query).aggregate(Sum('duration'))
        if compleks_total.get('duration__sum') is None:
            compleks_total = 0
        else:
            compleks_total = round(compleks_total.get('duration__sum'),1)
        compleks.total = compleks_total
        compleks.save()

    except ObjectDoesNotExist:
        pass

    try:
        high_performance = Endorsement.objects.get(user=user, endorsement='High Performance')

        high_performance_total = Flight.objects.filter(user=user).filter(high_performance_query).aggregate(Sum('duration'))
        if high_performance_total.get('duration__sum') is None:
            high_performance_total = 0
        else:
            high_performance_total = round(high_performance_total.get('duration__sum'),1)
        high_performance.total = high_performance_total
        high_performance.save()

    except ObjectDoesNotExist:
        pass

    try:
        tailwheel = Endorsement.objects.get(user=user, endorsement='Tailwheel')

        tailwheel_total = Flight.objects.filter(user=user).filter(tailwheel_query).aggregate(Sum('duration'))
        if tailwheel_total.get('duration__sum') is None:
            tailwheel_total = 0
        else:
            tailwheel_total = round(tailwheel_total.get('duration__sum'),1)
        tailwheel.total = tailwheel_total
        tailwheel.save()

    except ObjectDoesNotExist:
        pass

    try:
        type_rating = Endorsement.objects.get(user=user, endorsement='Type Rating')

        type_rating_total = Flight.objects.filter(user=user).filter(type_rating_query).aggregate(Sum('duration'))
        if type_rating_total.get('duration__sum') is None:
            type_rating_total = 0
        else:
            type_rating_total = round(type_rating_total.get('duration__sum'),1)
        type_rating.total = type_rating_total
        type_rating.save()

    except ObjectDoesNotExist:
        pass
