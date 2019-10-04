from flights.models import Flight, TailNumber, Aircraft, Imported, Endorsement, Regs, Power, Weight
from django.db.models.signals import post_save, post_delete
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.dispatch import receiver
from flights.queryset_helpers import avoid_none
from django.core.signals import request_finished

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
    lsa_query = Q(aircraft_type__light_sport=True)

    if not flight.filter(superr_query) and not imported.filter(superr_query):
        try:
            superr = Weight.objects.get(user=user, weight='Super')
            superr.delete()

        except ObjectDoesNotExist:
            pass

    else:
        superr = Weight.objects.get_or_create(user=user, weight='Super')[0]
        superr.total = avoid_none(flight.filter(superr_query), 'duration') + avoid_none(imported.filter(superr_query), 'total_time')
        superr.save()

    if not flight.filter(heavy_query) and not imported.filter(heavy_query):
        try:
            heavy = Weight.objects.get(user=user, weight='Heavy')
            heavy.delete()

        except ObjectDoesNotExist:
            pass

    else:
        heavy = Weight.objects.get_or_create(user=user, weight='Heavy')[0]
        heavy.total = avoid_none(flight.filter(heavy_query), 'duration') + avoid_none(imported.filter(heavy_query), 'total_time')
        heavy.save()

    if not flight.filter(large_query) and not imported.filter(large_query):
        try:
            large = Weight.objects.get(user=user, weight='Large')
            large.delete()

        except ObjectDoesNotExist:
            pass

    else:
        large = Weight.objects.get_or_create(user=user, weight='Large')[0]
        large.total = avoid_none(flight.filter(large_query), 'duration') + avoid_none(imported.filter(large_query), 'total_time')
        large.save()

    if not flight.filter(medium_query) and not imported.filter(medium_query):
        try:
            medium = Weight.objects.get(user=user, weight='Medium')
            medium.delete()

        except ObjectDoesNotExist:
            pass

    else:
        medium = Weight.objects.get_or_create(user=user, weight='Medium')[0]
        medium.total = avoid_none(flight.filter(medium_query), 'duration') + avoid_none(imported.filter(medium_query), 'total_time')
        medium.save()

    if not flight.filter(small_query) and not imported.filter(small_query):
        try:
            small = Weight.objects.get(user=user, weight='Small')
            small.delete()

        except ObjectDoesNotExist:
            pass

    else:
        small = Weight.objects.get_or_create(user=user, weight='Small')[0]
        small.total = avoid_none(flight.filter(small_query), 'duration') + avoid_none(imported.filter(small_query), 'total_time')
        small.save()

    if not flight.filter(lsa_query) and not imported.filter(lsa_query):
        try:
            lsa = Weight.objects.get(user=user, weight='LSA')
            lsa.delete()

        except ObjectDoesNotExist:
            pass

    else:
        lsa = Weight.objects.get_or_create(user=user, weight='LSA')[0]
        lsa.total = avoid_none(flight.filter(lsa_query), 'duration') + avoid_none(imported.filter(lsa_query), 'total_time')
        lsa.save()


request_finished.connect(weight_update, dispatch_uid="weight_update")


@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def regs_update(sender, instance, **kwargs):

    user = instance.user

    flight = Flight.objects.filter(user=user)
    imported = Imported.objects.filter(user=user)

    airline_query = Q(registration__is_121=True)
    charter_query = Q(registration__is_135=True)
    private_query = Q(registration__is_91=True)

    if flight.filter(pilot_in_command=True).filter(airline_query):
        airline_pic = Regs.objects.get_or_create(user=user, reg_type='121')[0]
        airline_pic.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True).filter(airline_query), 'duration') + avoid_none(imported.filter(is_121=True), 'pilot_in_command')
        airline_pic.save()
    else:
        airline_pic = Regs.objects.get_or_create(user=user, reg_type='121')[0]
        airline_pic.pilot_in_command = 0
        airline_pic.save()

    if flight.filter(second_in_command=True).filter(airline_query):
        airline_sic = Regs.objects.get_or_create(user=user, reg_type='121')[0]
        airline_sic.second_in_command = avoid_none(flight.filter(second_in_command=True).filter(airline_query), 'duration') + avoid_none(imported.filter(is_121=True), 'second_in_command')
        airline_sic.save
    else:
        airline_sic = Regs.objects.get_or_create(user=user, reg_type='121')[0]
        airline_sic.second_in_command = 0
        airline_sic.save()

    if flight.filter(pilot_in_command=True).filter(charter_query):
        charter_pic = Regs.objects.get_or_create(user=user, reg_type='135')[0]
        charter_pic.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True).filter(charter_query), 'duration') + avoid_none(imported.filter(is_135=True), 'pilot_in_command')
        charter_pic.save()
    else:
        charter_pic = Regs.objects.get_or_create(user=user, reg_type='135')[0]
        charter_pic.pilot_in_command = 0
        charter_pic.save()

    if flight.filter(second_in_command=True).filter(charter_query):
        charter_sic = Regs.objects.get_or_create(user=user, reg_type='135')[0]
        charter_sic.second_in_command = avoid_none(flight.filter(second_in_command=True).filter(charter_query), 'duration') + avoid_none(imported.filter(is_135=True), 'second_in_command')
        charter_sic.save()
    else:
        charter_sic = Regs.objects.get_or_create(user=user, reg_type='135')[0]
        charter_sic.second_in_command = 0
        charter_sic.save()

    if flight.filter(pilot_in_command=True).filter(private_query):
        private_pic = Regs.objects.get_or_create(user=user, reg_type='91')[0]
        private_pic.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True).filter(private_query), 'duration') + avoid_none(imported.filter(is_135=True), 'pilot_in_command')
        private_pic.save()
    else:
        private_pic = Regs.objects.get_or_create(user=user, reg_type='91')[0]
        private_pic.pilot_in_command = 0
        private_pic.save()

    if flight.filter(pilot_in_command=True).filter(private_query):
        private_sic = Regs.objects.get_or_create(user=user, reg_type='91')[0]
        private_sic.second_in_command = avoid_none(flight.filter(second_in_command=True).filter(private_query), 'duration') + avoid_none(imported.filter(is_135=True), 'second_in_command')
        private_sic.save()
    else:
        private_sic = Regs.objects.get_or_create(user=user, reg_type='91')[0]
        private_sic.second_in_command = 0
        private_sic.save()


request_finished.connect(regs_update, dispatch_uid="regs_update")


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
    total = Power.objects.get_or_create(user=user, role='Total')[0]
    pic = Power.objects.get_or_create(user=user, role='PIC')[0]
    sic = Power.objects.get_or_create(user=user, role='SIC')[0]

    turbine_query = Q(aircraft_type__turbine=True)
    piston_query = Q(aircraft_type__piston=True)

    if not flight.filter(turbine_query) and not imported.filter(turbine_query):
        pic.turbine = 0
        pic.save()
        sic.turbine = 0
        sic.save()
        total.turbine = 0
        total.save()
    else:
        pic.turbine = avoid_none(flight.filter(pilot_in_command=True).filter(turbine_query), 'duration') + avoid_none(imported.filter(turbine_query), 'pilot_in_command')
        pic.save()

        sic.turbine = avoid_none(flight.filter(second_in_command=True).filter(turbine_query), 'duration') + avoid_none(imported.filter(turbine_query), 'second_in_command')
        sic.save()

        total.turbine = pic.turbine + sic.turbine
        total.piston = pic.piston + sic.piston

        total.save()

    if not flight.filter(piston_query) and not imported.filter(piston_query):
        pic.piston = 0
        pic.save()
        sic.piston = 0
        sic.save()

    else:
        pic.piston = avoid_none(flight.filter(pilot_in_command=True).filter(piston_query), 'duration') + avoid_none(imported.filter(piston_query), 'pilot_in_command')
        pic.save()

        sic.piston = avoid_none(flight.filter(second_in_command=True).filter(piston_query), 'duration') + avoid_none(imported.filter(piston_query), 'second_in_command')
        sic.save()

        total.turbine = pic.turbine + sic.turbine
        total.piston = pic.piston + sic.piston

        total.save()


request_finished.connect(power_update, dispatch_uid="power_update")


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
        try:
            simple = Endorsement.objects.get(user=user, endorsement="Simple")
            simple.delete()

        except ObjectDoesNotExist:
            pass

    else:
        simple = Endorsement.objects.get_or_create(user=user, endorsement="Simple")[0]
        simple.total = avoid_none(flight.filter(simple_query), 'duration') + avoid_none(imported.filter(simple_query), 'total_time')
        simple.save()

    if not flight.filter(compleks_query) and not imported.filter(compleks_query):
        try:
            compleks = Endorsement.objects.get(user=user, endorsement="Complex")
            compleks.delete()

        except ObjectDoesNotExist:
            pass

    else:
        compleks = Endorsement.objects.get_or_create(user=user, endorsement="Complex")[0]
        compleks.total = avoid_none(flight.filter(compleks_query), 'duration') + avoid_none(imported.filter(compleks_query), 'total_time')
        compleks.save()

    if not flight.filter(high_performance_query) and not imported.filter(high_performance_query):
        try:
            high_performance = Endorsement.objects.get(user=user, endorsement="High Performance")
            high_performance.delete()

        except ObjectDoesNotExist:
            pass

    else:
        high_performance = Endorsement.objects.get_or_create(user=user, endorsement="High Performance")[0]
        high_performance.total = avoid_none(flight.filter(high_performance_query), 'duration') + avoid_none(imported.filter(high_performance_query), 'total_time')
        high_performance.save()

    if not flight.filter(tailwheel_query) and not imported.filter(tailwheel_query):
        try:
            tailwheel = Endorsement.objects.get(user=user, endorsement="Tailwheel")
            tailwheel.delete()

        except ObjectDoesNotExist:
            pass

    else:
        tailwheel = Endorsement.objects.get_or_create(user=user, endorsement="Tailwheel")[0]
        tailwheel.total = avoid_none(flight.filter(tailwheel_query), 'duration') + avoid_none(imported.filter(tailwheel_query), 'total_time')
        tailwheel.save()

    if not flight.filter(type_rating_query) and not imported.filter(type_rating_query):
        try:
            type_rating = Endorsement.objects.get(user=user, endorsement="Type Rating")
            type_rating.delete()

        except ObjectDoesNotExist:
            pass

    else:
        type_rating = Endorsement.objects.get_or_create(user=user, endorsement="Type Rating")[0]
        type_rating.total = avoid_none(flight.filter(type_rating_query), 'duration') + avoid_none(imported.filter(type_rating_query), 'total_time')
        type_rating.save()


request_finished.connect(endorsement_update, dispatch_uid="endorsement_update")
