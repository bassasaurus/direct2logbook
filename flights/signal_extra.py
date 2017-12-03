from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def weight_updater(sender, **kwargs):
    superr = Weight.objects.get(weight="Super")
    heavy = Weight.objects.get(weight="Heavy")
    large = Weight.objects.get(weight="Large")
    medium = Weight.objects.get(weight="Medium")
    small = Weight.objects.get(weight="Small")

    superr_query = Q(aircraft_type__superr=True)
    heavy_query = Q(aircraft_type__heavy=True)
    large_query = Q(aircraft_type__large=True)
    medium_query = Q(aircraft_type__medium=True)
    small_query = Q(aircraft_type__small=True)

    superr_total = Flight.objects.filter(superr_query).aggregate(Sum('duration'))
    if superr_total.get('duration__sum') is None:
        superr_total = 0
    else:
        superr_total = round(superr_total.get('duration__sum'),1)
    superr.total = superr_total
    superr.save()

    heavy_total = Flight.objects.filter(heavy_query).aggregate(Sum('duration'))
    if heavy_total.get('duration__sum') is None:
        heavy_total = 0
    else:
        heavy_total = round(heavy_total.get('duration__sum'),1)
    heavy.total = heavy_total
    heavy.save()

    large_total = Flight.objects.filter(large_query).aggregate(Sum('duration'))
    if large_total.get('duration__sum') is None:
        large_total = 0
    else:
        large_total = round(large_total.get('duration__sum'),1)
    large.total = large_total
    large.save()

    medium_total = Flight.objects.filter(medium_query).aggregate(Sum('duration'))
    if medium_total.get('duration__sum') is None:
        medium_total = 0
    else:
        medium_total = round(medium_total.get('duration__sum'),1)
    medium.total = medium_total
    medium.save()

    small_total = Flight.objects.filter(small_query).aggregate(Sum('duration'))
    if small_total.get('duration__sum') is None:
        small_total = 0
    else:
        small_total = round(small_total.get('duration__sum'),1)
    small.total = small_total
    small.save()

@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def regs_updater(sender, **kwargs):
    airline = Regs.objects.get(reg_type='121')
    charter = Regs.objects.get(reg_type='135')
    private = Regs.objects.get(reg_type='91')

    airline_query = Q(registration__is_121=True)
    charter_query = Q(registration__is_135=True)
    private_query = Q(registration__is_91=True)

    airline_pic = Flight.objects.filter(pilot_in_command=True).filter(airline_query).aggregate(Sum('duration'))
    if airline_pic.get('duration__sum') is None:
        airline_pic = 0
    else:
        airline_pic = round(airline_pic.get('duration__sum'),1)
    airline.pilot_in_command = airline_pic

    airline_sic = Flight.objects.filter(second_in_command=True).filter(airline_query).aggregate(Sum('duration'))
    if airline_sic.get('duration__sum') is None:
        airline_sic = 0
    else:
        airline_sic = round(airline_sic.get('duration__sum'),1)
    airline.second_in_command = airline_sic

    airline.save()

    charter_pic = Flight.objects.filter(pilot_in_command=True).filter(charter_query).aggregate(Sum('duration'))
    if charter_pic.get('duration__sum') is None:
        charter_pic = 0
    else:
        charter_pic = round(charter_pic.get('duration__sum'),1)
    charter.pilot_in_command = charter_pic

    charter_sic = Flight.objects.filter(second_in_command=True).filter(charter_query).aggregate(Sum('duration'))
    if charter_sic.get('duration__sum') is None:
        charter_sic = 0
    else:
        charter_sic = round(charter_sic.get('duration__sum'),1)
    charter.second_in_command = charter_sic

    charter.save()

    private_pic = Flight.objects.filter(pilot_in_command=True).filter(private_query).aggregate(Sum('duration'))
    if private_pic.get('duration__sum') is None:
        private_pic = 0
    else:
        private_pic = round(private_pic.get('duration__sum'),1)
    private.pilot_in_command = private_pic

    private_sic = Flight.objects.filter(second_in_command=True).filter(private_query).aggregate(Sum('duration'))
    if private_sic.get('duration__sum') is None:
        private_sic = 0
    else:
        private_sic = round(private_sic.get('duration__sum'),1)
    private.second_in_command = private_sic

    private.save()

@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def power_updater(sender, **kwargs):
    pic = Power.objects.get(role='PIC')
    sic = Power.objects.get(role='SIC')
    total = Power.objects.get(role='Total')

    turbine_query = Q(aircraft_type__turbine=True)
    piston_query = Q(aircraft_type__piston=True)

    pic_turbine = Flight.objects.filter(pilot_in_command=True).filter(turbine_query).aggregate(Sum('duration'))
    if pic_turbine.get('duration__sum') is None:
        pic_turbine = 0
    else:
        pic_turbine = round(pic_turbine.get('duration__sum'),1)
    pic.turbine = pic_turbine

    sic_turbine = Flight.objects.filter(second_in_command=True).filter(turbine_query).aggregate(Sum('duration'))
    if sic_turbine.get('duration__sum') is None:
        sic_turbine = 0
    else:
        sic_turbine = round(sic_turbine.get('duration__sum'),1)
    sic.turbine = sic_turbine

    pic_piston = Flight.objects.filter(pilot_in_command=True).filter(piston_query).aggregate(Sum('duration'))
    if pic_piston.get('duration__sum') is None:
        pic_piston = 0
    else:
        pic_piston = round(pic_piston.get('duration__sum'),1)
    pic.piston = pic_piston


    sic_piston = Flight.objects.filter(second_in_command=True).filter(piston_query).aggregate(Sum('duration'))
    if sic_piston.get('duration__sum') is None:
        sic_piston = 0
    else:
        sic_piston = round(sic_piston.get('duration__sum'),1)
    sic.piston = sic_piston

    pic.save()
    sic.save()

    total_turbine = pic_turbine + sic_turbine
    total.turbine = total_turbine
    total_piston = pic_piston + sic_piston
    total.piston = total_piston

    total.save()

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def endorsement_updater(sender, **kwargs):
    simple = Endorsement.objects.get(endorsement="Simple")
    compleks = Endorsement.objects.get(endorsement="Complex")
    high_performance = Endorsement.objects.get(endorsement='High Performance')
    tailwheel = Endorsement.objects.get(endorsement='Tailwheel')
    type_rating = Endorsement.objects.get(endorsement='Type Rating')

    simple_query = Q(aircraft_type__simple=True)
    compleks_query = Q(aircraft_type__compleks=True)
    high_performance_query = Q(aircraft_type__high_performance=True)
    tailwheel_query = Q(aircraft_type__tailwheel=True)
    type_rating_query = Q(aircraft_type__requires_type=True)

    simple_total = Flight.objects.filter(simple_query).aggregate(Sum('duration'))
    if simple_total.get('duration__sum') is None:
        simple_total = 0
    else:
        simple_total = round(simple_total.get('duration__sum'),1)
    simple.total = simple_total
    simple.save()

    compleks_total = Flight.objects.filter(compleks_query).aggregate(Sum('duration'))
    if compleks_total.get('duration__sum') is None:
        compleks_total = 0
    else:
        compleks_total = round(compleks_total.get('duration__sum'),1)
    compleks.total = compleks_total
    compleks.save()

    high_performance_total = Flight.objects.filter(high_performance_query).aggregate(Sum('duration'))
    if high_performance_total.get('duration__sum') is None:
        high_performance_total = 0
    else:
        high_performance_total = round(high_performance_total.get('duration__sum'),1)
    high_performance.total = high_performance_total
    high_performance.save()

    tailwheel_total = Flight.objects.filter(tailwheel_query).aggregate(Sum('duration'))
    if tailwheel_total.get('duration__sum') is None:
        tailwheel_total = 0
    else:
        tailwheel_total = round(tailwheel_total.get('duration__sum'),1)
    tailwheel.total = tailwheel_total
    tailwheel.save()

    type_rating_total = Flight.objects.filter(type_rating_query).aggregate(Sum('duration'))
    if type_rating_total.get('duration__sum') is None:
        type_rating_total = 0
    else:
        type_rating_total = round(type_rating_total.get('duration__sum'),1)
    type_rating.total = type_rating_total
    type_rating.save()
