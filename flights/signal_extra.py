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
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
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
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
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
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
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
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def endorsement_update(sender, instance, **kwargs):

    user = instance.user

    flight = Flight.objects.filter(user=user)
    imported = Imported.objects.filter(user=user)

    simple_query = Q(aircraft_type__simple=True)
    compleks_query = Q(aircraft_type__compleks=True)
    high_performance_query = Q(aircraft_type__high_performance=True)
    tailwheel_query = Q(aircraft_type__tailwheel=True)
    type_rating_query = Q(aircraft_type__requires_type=True)

    if not flight.filter(simple_query) and not imported.filter(simple_query):
        pass
    else:
        simple = Endorsement.objects.get_or_create(user=user, endorsement="Simple")[0]
        simple.total = avoid_none(flight.filter(simple_query), 'duration') + avoid_none(imported.filter(simple_query), 'total_time')
        simple.save()

    if not flight.filter(compleks_query) and not imported.filter(compleks_query):
        pass
    else:
        compleks = Endorsement.objects.get_or_create(user=user, endorsement="Complex")[0]
        compleks.total = avoid_none(flight.filter(compleks_query), 'duration') + avoid_none(imported.filter(compleks_query), 'total_time')
        compleks.save()

    if not flight.filter(high_performance_query) and not imported.filter(high_performance_query):
        pass
    else:
        high_performance = Endorsement.objects.get_or_create(user=user, endorsement="High Performance")[0]
        high_performance.total = avoid_none(flight.filter(high_performance_query), 'duration') + avoid_none(imported.filter(high_performance_query), 'total_time')
        high_performance.save()

    if not flight.filter(tailwheel_query) and not imported.filter(tailwheel_query):
        pass
    else:
        tailwheel = Endorsement.objects.get_or_create(user=user, endorsement="Tailwheel")[0]
        tailwheel.total = avoid_none(flight.filter(tailwheel_query), 'duration') + avoid_none(imported.filter(tailwheel_query), 'total_time')
        tailwheel.save()

    if not flight.filter(type_rating_query) and not imported.filter(type_rating_query):
        pass
    else:
        type_rating = Endorsement.objects.get_or_create(user=user, endorsement="Type Rating")[0]
        type_rating.total = avoid_none(flight.filter(type_rating_query), 'duration') + avoid_none(imported.filter(type_rating_query), 'total_time')
        type_rating.save()
