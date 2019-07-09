from flights.models import *
from accounts.models import Profile
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
from django.core.exceptions import ObjectDoesNotExist

@receiver(pre_save, sender=Profile)
def create_weight_instances(sender, instance, **kwargs):

    user = instance.user

    Weight.objects.get_or_create(user=user, weight="Super")
    Weight.objects.get_or_create(user=user, weight="Heavy")
    Weight.objects.get_or_create(user=user, weight="Large")
    Weight.objects.get_or_create(user=user, weight="Medium")
    Weight.objects.get_or_create(user=user, weight="Small")

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def weight_update(sender, instance, **kwargs):

    user = instance.user

    superr_query = Q(aircraft_type__superr=True)
    heavy_query = Q(aircraft_type__heavy=True)
    large_query = Q(aircraft_type__large=True)
    medium_query = Q(aircraft_type__medium=True)
    small_query = Q(aircraft_type__small=True)

    try:
        superr = Weight.objects.get(user=user, weight="Super")

        superr_total = Flight.objects.filter(user=user).filter(superr_query).aggregate(Sum('duration'))
        if superr_total.get('duration__sum') is None:
            superr_total = 0
        else:
            superr_total = round(superr_total.get('duration__sum'),1)
        superr.total = superr_total
        superr.save()

    except ObjectDoesNotExist:
        pass

    try:
        heavy = Weight.objects.get(user=user, weight="Heavy")

        heavy_total = Flight.objects.filter(user=user).filter(heavy_query).aggregate(Sum('duration'))
        if heavy_total.get('duration__sum') is None:
            heavy_total = 0
        else:
            heavy_total = round(heavy_total.get('duration__sum'),1)
        heavy.total = heavy_total
        heavy.save()

    except ObjectDoesNotExist:
        pass

    try:
        large = Weight.objects.get(user=user, weight="Large")

        large_total = Flight.objects.filter(user=user).filter(large_query).aggregate(Sum('duration'))
        if large_total.get('duration__sum') is None:
            large_total = 0
        else:
            large_total = round(large_total.get('duration__sum'),1)
        large.total = large_total
        large.save()

    except ObjectDoesNotExist:
        pass

    try:
        medium = Weight.objects.get(user=user, weight="Medium")

        medium_total = Flight.objects.filter(user=user).filter(medium_query).aggregate(Sum('duration'))
        if medium_total.get('duration__sum') is None:
            medium_total = 0
        else:
            medium_total = round(medium_total.get('duration__sum'),1)
        medium.total = medium_total
        medium.save()

    except ObjectDoesNotExist:
        pass

    try:
        small = Weight.objects.get(user=user, weight="Small")

        small_total = Flight.objects.filter(user=user).filter(small_query).aggregate(Sum('duration'))
        if small_total.get('duration__sum') is None:
            small_total = 0
        else:
            small_total = round(small_total.get('duration__sum'),1)
        small.total = small_total
        small.save()

    except ObjectDoesNotExist:
        pass

@receiver(pre_save, sender=Profile)
def create_reg_instances(sender, instance, **kwargs):

    user = instance.user

    Regs.objects.get_or_create(user=user, reg_type='121')
    Regs.objects.get_or_create(user=user, reg_type='135')
    Regs.objects.get_or_create(user=user, reg_type='91')

@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def regs_update(sender, instance, **kwargs):

    user = instance.user

    try:
        airline = Regs.objects.get(user=user, reg_type='121')
        airline_query = Q(registration__is_121=True)

        airline_pic = Flight.objects.filter(user=user).filter(pilot_in_command=True).filter(airline_query).aggregate(Sum('duration'))
        if airline_pic.get('duration__sum') is None:
            airline_pic = 0
        else:
            airline_pic = round(airline_pic.get('duration__sum'),1)
        airline.pilot_in_command = airline_pic

        airline_sic = Flight.objects.filter(user=user).filter(second_in_command=True).filter(airline_query).aggregate(Sum('duration'))
        if airline_sic.get('duration__sum') is None:
            airline_sic = 0
        else:
            airline_sic = round(airline_sic.get('duration__sum'),1)
        airline.second_in_command = airline_sic

        airline.save()

    except ObjectDoesNotExist:
        pass

    try:
        charter = Regs.objects.get(user=user, reg_type='135')
        charter_query = Q(registration__is_135=True)

        charter_pic = Flight.objects.filter(user=user).filter(pilot_in_command=True).filter(charter_query).aggregate(Sum('duration'))
        if charter_pic.get('duration__sum') is None:
            charter_pic = 0
        else:
            charter_pic = round(charter_pic.get('duration__sum'),1)
        charter.pilot_in_command = charter_pic

        charter_sic = Flight.objects.filter(user=user).filter(second_in_command=True).filter(charter_query).aggregate(Sum('duration'))
        if charter_sic.get('duration__sum') is None:
            charter_sic = 0
        else:
            charter_sic = round(charter_sic.get('duration__sum'),1)
        charter.second_in_command = charter_sic

        charter.save()

    except ObjectDoesNotExist:
        pass

    try:
        private = Regs.objects.get(user=user, reg_type='91')
        private_query = Q(registration__is_91=True)


        private_pic = Flight.objects.filter(user=user).filter(pilot_in_command=True).filter(private_query).aggregate(Sum('duration'))
        if private_pic.get('duration__sum') is None:
            private_pic = 0
        else:
            private_pic = round(private_pic.get('duration__sum'),1)
        private.pilot_in_command = private_pic

        private_sic = Flight.objects.filter(user=user).filter(second_in_command=True).filter(private_query).aggregate(Sum('duration'))
        if private_sic.get('duration__sum') is None:
            private_sic = 0
        else:
            private_sic = round(private_sic.get('duration__sum'),1)
        private.second_in_command = private_sic

        private.save()

    except ObjectDoesNotExist:
        pass

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

    turbine_query = Q(aircraft_type__turbine=True)
    piston_query = Q(aircraft_type__piston=True)

    try:
        pic = Power.objects.get(user=user, role='PIC')

        pic_turbine = Flight.objects.filter(user=user).filter(pilot_in_command=True).filter(turbine_query).aggregate(Sum('duration'))
        if pic_turbine.get('duration__sum') is None:
            pic_turbine = 0
        else:
            pic_turbine = round(pic_turbine.get('duration__sum'),1)
        pic.turbine = pic_turbine

        pic_piston = Flight.objects.filter(user=user).filter(pilot_in_command=True).filter(piston_query).aggregate(Sum('duration'))
        if pic_piston.get('duration__sum') is None:
            pic_piston = 0
        else:
            pic_piston = round(pic_piston.get('duration__sum'),1)
        pic.piston = pic_piston

        pic.save()

    except ObjectDoesNotExist:
        pass

    try:
        sic = Power.objects.get(user=user, role='SIC')

        sic_turbine = Flight.objects.filter(user=user).filter(second_in_command=True).filter(turbine_query).aggregate(Sum('duration'))
        if sic_turbine.get('duration__sum') is None:
            sic_turbine = 0
        else:
            sic_turbine = round(sic_turbine.get('duration__sum'),1)
        sic.turbine = sic_turbine

        sic_piston = Flight.objects.filter(user=user).filter(second_in_command=True).filter(piston_query).aggregate(Sum('duration'))
        if sic_piston.get('duration__sum') is None:
            sic_piston = 0
        else:
            sic_piston = round(sic_piston.get('duration__sum'),1)
        sic.piston = sic_piston

        sic.save()

    except ObjectDoesNotExist:
        pass

    try:
        total = Power.objects.get(user=user, role='Total')

        total_turbine = pic_turbine + sic_turbine
        total.turbine = total_turbine
        total_piston = pic_piston + sic_piston
        total.piston = total_piston

        total.save()

    except ObjectDoesNotExist:
        pass

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
