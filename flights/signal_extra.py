from flights.queryset_helpers import is_user_deletion
from flights.models import Flight, TailNumber, Aircraft, Imported, Endorsement, Regs, Power, Weight
from django.db.models.signals import post_save, post_delete
from django.db import transaction
from django.db.models import Q, Sum
from django.core.exceptions import ObjectDoesNotExist
from django.dispatch import receiver
from flights.queryset_helpers import avoid_none


@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def weight_update(sender, instance, dispatch_uid="weight_update", **kwargs):
    if is_user_deletion(kwargs.get('origin')):
        return

    flight = Flight.objects.filter(user=instance.user).exclude(simulator=True)
    imported = Imported.objects.filter(user=instance.user)
    for label, field in (('Small', 'small'), ('Large', 'large'), ('Heavy', 'heavy'), ('Super', 'superr')):
        dated = flight.filter(**{'aircraft_type__' + field: True})
        historical = imported.filter(**{'aircraft_type__' + field: True})
        if dated.exists() or historical.exists():
            Weight.objects.update_or_create(user=instance.user, weight=label, defaults={
                'total': avoid_none(dated, 'duration') + avoid_none(historical, 'total_time')})
        else:
            Weight.objects.filter(user=instance.user, weight=label).delete()


@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
def regs_update(sender, instance, dispatch_uid="regs_update", **kwargs):
    if is_user_deletion(kwargs.get('origin')):
        return

    refresh_operating_rule_summaries(instance.user_id, using=kwargs.get('using') or instance._state.db or 'default')


def refresh_operating_rule_summaries(user_id, *, using='default'):
    """Aggregate all three rule categories together; never load flight records."""
    rules = ('91', '121', '135')
    roles = ('pilot_in_command', 'second_in_command')
    flight_sums = {}
    imported_sums = {}
    for rule in rules:
        for role in roles:
            key = f'r{rule}_{role}'
            flight_sums[key] = Sum('duration', filter=Q(**{
                f'registration__is_{rule}': True, role: True,
            }))
            imported_sums[key] = Sum(role, filter=Q(**{f'is_{rule}': True}))

    with transaction.atomic(using=using):
        flights = Flight.objects.using(using).filter(user_id=user_id).exclude(simulator=True).aggregate(**flight_sums)
        imported = Imported.objects.using(using).filter(user_id=user_id).aggregate(**imported_sums)
        summaries = Regs.objects.using(using)
        # The unique (user, reg_type) constraint makes first-time creation safe.
        summaries.bulk_create([
            Regs(user_id=user_id, reg_type=rule) for rule in rules
        ], ignore_conflicts=True)
        rows = list(summaries.filter(user_id=user_id, reg_type__in=rules))
        for row in rows:
            for role in roles:
                key = f'r{row.reg_type}_{role}'
                setattr(row, role, round(flights[key] or 0, 1) + round(imported[key] or 0, 1))
        summaries.bulk_update(rows, roles)


@receiver(post_save, sender=TailNumber)
@receiver(post_delete, sender=TailNumber)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def power_update(sender, instance, dispatch_uid="power_update", **kwargs):
    if is_user_deletion(kwargs.get('origin')):
        return

    from flights.aircraft_characteristics import ENGINE_FIELDS
    # A hidden engine is not tracked as engine time, even if an older direct
    # import left an engine flag on a glider or balloon.
    flight = Flight.objects.filter(user=instance.user).exclude(simulator=True).exclude(
        Q(aircraft_type__aircraft_category='GL') | Q(aircraft_type__aircraft_category='LTA', aircraft_type__aircraft_class='BALLOON'))
    imported = Imported.objects.filter(user=instance.user).exclude(
        Q(aircraft_type__aircraft_category='GL') | Q(aircraft_type__aircraft_category='LTA', aircraft_type__aircraft_class='BALLOON'))
    values = {role: {} for role in ('PIC', 'SIC', 'Total')}
    for engine in ENGINE_FIELDS:
        for label, role in (('PIC', 'pilot_in_command'), ('SIC', 'second_in_command')):
            values[label][engine] = avoid_none(flight.filter(**{role: True, 'aircraft_type__' + engine: True}), 'duration') + avoid_none(
                imported.filter(**{'aircraft_type__' + engine: True}), role)
        values['Total'][engine] = values['PIC'][engine] + values['SIC'][engine]
    for role, defaults in values.items():
        Power.objects.update_or_create(user=instance.user, role=role, defaults=defaults)


@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def endorsement_update(sender, instance, dispatch_uid="endorsement_update", **kwargs):
    if is_user_deletion(kwargs.get('origin')):
        return

    user = instance.user

    flight = Flight.objects.filter(user=user).exclude(simulator=True)
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
